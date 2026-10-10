"""Acesso ao banco (Supabase)."""
import math

import pandas as pd
import streamlit as st
from supabase import create_client

from categorize import normalizar


@st.cache_resource
def cliente():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def _num(x, casas=None):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(x):
        return None
    return round(x, casas) if casas is not None else x


def buscar_todos(tabela, select="*", order="id"):
    sb, dados, ini, passo = cliente(), [], 0, 1000
    while True:
        lote = sb.table(tabela).select(select).order(order).range(ini, ini + passo - 1).execute().data
        dados.extend(lote)
        if len(lote) < passo:
            return dados
        ini += passo


def limpar_cache():
    st.cache_data.clear()


# ---------- Leituras ----------
@st.cache_data(ttl=300)
def carregar_categorias():
    nomes = [r["nome"] for r in buscar_todos("categorias", "nome", order="nome")]
    if "Outros" in nomes:  # "Outros" sempre por último
        nomes.remove("Outros")
        nomes.append("Outros")
    return nomes or ["Outros"]


@st.cache_data(ttl=300)
def carregar_produtos():
    return {r["id"]: {"nome": r["nome_padrao"], "categoria": r["categoria"]}
            for r in buscar_todos("produtos", "id,nome_padrao,categoria")}


@st.cache_data(ttl=300)
def carregar_apelidos():
    return {r["descricao_norm"]: r["produto_id"]
            for r in buscar_todos("apelidos", "descricao_norm,produto_id", order="descricao_norm")}


@st.cache_data(ttl=300)
def carregar_mercados():
    rows = buscar_todos("compras", "id,mercado")
    return pd.Series([r["mercado"] for r in rows]).value_counts().index.tolist() if rows else []


def compra_existe(chave):
    if not chave:
        return False
    return bool(cliente().table("compras").select("id").eq("chave", chave).limit(1).execute().data)


@st.cache_data(ttl=300)
def df_compras():
    cols = ["id", "chave", "mercado", "cnpj", "data", "hora", "total", "origem",
            "registrado_por", "observacao"]
    rows = buscar_todos("compras", ",".join(cols))
    df = pd.DataFrame(rows, columns=cols)
    df["data"] = pd.to_datetime(df["data"])
    df["total"] = pd.to_numeric(df["total"])
    return df


@st.cache_data(ttl=300)
def df_itens():
    cols = ["id", "compra_id", "produto_id", "descricao_original", "quantidade", "unidade",
            "valor_unitario", "valor_total", "data", "mercado", "registrado_por", "produto", "categoria"]
    sel = ("id,compra_id,produto_id,descricao_original,quantidade,unidade,valor_unitario,valor_total,"
           "compras(data,mercado,registrado_por),produtos(nome_padrao,categoria)")
    rows = buscar_todos("itens", sel)
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.json_normalize(rows).rename(columns={
        "compras.data": "data", "compras.mercado": "mercado",
        "compras.registrado_por": "registrado_por",
        "produtos.nome_padrao": "produto", "produtos.categoria": "categoria",
    })
    for c in cols:
        if c not in df:
            df[c] = None
    df["produto"] = df["produto"].fillna("Sem produto")
    df["categoria"] = df["categoria"].fillna("Outros")
    df["data"] = pd.to_datetime(df["data"])
    for c in ["quantidade", "valor_unitario", "valor_total"]:
        df[c] = pd.to_numeric(df[c])
    return df[cols]


# ---------- Gravações ----------
def salvar_compra(compra: dict, itens: list):
    """compra: dados do cabeçalho. itens: dicts com descricao, produto, categoria, quantidade,
    unidade, valor_unitario, valor_total, codigo."""
    sb = cliente()
    c = sb.table("compras").insert(compra).execute().data[0]
    try:
        # 1) produtos padrão (cria os novos, atualiza categoria dos existentes)
        prods = {}
        for i in itens:
            prods[i["produto"].strip()] = i["categoria"]
        res = sb.table("produtos").upsert(
            [{"nome_padrao": n, "categoria": cat} for n, cat in prods.items()],
            on_conflict="nome_padrao").execute()
        ids = {r["nome_padrao"]: r["id"] for r in res.data}

        # 2) de/para: descrição do cupom -> produto padrão
        ap = {normalizar(i["descricao"]): ids[i["produto"].strip()] for i in itens}
        sb.table("apelidos").upsert(
            [{"descricao_norm": k, "produto_id": v} for k, v in ap.items()],
            on_conflict="descricao_norm").execute()

        # 3) itens
        sb.table("itens").insert([{
            "compra_id": c["id"],
            "produto_id": ids[i["produto"].strip()],
            "descricao_original": i["descricao"],
            "codigo": i.get("codigo") or None,
            "quantidade": _num(i.get("quantidade"), 4) or 1,
            "unidade": i.get("unidade") or None,
            "valor_unitario": _num(i.get("valor_unitario"), 4),
            "valor_total": _num(i.get("valor_total"), 2) or 0,
        } for i in itens]).execute()
    except Exception:
        sb.table("compras").delete().eq("id", c["id"]).execute()
        raise
    limpar_cache()
    return c["id"]


