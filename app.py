import math
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

import categorize as cat
import db
import nfce
import perfis
from qr_scanner import qr_scanner

st.set_page_config(page_title="Notinha", page_icon="🛒", layout="centered")


# ================= Utilitários =================
def brl(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"


MOEDA = "R$ %.2f"


def barras_h(df, valor, rotulo):
    return (alt.Chart(df).mark_bar()
            .encode(x=alt.X(f"{valor}:Q", title=None),
                    y=alt.Y(f"{rotulo}:N", sort="-x", title=None),
                    tooltip=[rotulo, alt.Tooltip(valor, format=",.2f")])
            .properties(height=max(160, 26 * len(df))))


def csv_br(df):
    return df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")


# ================= Login e perfis =================
def usuarios():
    return db.carregar_usuarios(list(st.secrets.get("USUARIOS", ["Alan", "Gi"])))


def usuario_atual():
    return next((u for u in usuarios() if u["nome"] == st.session_state.get("usuario")), None)


def entrar(nome):
    st.query_params["t"] = db.criar_sessao(nome)
    st.session_state.logado = True
    st.session_state.usuario = nome
    st.session_state.menu = "📷 Nota"
    st.session_state.dica_atalho = True
    st.rerun()


def login():
    if st.session_state.get("logado"):
        return True
    token = st.query_params.get("t")
    if token:
        nome = db.usuario_da_sessao(token)
        if nome:
            st.session_state.logado = True
            st.session_state.usuario = nome
            return True
        del st.query_params["t"]
    st.title("🧾 Notinha")
    lista = usuarios()
    sel = st.session_state.get("login_sel")

    if not sel:
        st.subheader("Quem está usando?")
        cols = st.columns(min(len(lista), 4))
        for i, u in enumerate(lista):
            with cols[i % len(cols)]:
                st.markdown(perfis.avatar_html(u["icone"], u["cor"], 96), unsafe_allow_html=True)
                if st.button(u["nome"], key=f"perfil_{u['nome']}", use_container_width=True):
                    st.session_state.login_sel = u["nome"]
                    st.rerun()
        return False

    u = next(x for x in lista if x["nome"] == sel)
    st.markdown(perfis.avatar_html(u["icone"], u["cor"], 110), unsafe_allow_html=True)
    st.markdown(f"<h3 style='text-align:center;margin-top:0'>{u['nome']}</h3>", unsafe_allow_html=True)
    if not u.get("senha_hash"):
        st.caption("Entre com a senha do app. Você só precisa fazer isso uma vez neste aparelho.")
    with st.form("form_login"):
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar", type="primary", use_container_width=True)
    if entrar:
        if u.get("senha_hash"):
            ok = perfis.verificar(senha, u["senha_hash"])
        else:
            ok = senha == st.secrets["APP_SENHA"]
        if ok:
            entrar(u["nome"])
        else:
            st.error("Senha incorreta.")
    if st.button("Trocar de perfil"):
        st.session_state.pop("login_sel", None)
        st.rerun()
    return False


def seletor_aparencia(u):
    st.session_state.setdefault("icone_tmp", u["icone"])
    st.session_state.setdefault("cor_tmp", u["cor"])
    previa = st.empty()

    tema = st.selectbox("Tema", list(perfis.ICONES))
    escolhido = st.pills("Ícone", perfis.ICONES[tema], selection_mode="single", key=f"pill_{tema}")
    if escolhido:
        st.session_state.icone_tmp = escolhido

    cor = st.pills("Cor de fundo", list(perfis.CORES), selection_mode="single", key="pill_cor")
    if cor:
        st.session_state.cor_tmp = perfis.CORES[cor]
    with st.expander("Outra cor"):
        livre = st.color_picker("Escolha", st.session_state.cor_tmp)
        if livre != st.session_state.cor_tmp and st.button("Usar esta cor"):
            st.session_state.cor_tmp = livre
            st.rerun()

    previa.markdown(perfis.avatar_html(st.session_state.icone_tmp, st.session_state.cor_tmp, 120),
                    unsafe_allow_html=True)
    if st.button("💾 Salvar ícone", type="primary", use_container_width=True):
        db.salvar_aparencia(u["nome"], st.session_state.icone_tmp, st.session_state.cor_tmp)
        st.success("Ícone salvo.")


if not login():
    st.stop()


# ================= Revisão de itens (nota e manual) =================
def montar_revisao(itens):
    categorias = db.carregar_categorias()
    sug = cat.sugerir([i["descricao"] for i in itens], db.carregar_apelidos(),
                      db.carregar_produtos(), categorias,
                      api_key=st.secrets.get("ANTHROPIC_API_KEY"))
    linhas = []
    for i, s in zip(itens, sug):
        linhas.append({
            "status": s["status"],
            "descricao": i["descricao"],
            "valor_total": i["valor_total"],
            "produto": s["produto"],
            "categoria": s["categoria"],
            "quantidade": i.get("quantidade", 1),
            "unidade": i.get("unidade", ""),
            "valor_unitario": i.get("valor_unitario"),
            "codigo": i.get("codigo"),
        })
    return pd.DataFrame(linhas)


def editor_revisao(df, key):
    st.caption("✅ já conhecido · 🔁 parecido com um que você já tem · 🆕 novo. "
               "Ajuste o nome padrão e a categoria se precisar. Itens com o mesmo nome padrão "
               "são tratados como o mesmo produto nas análises.")
    return st.data_editor(
        df, key=key, hide_index=True, use_container_width=True,
        column_order=["status", "descricao", "valor_total", "produto", "categoria"],
        disabled=["status", "descricao", "valor_total"],
        column_config={
            "status": st.column_config.TextColumn("", width="small"),
            "descricao": st.column_config.TextColumn("Na nota"),
            "valor_total": st.column_config.NumberColumn("Valor", format=MOEDA),
            "produto": st.column_config.TextColumn("Produto", required=True),
            "categoria": st.column_config.SelectboxColumn(
                "Categoria", options=db.carregar_categorias(), required=True),
        },
    )


def itens_do_editor(df):
    itens = []
    for r in df.to_dict("records"):
        r["produto"] = (r.get("produto") or r["descricao"]).strip()
        r["categoria"] = r.get("categoria") or "Outros"
        itens.append(r)
    return itens


# ================= Páginas =================
def processar_link(url):
    url = (url or "").strip()
    if not url:
        return
    if db.compra_existe(nfce.extrair_chave(url)):
        st.warning("Essa nota já está registrada.")
        return
    with st.spinner("Consultando a SEFAZ..."):
        try:
            nota = nfce.ler_nfce(url)
        except Exception as e:
            st.error(f"Não consegui ler a nota. {e}")
            st.info("Se continuar dando erro, use o lançamento manual.")
            return
    if db.compra_existe(nota["chave"]):
        st.warning("Essa nota já está registrada.")
        return
    with st.spinner("Organizando os itens..."):
        st.session_state.nota = nota
        st.session_state.rev_nota = montar_revisao(nota["itens"])


def pagina_nota():
    if st.session_state.pop("dica_atalho", False):
        st.success("Pronto, você está logado neste aparelho.")
        st.info("Para abrir sempre já logado, adicione esta página à tela inicial **agora** "
                "(iPhone: Compartilhar → Adicionar à Tela de Início). "
                "Se já tinha um atalho antigo, apague e crie de novo.")
    st.subheader("Ler cupom fiscal")
    modo = st.radio("Como ler?", ["📷 Câmera", "🔗 Colar link", "🖼️ Foto"],
                    horizontal=True, label_visibility="collapsed")

    if modo == "📷 Câmera":
        st.caption("Aponte para o QR Code e segure firme. Ele lê sozinho.")
        lido = qr_scanner(key="scanner")
        if lido and lido.get("ts") != st.session_state.get("ultimo_scan"):
            st.session_state.ultimo_scan = lido["ts"]
            processar_link(lido.get("texto"))

    elif modo == "🔗 Colar link":
        url = st.text_input("Link do QR Code", placeholder="https://www.nfce.fazenda.sp.gov.br/...")
        if st.button("Ler nota", type="primary", disabled=not url):
            processar_link(url)

    else:
        foto = st.camera_input("Tirar foto")
        arquivo = st.file_uploader("Ou escolher da galeria", type=["jpg", "jpeg", "png", "webp"])
        img = foto or arquivo
        if img is not None:
            lido = nfce.decodificar_qr(img.getvalue())
            if not lido:
                st.warning("Não consegui ler o QR Code. Chegue mais perto, com boa luz, ou use a câmera ao vivo.")
            elif st.button("Ler nota", type="primary"):
                processar_link(lido)

    nota = st.session_state.get("nota")
    if not nota:
        return

    st.divider()
    dia = pd.to_datetime(nota["data"]).strftime("%d/%m/%Y") if nota.get("data") else "sem data"
    st.markdown(f"**{nota['mercado']}**  \n{dia}, {len(nota['itens'])} itens, total **{brl(nota['total'])}**")
    if nota.get("desconto"):
        st.caption(f"Desconto na nota: {brl(nota['desconto'])}")

    df = editor_revisao(st.session_state.rev_nota, key=f"ed_{nota.get('chave')}")
    c1, c2 = st.columns(2)
    if c1.button("💾 Salvar compra", type="primary", use_container_width=True):
        compra = {
            "chave": nota.get("chave"), "mercado": nota["mercado"], "cnpj": nota.get("cnpj"),
            "data": nota.get("data") or date.today().isoformat(), "hora": nota.get("hora"),
            "total": round(float(nota["total"]), 2), "origem": "nfce",
            "registrado_por": st.session_state.usuario, "url": nota.get("url"),
        }
        try:
            db.salvar_compra(compra, itens_do_editor(df))
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")
            return
        st.session_state.pop("nota", None)
        st.session_state.pop("rev_nota", None)
        st.success("Compra salva.")
    if c2.button("Descartar", use_container_width=True):
        st.session_state.pop("nota", None)
        st.session_state.pop("rev_nota", None)
        st.rerun()


def pagina_manual():
    st.subheader("Lançamento manual")
    mercados = db.carregar_mercados()
    escolha = st.selectbox("Onde comprou?", ["Novo local..."] + mercados)
    local = st.text_input("Nome do local", placeholder="Feira, sacolão, açougue...") \
        if escolha == "Novo local..." else escolha
    dia = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
    obs = st.text_input("Observação (opcional)")
    modo = st.radio("Como lançar?", ["Com itens", "Só o valor total"], horizontal=True)

    def cabecalho(total):
        return {"chave": None, "mercado": local.strip(), "data": dia.isoformat(),
                "total": round(float(total), 2), "origem": "manual",
                "registrado_por": st.session_state.usuario, "observacao": obs or None}

    if modo == "Só o valor total":
        valor = st.number_input("Valor (R$)", min_value=0.0, step=1.0, format="%.2f")
        categoria = st.selectbox("Categoria", db.carregar_categorias())
        if st.button("💾 Salvar", type="primary", disabled=not (local and valor > 0)):
            db.salvar_compra(cabecalho(valor), [{
                "descricao": f"Compra sem itens ({categoria})",
                "produto": f"Compra sem itens - {categoria}", "categoria": categoria,
                "quantidade": 1, "valor_unitario": valor, "valor_total": valor}])
            st.success("Lançamento salvo.")
        return

    base = pd.DataFrame({"descricao": pd.Series(dtype="str"),
                         "quantidade": pd.Series(dtype="float"),
                         "valor_total": pd.Series(dtype="float")})
    tabela = st.data_editor(
        base, key="manual_itens", num_rows="dynamic", hide_index=True, use_container_width=True,
        column_config={
            "descricao": st.column_config.TextColumn("Item", required=True),
            "quantidade": st.column_config.NumberColumn("Qtd", default=1.0, min_value=0.0),
            "valor_total": st.column_config.NumberColumn("Valor total", format=MOEDA, min_value=0.0),
        })
    tabela = tabela.fillna({"descricao": "", "quantidade": 1.0, "valor_total": 0.0})
    validos = tabela[(tabela.descricao.str.strip() != "") & (tabela.valor_total > 0)]
    st.caption(f"Total: {brl(validos.valor_total.sum())}")

    if st.button("Organizar itens", disabled=validos.empty or not local):
        itens = [{"descricao": r.descricao.strip(), "quantidade": r.quantidade or 1,
                  "valor_total": r.valor_total, "valor_unitario": r.valor_total / (r.quantidade or 1),
                  "unidade": ""} for r in validos.itertuples()]
        with st.spinner("Organizando os itens..."):
            st.session_state.rev_manual = montar_revisao(itens)

    if "rev_manual" in st.session_state:
        df = editor_revisao(st.session_state.rev_manual, key="ed_manual")
        if st.button("💾 Salvar compra", type="primary"):
            db.salvar_compra(cabecalho(df.valor_total.sum()), itens_do_editor(df))
            for k in ("rev_manual", "manual_itens"):
                st.session_state.pop(k, None)
            st.success("Compra salva.")


def pagina_analises():
    compras, itens = db.df_compras(), db.df_itens()
    if compras.empty:
        st.info("Nenhuma compra registrada ainda. Comece lendo um cupom.")
        return

    hoje = date.today()
    ini_padrao = (pd.Timestamp(hoje) - pd.DateOffset(months=11)).replace(day=1).date()
    c1, c2 = st.columns(2)
    ini = c1.date_input("De", ini_padrao, format="DD/MM/YYYY")
    fim = c2.date_input("Até", hoje, format="DD/MM/YYYY")
    compras["registrado_por"] = compras["registrado_por"].fillna("-")
    pessoas = sorted(compras.registrado_por.unique())
    quem = st.multiselect("Registrado por", pessoas, default=pessoas) if len(pessoas) > 1 else pessoas

    cp = compras[(compras.data >= pd.Timestamp(ini)) & (compras.data <= pd.Timestamp(fim))
                 & compras.registrado_por.isin(quem)].copy()
    if cp.empty:
        st.info("Nenhuma compra nesse período.")
        return
    it = itens[itens.compra_id.isin(cp.id)].copy()
    cp["mes"] = cp.data.dt.strftime("%Y-%m")
    it["mes"] = it.data.dt.strftime("%Y-%m")
    n_meses = max(cp.mes.nunique(), 1)
    total = cp.total.sum()

    a, b = st.columns(2)
    a.metric("Gasto no período", brl(total))
    b.metric("Média por mês", brl(total / n_meses))
    a, b = st.columns(2)
    a.metric("Compras", len(cp))
    b.metric("Ticket médio", brl(cp.total.mean()))

    t_mes, t_cat, t_merc, t_prod, t_preco, t_lista = st.tabs(
        ["Mês", "Categorias", "Mercados", "Produtos", "Preços", "Lista do mês"])

    with t_mes:
        mensal = cp.groupby("mes", as_index=False).total.sum()
        st.altair_chart(alt.Chart(mensal).mark_bar().encode(
            x=alt.X("mes:N", title=None), y=alt.Y("total:Q", title="R$"),
            tooltip=["mes", alt.Tooltip("total", format=",.2f")]), use_container_width=True)
        if not it.empty:
            st.markdown("**Categoria por mês**")
            piv = it.pivot_table(index="categoria", columns="mes", values="valor_total",
                                 aggfunc="sum", fill_value=0)
            piv["Média"] = piv.mean(axis=1)
            st.dataframe(piv.sort_values("Média", ascending=False).round(2), use_container_width=True)

    with t_cat:
        g = (it.groupby("categoria", as_index=False).valor_total.sum()
             .sort_values("valor_total", ascending=False))
        g["pct"] = g.valor_total / g.valor_total.sum() * 100
        g["media_mes"] = g.valor_total / n_meses
        st.altair_chart(barras_h(g, "valor_total", "categoria"), use_container_width=True)
        st.dataframe(g, hide_index=True, use_container_width=True, column_config={
            "categoria": "Categoria",
            "valor_total": st.column_config.NumberColumn("Gasto", format=MOEDA),
            "pct": st.column_config.NumberColumn("% do total", format="%.1f%%"),
            "media_mes": st.column_config.NumberColumn("Média/mês", format=MOEDA)})
        st.caption("Soma dos itens. Descontos aplicados no total da nota podem gerar pequena diferença.")

    with t_merc:
        m = (cp.groupby("mercado").agg(gasto=("total", "sum"), compras=("id", "count"),
                                        ticket=("total", "mean"), ultima=("data", "max"))
             .reset_index().sort_values("gasto", ascending=False))
        st.altair_chart(barras_h(m, "gasto", "mercado"), use_container_width=True)
        st.dataframe(m, hide_index=True, use_container_width=True, column_config={
            "mercado": "Mercado",
            "gasto": st.column_config.NumberColumn("Gasto", format=MOEDA),
            "compras": "Compras",
            "ticket": st.column_config.NumberColumn("Ticket médio", format=MOEDA),
            "ultima": st.column_config.DateColumn("Última", format="DD/MM/YYYY")})

    with t_prod:
        p = (it.groupby(["produto", "categoria"])
             .agg(gasto=("valor_total", "sum"), qtd=("quantidade", "sum"),
                  vezes=("compra_id", "nunique"), meses=("mes", "nunique"), ultima=("data", "max"))
             .reset_index().sort_values("gasto", ascending=False))
        p["preco_medio"] = p.gasto / p.qtd.where(p.qtd > 0)
        busca = st.text_input("Buscar produto")
        if busca:
            p = p[p.produto.str.contains(busca, case=False, na=False)]
        st.dataframe(p, hide_index=True, use_container_width=True, column_config={
            "produto": "Produto", "categoria": "Categoria",
            "gasto": st.column_config.NumberColumn("Gasto", format=MOEDA),
            "qtd": st.column_config.NumberColumn("Qtd", format="%.2f"),
            "vezes": "Compras", "meses": "Meses",
            "ultima": st.column_config.DateColumn("Última", format="DD/MM/YYYY"),
            "preco_medio": st.column_config.NumberColumn("Preço médio", format=MOEDA)})

    with t_preco:
        opcoes = it.groupby("produto").size().sort_values(ascending=False).index.tolist()
        if not opcoes:
            st.info("Sem itens no período.")
        else:
            prod = st.selectbox("Produto", opcoes)
            h = it[it.produto == prod].copy()
            h["preco"] = h.valor_unitario.fillna(h.valor_total / h.quantidade)
            st.altair_chart(alt.Chart(h).mark_line(point=True).encode(
                x=alt.X("data:T", title=None), y=alt.Y("preco:Q", title="Preço unitário (R$)"),
                color=alt.Color("mercado:N", legend=alt.Legend(orient="bottom", title=None)),
                tooltip=["data:T", "mercado", "descricao_original", alt.Tooltip("preco", format=",.2f")]
            ), use_container_width=True)
            h = h.sort_values("data")
            por_merc = h.groupby("mercado").agg(
                menor=("preco", "min"), medio=("preco", "mean"), ultimo=("preco", "last"),
                vezes=("preco", "count"), quando=("data", "max")).reset_index().sort_values("medio")
            st.dataframe(por_merc, hide_index=True, use_container_width=True, column_config={
                "mercado": "Mercado",
                "menor": st.column_config.NumberColumn("Menor", format=MOEDA),
                "medio": st.column_config.NumberColumn("Médio", format=MOEDA),
                "ultimo": st.column_config.NumberColumn("Último", format=MOEDA),
                "vezes": "Vezes",
                "quando": st.column_config.DateColumn("Última compra", format="DD/MM/YYYY")})

    with t_lista:
        pct = st.slider("Comprado em pelo menos X% dos meses do período", 20, 100, 60, step=10)
        r = (it.groupby(["produto", "categoria"])
             .agg(meses=("mes", "nunique"), qtd=("quantidade", "sum"), gasto=("valor_total", "sum"))
             .reset_index())
        r = r[r.meses >= math.ceil(n_meses * pct / 100)].copy()
        r["qtd_mes"] = r.qtd / r.meses
        r["gasto_mes"] = r.gasto / r.meses
        r = r.sort_values(["categoria", "gasto_mes"], ascending=[True, False])
        st.caption(f"{len(r)} produtos, custo estimado {brl(r.gasto_mes.sum())} por mês")
        st.dataframe(r[["produto", "categoria", "meses", "qtd_mes", "gasto_mes"]], hide_index=True,
                     use_container_width=True, column_config={
                         "produto": "Produto", "categoria": "Categoria", "meses": "Meses",
                         "qtd_mes": st.column_config.NumberColumn("Qtd/mês", format="%.1f"),
                         "gasto_mes": st.column_config.NumberColumn("Gasto/mês", format=MOEDA)})
        st.download_button("Baixar lista (CSV)", csv_br(r), "lista_do_mes.csv", "text/csv")


def pagina_historico():
    compras, itens = db.df_compras(), db.df_itens()
    if compras.empty:
        st.info("Nenhuma compra registrada ainda.")
        return
    compras = compras.sort_values(["data", "id"], ascending=False)
    meses = compras.data.dt.strftime("%m/%Y").drop_duplicates().tolist()
    mes = st.selectbox("Mês", meses)
    sel = compras[compras.data.dt.strftime("%m/%Y") == mes]
    st.caption(f"{len(sel)} compras, {brl(sel.total.sum())}")

    for c in sel.itertuples():
        icone = "🧾" if c.origem == "nfce" else "✍️"
        with st.expander(f"{icone} {c.data:%d/%m} {c.mercado}  {brl(c.total)}"):
            info = [f"Registrado por {c.registrado_por or '-'}"]
            if c.observacao:
                info.append(c.observacao)
            st.caption(". ".join(info))
            st.dataframe(itens[itens.compra_id == c.id][
                ["descricao_original", "produto", "categoria", "quantidade", "valor_total"]],
                hide_index=True, use_container_width=True, column_config={
                    "descricao_original": "Na nota", "produto": "Produto", "categoria": "Categoria",
                    "quantidade": "Qtd",
                    "valor_total": st.column_config.NumberColumn("Valor", format=MOEDA)})
            if st.checkbox("Quero excluir esta compra", key=f"chk_{c.id}"):
                if st.button("Excluir compra", key=f"del_{c.id}"):
                    db.excluir_compra(c.id)
                    st.rerun()

    st.divider()
    st.download_button("Baixar todos os itens (CSV)", csv_br(itens), "itens.csv", "text/csv")


def pagina_produtos():
    produtos = db.carregar_produtos()
    if not produtos:
        st.info("Os produtos aparecem aqui depois da primeira compra salva.")
        return
    categorias = db.carregar_categorias()

    if msg := st.session_state.pop("msg_padronizar", None):
        st.success(msg)

    st.subheader("Padronizar nomes")
    st.caption("Deixa os nomes genéricos (ex.: 'Vinho tinto casillero 750ml' vira 'Vinho') e "
               "junta os produtos que ficarem com o mesmo nome. Você revisa antes de aplicar.")
    if st.button("Gerar sugestões"):
        with st.spinner("Analisando produtos..."):
            plano = cat.padronizar(produtos, categorias, api_key=st.secrets.get("ANTHROPIC_API_KEY"))
        linhas = [{"id": pid, "atual": produtos[pid]["nome"], "novo": n, "categoria": c, "aplicar": True}
                  for pid, (n, c) in plano.items()
                  if (n, c) != (produtos[pid]["nome"], produtos[pid]["categoria"])]
        st.session_state.plano = pd.DataFrame(
            linhas, columns=["id", "atual", "novo", "categoria", "aplicar"]).sort_values("novo")

    if "plano" in st.session_state:
        plano = st.session_state.plano
        if plano.empty:
            st.success("Tudo já está padronizado.")
            st.session_state.pop("plano")
        else:
            juntam = plano.groupby("novo").size()
            st.caption(f"{len(plano)} produtos vão mudar. "
                       f"{int((juntam > 1).sum())} nomes vão juntar mais de um produto.")
            ed = st.data_editor(plano, key="ed_plano", hide_index=True, use_container_width=True,
                                disabled=["id", "atual"], column_config={
                                    "id": None, "atual": "Hoje",
                                    "novo": st.column_config.TextColumn("Vai ficar", required=True),
                                    "categoria": st.column_config.SelectboxColumn(
                                        "Categoria", options=categorias, required=True),
                                    "aplicar": st.column_config.CheckboxColumn("Aplicar")})
            c1, c2 = st.columns(2)
            if c1.button("Aplicar", type="primary", use_container_width=True):
                sel = ed[ed.aplicar]
                with st.spinner("Aplicando..."):
                    falhas = db.aplicar_padronizacao(
                        [(r.id, r.novo, r.categoria) for r in sel.itertuples()])
                st.session_state.msg_padronizar = (
                    f"{len(sel)} produtos padronizados." +
                    (f" {falhas} nomes deram conflito; rode de novo para concluir." if falhas else ""))
                st.session_state.pop("plano", None)
                st.session_state.pop("ed_plano", None)
                st.rerun()
            if c2.button("Cancelar", use_container_width=True):
                st.session_state.pop("plano", None)
                st.session_state.pop("ed_plano", None)
                st.rerun()

    st.divider()
    produtos = db.carregar_produtos()
    itens = db.df_itens()
    uso = itens.groupby("produto_id").size()
    df = pd.DataFrame([{"id": k, "nome": v["nome"], "categoria": v["categoria"]}
                       for k, v in produtos.items()]).sort_values("nome")
    df["itens"] = df.id.map(uso).fillna(0).astype(int)

    st.subheader("Produtos")
    busca = st.text_input("Buscar")
    vis = df[df.nome.str.contains(busca, case=False, na=False)] if busca else df
    editado = st.data_editor(vis, key="ed_prod", hide_index=True, use_container_width=True,
                             disabled=["id", "itens"], column_config={
                                 "id": None, "nome": st.column_config.TextColumn("Nome padrão", required=True),
                                 "categoria": st.column_config.SelectboxColumn(
                                     "Categoria", options=categorias, required=True),
                                 "itens": "Itens"})
    if st.button("Salvar alterações"):
        orig = vis.set_index("id")
        erros = 0
        for r in editado.itertuples():
            if (r.nome, r.categoria) != (orig.at[r.id, "nome"], orig.at[r.id, "categoria"]):
                try:
                    db.atualizar_produto(r.id, r.nome, r.categoria)
                except Exception:
                    erros += 1
        db.limpar_cache()
        if erros:
            st.warning(f"{erros} alteração(ões) não salvas: já existe produto com esse nome. "
                       "Use 'Juntar produtos' abaixo.")
        else:
            st.success("Alterações salvas.")

    st.subheader("Juntar produtos iguais")
    nomes = df.set_index("nome").id.to_dict()
    origem = st.selectbox("Este produto...", list(nomes), index=None, placeholder="Escolha")
    destino = st.selectbox("...passa a fazer parte deste", [n for n in nomes if n != origem],
                           index=None, placeholder="Escolha")
    if st.button("Juntar", disabled=not (origem and destino)):
        db.mesclar_produtos(nomes[origem], nomes[destino], origem)
        st.success(f"'{origem}' agora faz parte de '{destino}'.")
        st.rerun()

    with st.expander("Corrigir uma descrição ligada ao produto errado"):
        apelidos = db.carregar_apelidos()
        prod = st.selectbox("Produto", list(nomes), index=None, placeholder="Escolha", key="ap_prod")
        if prod:
            descs = [k for k, v in apelidos.items() if v == nomes[prod]]
            if not descs:
                st.caption("Nenhuma descrição ligada.")
            else:
                desc = st.selectbox("Descrição do cupom", descs)
                novo = st.selectbox("Mover para", [n for n in nomes if n != prod], key="ap_novo")
                if st.button("Mover"):
                    db.mover_descricao(desc, nomes[novo])
                    st.success("Descrição movida.")
                    st.rerun()

    st.subheader("Categorias")
    st.caption(", ".join(categorias))
    nova = st.text_input("Nova categoria")
    if st.button("Adicionar categoria", disabled=not nova.strip()):
        db.adicionar_categoria(nova)
        st.rerun()


# ================= Perfil =================
def pagina_perfil():
    u = usuario_atual()
    st.subheader("Seu ícone")
    seletor_aparencia(u)

    st.divider()
    tem_senha = bool(u.get("senha_hash"))
    st.subheader("Senha pessoal" + ("" if tem_senha else " (opcional)"))
    st.caption("Sem senha pessoal, o seu perfil abre com a senha do app. "
               "Em qualquer caso, você só digita uma vez por aparelho.")
    with st.form("form_troca_senha", clear_on_submit=True):
        atual = st.text_input("Senha atual", type="password") if tem_senha else ""
        s1 = st.text_input("Nova senha", type="password")
        s2 = st.text_input("Repita a nova senha", type="password")
        ok = st.form_submit_button("Salvar senha")
    if ok:
        if tem_senha and not perfis.verificar(atual, u["senha_hash"]):
            st.error("Senha atual incorreta.")
        elif len(s1) < 4:
            st.error("Use pelo menos 4 caracteres.")
        elif s1 != s2:
            st.error("As senhas não são iguais.")
        else:
            db.salvar_senha(u["nome"], perfis.gerar_hash(s1))
            st.success("Senha salva.")

    st.divider()
    if st.button("Sair deste aparelho", use_container_width=True):
        db.apagar_sessao(st.query_params.get("t"))
        st.query_params.clear()
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


# ================= Navegação =================
PAGINAS = {
    "📷 Nota": pagina_nota,
    "✍️ Manual": pagina_manual,
    "📊 Análises": pagina_analises,
    "🧾 Histórico": pagina_historico,
    "🏷️ Produtos": pagina_produtos,
    "👤 Perfil": pagina_perfil,
}
eu = usuario_atual()
if eu:
    st.markdown(perfis.avatar_html(eu["icone"], eu["cor"], 30, inline=True) + f"<b>{eu['nome']}</b>",
                unsafe_allow_html=True)
escolha = st.radio("Menu", list(PAGINAS), horizontal=True, label_visibility="collapsed", key="menu")
PAGINAS[escolha]()
