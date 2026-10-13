"""Normalização de descrições, junção de itens iguais e sugestão de produto e categoria."""
import json
import re
import unicodedata

from rapidfuzz import fuzz, process

LIMIAR_SIMILARIDADE = 90  # 0 a 100. Mais alto = só junta descrições muito parecidas.
MODELO_CLAUDE = "claude-haiku-5-5"

# Palavra-chave do cupom (maiúscula, sem acento) -> nome genérico do produto.
# Quando várias batem, vence a palavra-chave mais longa.
REGRAS = {
    "Hortifruti": {
        "BANANA": "Banana", "AVOCADO": "Abacate", "BAN": "Banana", "MACA": "Maçã", "TOMATE": "Tomate", "ALFACE": "Alface",
        "BATATA": "Batata", "BATATA DOCE": "Batata-doce", "CEBOLA": "Cebola", "ALHO": "Alho",
        "LIMAO": "Limão", "LARANJA": "Laranja", "MAMAO": "Mamão", "PAPAYA": "Mamão",
        "CENOURA": "Cenoura", "ABOBRINHA": "Abobrinha", "ABOBORA": "Abóbora", "BROCOLIS": "Brócolis",
        "COUVE FLOR": "Couve-flor", "MELANCIA": "Melancia", "MELAO": "Melão", "UVA": "Uva",
        "MORANGO": "Morango", "ABACATE": "Abacate", "PEPINO": "Pepino", "PIMENTAO": "Pimentão",
        "REPOLHO": "Repolho", "COUVE": "Couve", "RUCULA": "Rúcula", "AGRIAO": "Agrião",
        "ESPINAFRE": "Espinafre", "MANGA": "Manga", "ABACAXI": "Abacaxi", "CHEIRO VERDE": "Cheiro-verde",
        "SALSINHA": "Cheiro-verde", "CEBOLINHA": "Cheiro-verde", "COENTRO": "Coentro",
        "MANDIOCA": "Mandioca", "MANDIOQUINHA": "Mandioquinha", "BETERRABA": "Beterraba",
        "CHUCHU": "Chuchu", "KIWI": "Kiwi", "PERA": "Pera", "MARACUJA": "Maracujá", "GOIABA": "Goiaba",
        "TANGERINA": "Tangerina", "MEXERICA": "Tangerina", "PONKAN": "Tangerina", "GENGIBRE": "Gengibre",
        "BERINJELA": "Berinjela", "VAGEM": "Vagem", "QUIABO": "Quiabo", "ESPIGA": "Milho verde", "MILHO ESPIGA": "Milho verde", "SALADA": "Salada", "MIX FOLHAS": "Salada",
        "COGUMELO": "Cogumelo", "CHAMPIGNON": "Cogumelo", "MIRTILO": "Mirtilo", "AMEIXA": "Ameixa",
        "PESSEGO": "Pêssego", "COCO": "Coco", "HORTIFRUTI": "Hortifruti",
    },
    "Carnes e peixes": {
        "CARNE": "Carne bovina", "BOV": "Carne bovina", "CARNE MOIDA": "Carne moída", "MOIDA": "Carne moída",
        "FRANGO": "Frango", "FGO": "Frango", "PEITO": "Peito de frango", "PEITO FRANGO": "Peito de frango",
        "PEITO DE FRANGO": "Peito de frango", "FILE PEITO": "Peito de frango", "FILE FRANGO": "Peito de frango", "FILE DE FRANGO": "Peito de frango", "COXA": "Coxa de frango",
        "SOBRECOXA": "Sobrecoxa", "ASA": "Asa de frango", "COXINHA DA ASA": "Asa de frango",
        "PATINHO": "Patinho", "ALCATRA": "Alcatra", "PICANHA": "Picanha", "CONTRA FILE": "Contrafilé",
        "FRALDINHA": "Fraldinha", "COSTELA": "Costela", "LINGUICA": "Linguiça", "LING": "Linguiça",
        "TILAPIA": "Tilápia", "SALMAO": "Salmão", "PEIXE": "Peixe", "CAMARAO": "Camarão", "ACEM": "Acém",
        "BACON": "Bacon", "COXAO": "Coxão", "MAMINHA": "Maminha", "LOMBO": "Lombo suíno",
        "PERNIL": "Pernil", "CUPIM": "Cupim", "MIGNON": "Filé mignon", "BISTECA": "Bisteca",
        "MUSCULO": "Músculo", "CORACAO": "Coração de frango", "FIGADO": "Fígado",
        "BACALHAU": "Bacalhau", "MERLUZA": "Merluza", "SUINO": "Carne suína", "SUINA": "Carne suína",
        "FILE": "Filé", "CARNE SECA": "Carne-seca", "CHARQUE": "Carne-seca",
    },
    "Frios e laticínios": {
        "LEITE": "Leite", "LEITE EM PO": "Leite em pó", "QUEIJO": "Queijo", "QJO": "Queijo",
        "MUSSARELA": "Mussarela", "MUCARELA": "Mussarela", "MUSS": "Mussarela",
        "QUEIJO PRATO": "Queijo prato", "PARMESAO": "Parmesão", "PRESUNTO": "Presunto", "PRES": "Presunto",
        "APRESUNTADO": "Apresuntado", "IOGURTE": "Iogurte", "IOG": "Iogurte", "REQUEIJAO": "Requeijão",
        "REQ": "Requeijão", "MANTEIGA": "Manteiga", "MARGARINA": "Margarina",
        "CREME DE LEITE": "Creme de leite", "CR LEITE": "Creme de leite", "PEITO PERU": "Peito de peru",
        "PEITO DE PERU": "Peito de peru", "SALAME": "Salame", "MORTADELA": "Mortadela", "OVO": "Ovos",
        "OVOS": "Ovos", "RICOTA": "Ricota", "COTTAGE": "Cottage", "BEBIDA LACTEA": "Bebida láctea",
        "LEITE FERMENTADO": "Leite fermentado", "YAKULT": "Leite fermentado",
        "PETIT SUISSE": "Petit suisse", "DANONINHO": "Petit suisse", "CREAM CHEESE": "Cream cheese", "CRCHEESE": "Cream cheese", "CR CHEESE": "Cream cheese", "MANT": "Manteiga", "IOGLIQ": "Iogurte", "SALSADIA": "Salame",
        "PROVOLONE": "Provolone", "GORGONZOLA": "Gorgonzola", "COPA": "Copa", "SALSICHA": "Salsicha", "CHANTILLY": "Chantilly",
    },
    "Padaria": {
        "PAO": "Pão", "PAOZINHO": "Pão", "PAO FRANCES": "Pão francês", "FRANCES": "Pão francês", "PAO FORMA": "Pão de forma",
        "PAO DE FORMA": "Pão de forma", "BISNAGUINHA": "Bisnaguinha", "BOLO": "Bolo", "TORRADA": "Torrada",
        "CROISSANT": "Croissant", "SONHO": "Sonho", "PAO DE QUEIJO": "Pão de queijo",
        "PAO QUEIJO": "Pão de queijo", "PANETONE": "Panetone", "CHOCOTONE": "Panetone", "ROSCA": "Rosca",
        "SALGADO": "Salgado", "BROA": "Broa", "WRAP": "Wrap", "TORTILHA": "Wrap",
        "PAO SIRIO": "Pão sírio", "PAO ARABE": "Pão sírio",
    },
    "Mercearia": {
        "ARROZ": "Arroz", "FEIJAO": "Feijão", "MACARRAO": "Macarrão", "ESPAGUETE": "Macarrão",
        "PENNE": "Macarrão", "MIOJO": "Macarrão instantâneo", "LAMEN": "Macarrão instantâneo",
        "ACUCAR": "Açúcar", "ACUC": "Açúcar", "SAL": "Sal", "OLEO": "Óleo", "AZEITE": "Azeite",
        "CAFE": "Café", "CAPSULA": "Café em cápsula", "FARINHA": "Farinha", "FARINHA DE TRIGO": "Farinha de trigo",
        "MOLHO": "Molho", "MOLHO TOMATE": "Molho de tomate", "MOLHO DE TOMATE": "Molho de tomate",
        "PASSATA": "Molho de tomate", "EXTRATO": "Extrato de tomate", "ATUM": "Atum", "SARDINHA": "Sardinha",
        "MILHO": "Milho", "MILHO VERDE": "Milho", "BATATA PALHA": "Batata palha", "ERVILHA": "Ervilha", "AVEIA": "Aveia", "GRANOLA": "Granola", "TEMPERO": "Tempero",
        "VINAGRE": "Vinagre", "MAIONESE": "Maionese", "KETCHUP": "Ketchup", "CATCHUP": "Ketchup",
        "MOSTARDA": "Mostarda", "MOSTAR": "Mostarda", "POMODORI": "Tomate pelado", "PELATI": "Tomate pelado", "TOMATE PELADO": "Tomate pelado", "FAROFA": "Farofa", "FUBA": "Fubá", "LENTILHA": "Lentilha",
        "GRAO DE BICO": "Grão-de-bico", "ACHOCOLATADO": "Achocolatado", "NESCAU": "Achocolatado",
        "TODDY": "Achocolatado", "CEREAL": "Cereal", "SUCRILHOS": "Cereal", "MEL": "Mel",
        "TAPIOCA": "Tapioca", "PALMITO": "Palmito", "AZEITONA": "Azeitona", "CALDO": "Caldo",
        "FERMENTO": "Fermento", "AMIDO": "Amido de milho", "MAIZENA": "Amido de milho",
        "PIMENTA": "Pimenta", "OREGANO": "Orégano", "COLORAU": "Colorau", "CANELA": "Canela",
        "LEITE DE COCO": "Leite de coco", "COCO RALADO": "Coco ralado", "SOPA": "Sopa", "SHOYU": "Shoyu",
        "GELEIA": "Geleia", "PASTA AMENDOIM": "Pasta de amendoim", "CHIA": "Chia", "LINHACA": "Linhaça",
        "QUINOA": "Quinoa", "WHEY": "Whey protein",
    },
    "Bebidas": {
        "AGUA": "Água", "AGUA MINERAL": "Água", "AGUA C GAS": "Água com gás", "AGUA COM GAS": "Água com gás",
        "REFRIG": "Refrigerante", "REFRI": "Refrigerante", "REFRIGERANTE": "Refrigerante",
        "COCA": "Refrigerante", "COCA COLA": "Refrigerante", "GUARANA": "Refrigerante",
        "PEPSI": "Refrigerante", "FANTA": "Refrigerante", "SPRITE": "Refrigerante", "SUCO": "Suco",
        "NECTAR": "Suco", "CHA": "Chá", "MATE": "Chá", "ISOTONICO": "Isotônico", "GATORADE": "Isotônico",
        "ENERGETICO": "Energético", "RED BULL": "Energético", "MONSTER": "Energético",
        "AGUA DE COCO": "Água de coco", "KOMBUCHA": "Kombucha", "TONICA": "Água tônica",
    },
    "Bebidas alcoólicas": {
        "CERVEJA": "Cerveja", "CERV": "Cerveja", "VH": "Vinho", "CHOPP": "Chope", "CHOPE": "Chope", "VINHO": "Vinho",
        "ESPUMANTE": "Espumante", "PROSECCO": "Espumante", "CHAMPAGNE": "Espumante", "VODKA": "Vodka",
        "WHISKY": "Whisky", "GIN": "Gin", "CACHACA": "Cachaça", "RUM": "Rum", "TEQUILA": "Tequila",
        "LICOR": "Licor", "SAKE": "Saquê", "APEROL": "Aperol", "CAMPARI": "Campari",
        "HEINEKEN": "Cerveja", "BRAHMA": "Cerveja", "SKOL": "Cerveja", "AMSTEL": "Cerveja",
        "STELLA": "Cerveja", "BUDWEISER": "Cerveja", "CORONA": "Cerveja", "SPATEN": "Cerveja",
        "ITAIPAVA": "Cerveja", "EISENBAHN": "Cerveja", "PATAGONIA": "Cerveja", "BADEN": "Cerveja",
    },
    "Congelados": {
        "CONG": "Congelado", "CONGELADO": "Congelado", "LASANHA": "Lasanha", "PIZZA": "Pizza",
        "SORVETE": "Sorvete", "PICOLE": "Picolé", "HAMBURGUER": "Hambúrguer", "NUGGETS": "Nuggets",
        "EMPANADO": "Empanado", "BATATA PALITO": "Batata frita congelada",
        "BATATA PRE FRITA": "Batata frita congelada", "POLPA": "Polpa de fruta", "ACAI": "Açaí",
        "PAO DE QUEIJO CONG": "Pão de queijo", "STEAK": "Steak", "LEGUMES CONG": "Legumes congelados",
        "SELETA": "Legumes congelados", "GELO": "Gelo",
    },
    "Doces e snacks": {
        "CHOCOLATE": "Chocolate", "CHOC": "Chocolate", "KITKAT": "Chocolate", "KIT KAT": "Chocolate",
        "BOMBOM": "Bombom", "BISCOITO": "Biscoito", "BISC": "Biscoito", "BOLACHA": "Biscoito", "PIRAQUE": "Biscoito", "AGUA E SAL": "Biscoito", "CREAM CRACKER": "Biscoito", "CROSTATA": "Crostata",
        "COOKIE": "Biscoito", "WAFER": "Biscoito", "BALA": "Bala", "GOMA": "Bala", "CHICLETE": "Chiclete",
        "SALGADINHO": "Salgadinho", "DORITOS": "Salgadinho", "BATATA CHIPS": "Batata chips",
        "CHIPS": "Batata chips", "RUFFLES": "Batata chips", "AMENDOIM": "Amendoim", "PACOCA": "Paçoca", "COCADA": "Cocada", "MANTECAL": "Doce",
        "CASTANHA": "Castanha", "MIX NUTS": "Castanha", "UVA PASSA": "Uva-passa", "DOCE": "Doce",
        "DOCE DE LEITE": "Doce de leite", "PIPOCA": "Pipoca", "BARRA CEREAL": "Barra de cereal",
        "BARRA DE CEREAL": "Barra de cereal", "BARRA PROTEINA": "Barra de proteína",
        "LEITE CONDENSADO": "Leite condensado", "LT COND": "Leite condensado", "LEITE COND": "Leite condensado", "CONDMOCA": "Leite condensado", "MOCA": "Leite condensado",
        "NUTELLA": "Creme de avelã", "CREME AVELA": "Creme de avelã", "GELATINA": "Gelatina",
        "PUDIM": "Pudim", "SOBREMESA": "Sobremesa", "MOUSSE": "Sobremesa",
    },
    "Limpeza": {
        "DETERGENTE": "Detergente", "DETERG": "Detergente", "DET": "Detergente", "LAVA LOUCAS": "Detergente",
        "SABAO": "Sabão", "OMO": "Sabão", "SABAO PO": "Sabão em pó", "SABAO EM PO": "Sabão em pó",
        "SABAO LIQ": "Sabão líquido", "LAVA ROUPAS": "Sabão líquido", "AMACIANTE": "Amaciante",
        "AMAC": "Amaciante", "DESINFETANTE": "Desinfetante", "DESINF": "Desinfetante",
        "AGUA SANITARIA": "Água sanitária", "QBOA": "Água sanitária", "ALVEJANTE": "Alvejante",
        "ESPONJA": "Esponja", "LIMPADOR": "Limpador", "LIMPA PISO": "Limpador", "MULTIUSO": "Multiuso",
        "SACO LIXO": "Saco de lixo", "SACO DE LIXO": "Saco de lixo", "SACO P LIXO": "Saco de lixo",
        "LUSTRA MOVEIS": "Lustra-móveis", "PANO": "Pano de limpeza", "PERFEX": "Pano de limpeza",
        "LIMPA VIDRO": "Limpa-vidros", "TIRA MANCHAS": "Tira-manchas", "VANISH": "Tira-manchas",
        "INSETICIDA": "Inseticida", "REPELENTE": "Repelente", "ALCOOL": "Álcool",
        "ALCOOL GEL": "Álcool em gel", "PALHA DE ACO": "Palha de aço", "BOMBRIL": "Palha de aço",
        "CERA": "Cera", "ODORIZADOR": "Odorizador", "PEDRA SANITARIA": "Pedra sanitária", "LUVA": "Luva",
        "VASSOURA": "Vassoura", "RODO": "Rodo",
    },
    "Higiene e beleza": {
        "SHAMPOO": "Shampoo", "SHAMP": "Shampoo", "CONDICIONADOR": "Condicionador", "COND": "Condicionador",
        "SABONETE": "Sabonete", "SAB": "Sabonete", "SAB LIQ": "Sabonete líquido",
        "CREME DENTAL": "Creme dental", "CR DENTAL": "Creme dental", "COLGATE": "Creme dental",
        "ESCOVA DENTAL": "Escova de dentes", "ESC DENTAL": "Escova de dentes",
        "DESODORANTE": "Desodorante", "DESOD": "Desodorante", "PAPEL HIGIENICO": "Papel higiênico",
        "PAPEL HIG": "Papel higiênico", "PAP HIG": "Papel higiênico", "FIO DENTAL": "Fio dental",
        "ABSORVENTE": "Absorvente", "PROTETOR DIARIO": "Protetor diário", "BARBEAR": "Aparelho de barbear",
        "LAMINA": "Lâmina de barbear", "HIDRATANTE": "Hidratante", "COTONETE": "Cotonete",
        "HASTES": "Cotonete", "ENXAGUANTE": "Enxaguante bucal", "LISTERINE": "Enxaguante bucal",
        "PROTETOR SOLAR": "Protetor solar", "FPS": "Protetor solar", "CREME PENTEAR": "Creme de pentear",
        "LENCO UMEDECIDO": "Lenço umedecido", "FRALDA": "Fralda", "ALGODAO": "Algodão",
        "ESMALTE": "Esmalte", "ACETONA": "Removedor de esmalte",
    },
    "Pet": {
        "RACAO": "Ração", "PEDIGREE": "Ração", "WHISKAS": "Ração", "GOLDEN": "Ração", "PREMIER": "Ração",
        "AREIA": "Areia sanitária", "AREIA GATO": "Areia sanitária", "AREIA SANITARIA": "Areia sanitária",
        "PETISCO": "Petisco pet", "SACHE": "Sachê pet", "TAPETE HIGIENICO": "Tapete higiênico",
    },
    "Utilidades": {
        "PILHA": "Pilha", "LAMPADA": "Lâmpada", "PAPEL ALUMINIO": "Papel-alumínio",
        "PAPEL ALUM": "Papel-alumínio", "FILME PVC": "Filme plástico", "PAPEL FILME": "Filme plástico",
        "GUARDANAPO": "Guardanapo", "PAPEL TOALHA": "Papel-toalha", "TOALHA PAPEL": "Papel-toalha", "FILTRO": "Filtro de café", "FILTRO CAFE": "Filtro de café", "FILTRO PAPEL": "Filtro de café", "PAP TOALHA": "Papel-toalha",
        "PAPEL MANTEIGA": "Papel-manteiga", "SACO FREEZER": "Saco para freezer", "CARVAO": "Carvão",
        "FOSFORO": "Fósforo", "ISQUEIRO": "Isqueiro", "ACENDEDOR": "Acendedor", "VELA": "Vela",
        "SACOLA": "Sacola", "COPO DESC": "Descartáveis", "COPO DESCARTAVEL": "Descartáveis",
        "PRATO DESC": "Descartáveis", "PRATO DESCARTAVEL": "Descartáveis", "PALITO": "Palito",
    },
}

