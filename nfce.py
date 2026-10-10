"""Leitura do QR Code e da página pública da NFC-e (layout padrão usado por SP e vários estados)."""
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}


# ---------- QR Code ----------
def decodificar_qr(image_bytes: bytes):
    """Recebe a foto (bytes) e devolve o texto do QR Code, ou None."""
    import cv2
    import numpy as np

    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    det = cv2.QRCodeDetector()
    cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    tentativas = [
        img,
        cinza,
        cv2.resize(cinza, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC),
        cv2.threshold(cinza, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
    ]
    for t in tentativas:
        try:
            texto, _, _ = det.detectAndDecode(t)
        except cv2.error:
            continue
        if texto:
            return texto.strip()
    return None


# ---------- Utilitários ----------
def br_num(txt) -> float:
    txt = re.sub(r"[^\d,.\-]", "", str(txt or ""))
    if not txt:
        return 0.0
    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        return 0.0


def extrair_chave(texto: str):
    """Pega os 44 dígitos da chave de acesso a partir do link do QR Code."""
    qs = parse_qs(urlparse(texto).query)
    p = (qs.get("p") or qs.get("chNFe") or [""])[0]
    m = re.search(r"\d{44}", p or texto)
    return m.group(0) if m else None


# ---------- Consulta ----------
def ler_nfce(url: str, timeout: int = 25) -> dict:
    url = url.strip()
    if not url.lower().startswith("http"):
        raise ValueError("O QR Code não contém um link válido de NFC-e.")
    with requests.Session() as s:
        r = s.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    nota = parse_html(r.text)
    nota["url"] = url
    nota["chave"] = nota.get("chave") or extrair_chave(url)
    return nota


def parse_html(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    texto = soup.get_text(" ", strip=True)

    # Itens
    itens = []
    for tr in soup.select("table#tabResult tr"):
        nome = tr.select_one(".txtTit")
        if not nome:
            continue

        def campo(sel):
            el = tr.select_one(sel)
            return el.get_text(" ", strip=True) if el else ""

        qtd = br_num(campo(".Rqtd").split(":")[-1]) or 1.0
        vtot = br_num(campo(".valor"))
        vunit = br_num(campo(".RvlUnit").split(":")[-1]) or (vtot / qtd if qtd else vtot)
        itens.append({
            "descricao": nome.get_text(" ", strip=True),
            "codigo": re.sub(r"\D", "", campo(".RCod")) or None,
            "quantidade": qtd,
            "unidade": campo(".RUN").split(":")[-1].strip().upper(),
            "valor_unitario": vunit,
            "valor_total": vtot,
        })

    if not itens:
        if "captcha" in html.lower():
            raise ValueError("A SEFAZ pediu captcha para essa consulta. Tente de novo mais tarde ou lance manualmente.")
        raise ValueError(
            "Não encontrei itens na página da SEFAZ. A nota pode ainda não estar disponível "
            "(tente mais tarde) ou o layout do seu estado é diferente."
        )

    # Emitente
    topo = soup.select_one("#u20") or soup.select_one(".txtTopo")
    mercado = topo.get_text(" ", strip=True) if topo else "Mercado não identificado"
    m_cnpj = re.search(r"CNPJ:?\s*([\d./\-]{14,18})", texto)

    # Emissão
    data_iso, hora = None, None
    m_data = re.search(r"Emiss[ãa]o:?\s*(\d{2}/\d{2}/\d{4})\s*(\d{2}:\d{2}:\d{2})?", texto)
    if m_data:
        data_iso = datetime.strptime(m_data.group(1), "%d/%m/%Y").date().isoformat()
        hora = m_data.group(2)

    # Totais
    total, desconto = None, 0.0
    for linha in soup.select("#totalNota div"):
        lab = linha.find("label")
        val = linha.select_one(".totalNumb")
        if not lab or not val:
            continue
        rotulo = lab.get_text(" ", strip=True).lower()
        if "valor a pagar" in rotulo:
            total = br_num(val.get_text())
        elif "desconto" in rotulo:
            desconto = br_num(val.get_text())
    if total is None:
        total = round(sum(i["valor_total"] for i in itens) - desconto, 2)

    chave_el = soup.select_one(".chave")
    chave = re.sub(r"\D", "", chave_el.get_text()) if chave_el else None

    return {
        "chave": chave if chave and len(chave) == 44 else None,
        "mercado": mercado,
        "cnpj": m_cnpj.group(1) if m_cnpj else None,
        "data": data_iso,
        "hora": hora,
        "total": total,
        "desconto": desconto,
        "itens": itens,
    }