def excluir_compra(compra_id):
    cliente().table("compras").delete().eq("id", int(compra_id)).execute()
    limpar_cache()


def adicionar_categoria(nome):
    cliente().table("categorias").upsert({"nome": nome.strip()}, on_conflict="nome").execute()
    limpar_cache()


def atualizar_produto(pid, nome, categoria):
    cliente().table("produtos").update(
        {"nome_padrao": nome.strip(), "categoria": categoria}).eq("id", int(pid)).execute()


def _mesclar(sb, origem_id, destino_id, nome_origem):
    origem_id, destino_id = int(origem_id), int(destino_id)
    sb.table("itens").update({"produto_id": destino_id}).eq("produto_id", origem_id).execute()
    sb.table("apelidos").update({"produto_id": destino_id}).eq("produto_id", origem_id).execute()
    sb.table("apelidos").upsert({"descricao_norm": normalizar(nome_origem), "produto_id": destino_id},
                                on_conflict="descricao_norm").execute()
    sb.table("produtos").delete().eq("id", origem_id).execute()


def mesclar_produtos(origem_id, destino_id, nome_origem):
    """Junta 'origem' dentro de 'destino' (itens, de/para) e apaga 'origem'."""
    _mesclar(cliente(), origem_id, destino_id, nome_origem)
    limpar_cache()


def aplicar_padronizacao(mudancas):
    """mudancas: [(produto_id, novo_nome, categoria)]. Renomeia e junta quem ficar com o mesmo nome.
    Retorna quantos grupos falharam."""
    sb = cliente()
    atuais = {r["id"]: r["nome_padrao"] for r in buscar_todos("produtos", "id,nome_padrao")}
    alvo = {int(pid): nome.strip() for pid, nome, _ in mudancas}
    cats = {int(pid): cat for pid, _, cat in mudancas}
    grupos = {}
    for pid, nome in alvo.items():
        grupos.setdefault(nome, []).append(pid)

    falhas = 0
    for nome, ids in grupos.items():
        try:
            # já existe um produto com esse nome que vai continuar com ele?
            dono = next((i for i, n in atuais.items() if n == nome and alvo.get(i, nome) == nome), None)
            if dono is None:
                dono = ids[0]
                sb.table("produtos").update({"nome_padrao": nome, "categoria": cats[dono]}) \
                    .eq("id", dono).execute()
                atuais[dono] = nome
            else:
                sb.table("produtos").update({"categoria": cats[ids[0]]}).eq("id", dono).execute()
            for pid in ids:
                if pid != dono and pid in atuais:
                    _mesclar(sb, pid, dono, atuais.pop(pid))
        except Exception as e:
            print("Falha ao padronizar", nome, e)
            falhas += 1
    limpar_cache()
    return falhas


def mover_descricao(descricao_norm, novo_produto_id):
    """Faz uma descrição específica do cupom passar a apontar para outro produto."""
    sb = cliente()
    novo_produto_id = int(novo_produto_id)
    antigo = sb.table("apelidos").select("produto_id").eq("descricao_norm", descricao_norm).execute().data
    sb.table("apelidos").upsert({"descricao_norm": descricao_norm, "produto_id": novo_produto_id},
                                on_conflict="descricao_norm").execute()
    if antigo:
        rows = (sb.table("itens").select("id,descricao_original")
                .eq("produto_id", antigo[0]["produto_id"]).execute().data)
        ids = [r["id"] for r in rows if normalizar(r["descricao_original"]) == descricao_norm]
        if ids:
            sb.table("itens").update({"produto_id": novo_produto_id}).in_("id", ids).execute()
    limpar_cache()


# ---------- Perfis ----------
def carregar_usuarios(nomes_iniciais):
    """Lê os perfis e cria os que estão em USUARIOS e ainda não existem."""
    from perfis import PADROES
    sb = cliente()
    rows = sb.table("usuarios").select("nome,senha_hash,icone,cor").execute().data
    existentes = {r["nome"] for r in rows}
    novos = []
    for i, nome in enumerate(nomes_iniciais):
        if nome not in existentes:
            icone, cor = PADROES[i % len(PADROES)]
            novos.append({"nome": nome, "icone": icone, "cor": cor})
    if novos:
        rows += sb.table("usuarios").insert(novos).execute().data
    ordem = {n: i for i, n in enumerate(nomes_iniciais)}
    return sorted(rows, key=lambda r: ordem.get(r["nome"], 99))


def salvar_senha(nome, senha_hash):
    cliente().table("usuarios").update({"senha_hash": senha_hash}).eq("nome", nome).execute()


def salvar_aparencia(nome, icone, cor):
    cliente().table("usuarios").update({"icone": icone, "cor": cor}).eq("nome", nome).execute()