SEM_ITENS = "Compra sem itens"


def normalizar(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode()
    txt = re.sub(r"[^A-Za-z0-9]+", " ", txt.upper())
    return re.sub(r"\s+", " ", txt).strip()


def regra(descricao: str, categorias=None):
    """Devolve (nome_generico, categoria) pela palavra-chave mais longa encontrada, ou None."""
    # "SABOR UVA", "SABOR MORANGO" etc. não definem o produto
    n = re.sub(r" (SABOR|SAB|SB) .*", " ", f" {normalizar(descricao)} ") 
    n = n if n.strip() else f" {normalizar(descricao)} "
    melhor, tam = None, 0
    for cat, mapa in REGRAS.items():
        if categorias and cat not in categorias:
            continue
        for chave, nome in mapa.items():
            if len(chave) > tam and f" {chave} " in n:
                melhor, tam = (nome, cat), len(chave)
    if melhor:
        return melhor
    # Cupom costuma grudar palavras (CERVBADEN, MANTPORTO): tenta como começo de palavra
    for cat, mapa in REGRAS.items():
        if categorias and cat not in categorias:
            continue
        for chave, nome in mapa.items():
            if " " in chave or len(chave) < 4 or len(chave) <= tam:
                continue
            if re.search(rf" {chave}[A-Z]", n):
                melhor, tam = (nome, cat), len(chave)
    return melhor


def categoria_por_regra(descricao, categorias):
    r = regra(descricao, categorias)
    return r[1] if r else "Outros"


def nome_limpo(descricao: str) -> str:
    """Tira tamanhos e números ('750ML', '1KG') e deixa só a primeira letra maiúscula."""
    partes = [p for p in str(descricao).split() if not re.search(r"\d", p)]
    texto = " ".join(partes) or str(descricao)
    return re.sub(r"\s+", " ", texto).strip().capitalize()


def _categoria_por_semelhanca(n, produtos, apelidos):
    """Sem regra: herda a categoria de algo já cadastrado que começa com a mesma palavra."""
    primeira = n.split(" ")[0] if n else ""
    if len(primeira) < 4:
        return None
    for norm, pid in apelidos.items():
        p = produtos.get(pid)
        if p and p["categoria"] != "Outros" and norm.split(" ")[0] == primeira:
            return p["categoria"]
    for p in produtos.values():
        if p["categoria"] != "Outros" and normalizar(p["nome"]).split(" ")[0] == primeira:
            return p["categoria"]
    return None


def sugerir(descricoes, apelidos, produtos, categorias, api_key=None):
    """
    Retorna [{"status", "produto", "categoria"}] na mesma ordem das descrições.
    status: ✅ já conhecido, 🔁 vai juntar com um existente, 🆕 novo
    """
    candidatos = {normalizar(p["nome"]): pid for pid, p in produtos.items()}
    candidatos.update(apelidos)
    chaves = list(candidatos)
    existentes = {p["nome"]: p for p in produtos.values()}
    fallback = "Outros" if "Outros" in categorias else categorias[-1]

    saida, sem_regra = [], []
    for d in descricoes:
        n = normalizar(d)
        p = produtos.get(candidatos.get(n))
        if p:
            saida.append({"status": "✅", "produto": p["nome"], "categoria": p["categoria"]})
            continue
        m = process.extractOne(n, chaves, scorer=fuzz.token_sort_ratio,
                               score_cutoff=LIMIAR_SIMILARIDADE) if chaves else None
        p = produtos.get(candidatos[m[0]]) if m else None
        if p:
            saida.append({"status": "🔁", "produto": p["nome"], "categoria": p["categoria"]})
            continue
        r = regra(d, categorias)
        if r:
            nome, cat = r
            if nome in existentes:
                saida.append({"status": "🔁", "produto": nome, "categoria": existentes[nome]["categoria"]})
            else:
                saida.append({"status": "🆕", "produto": nome, "categoria": cat})
            continue
        cat = _categoria_por_semelhanca(n, produtos, apelidos) or fallback
        saida.append({"status": "🆕", "produto": nome_limpo(d), "categoria": cat})
        sem_regra.append(len(saida) - 1)

    if api_key and sem_regra:
        nomes_base = list(existentes) + [s["produto"] for s in saida if s["status"] == "🆕"]
        try:
            resp = sugerir_com_claude(api_key, [descricoes[i] for i in sem_regra],
                                      sorted(set(nomes_base)), categorias)
            for pos, idx in enumerate(sem_regra):
                s = resp.get(pos) or {}
                nome = (s.get("produto") or "").strip()
                if nome in existentes:
                    saida[idx] = {"status": "🔁", "produto": nome,
                                  "categoria": existentes[nome]["categoria"]}
                    continue
                if nome:
                    saida[idx]["produto"] = nome
                if s.get("categoria") in categorias:
                    saida[idx]["categoria"] = s["categoria"]
        except Exception as e:
            print("Claude indisponível:", e)
    return saida


def padronizar(produtos, categorias, api_key=None):
    """Sugere nome genérico e categoria para produtos já salvos. {pid: (nome, categoria)}"""
    plano, sem_regra = {}, []
    for pid, p in produtos.items():
        if p["nome"].startswith(SEM_ITENS):
            continue
        r = regra(p["nome"], categorias)
        if r:
            plano[pid] = r
        else:
            plano[pid] = (nome_limpo(p["nome"]), p["categoria"])
            sem_regra.append(pid)

    if api_key and sem_regra:
        nomes_base = sorted({v[0] for k, v in plano.items() if k not in sem_regra})
        for i in range(0, len(sem_regra), 150):
            lote = sem_regra[i:i + 150]
            try:
                resp = sugerir_com_claude(api_key, [produtos[pid]["nome"] for pid in lote],
                                          nomes_base, categorias)
            except Exception as e:
                print("Claude indisponível:", e)
                break
            for pos, pid in enumerate(lote):
                s = resp.get(pos) or {}
                nome = (s.get("produto") or "").strip() or plano[pid][0]
                cat = s.get("categoria") if s.get("categoria") in categorias else plano[pid][1]
                plano[pid] = (nome, cat)
                nomes_base.append(nome)
    return plano


def sugerir_com_claude(api_key, descricoes, nomes_existentes, categorias) -> dict:
    import anthropic

    lista = "\n".join(f"{i}: {d}" for i, d in enumerate(descricoes))
    existentes = "\n".join(nomes_existentes[:1500]) or "(nenhum ainda)"
    prompt = f"""Você organiza compras de supermercado de uma família brasileira.
Para cada descrição abreviada de item de cupom fiscal, devolva:

- "produto": o TIPO do produto, genérico, com 1 a 3 palavras, em português.
  Sem marca, sem tamanho, sem peso, sem sabor e sem variação.
  Exemplos: "VH TTO CASILLERO DEL DIABLO 750ML" -> "Vinho"; "LEITE UHT ITALAC INT 1L" -> "Leite";
  "BAN PRATA KG" -> "Banana"; "CERV HEINEKEN LT 350ML" -> "Cerveja"; "DET YPE NEUTRO 500ML" -> "Detergente";
  "PAPEL HIG NEVE FD 12UN" -> "Papel higiênico"; "FILE PEITO FGO SADIA KG" -> "Peito de frango".
  Se algum nome da lista EXISTENTES for o mesmo tipo de produto, use exatamente aquele nome.
- "categoria": exatamente uma destas: {", ".join(categorias)}
  Evite "Outros". Use "Outros" só se o item realmente não couber em nenhuma outra.

EXISTENTES:
{existentes}

ITENS:
{lista}

Responda somente com JSON, sem texto extra:
[{{"i": 0, "produto": "...", "categoria": "..."}}]"""

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(model=MODELO_CLAUDE, max_tokens=8000,
                                 messages=[{"role": "user", "content": prompt}])
    texto = "".join(b.text for b in msg.content if b.type == "text")
    texto = re.sub(r"```(?:json)?", "", texto).strip()
    dados = json.loads(texto[texto.find("["): texto.rfind("]") + 1])
    return {int(d["i"]): d for d in dados if "i" in d}
