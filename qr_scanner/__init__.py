"""Leitor de QR Code com a câmera ao vivo (componente Streamlit, sem build)."""
import os

import streamlit.components.v1 as components

_componente = components.declare_component(
    "qr_scanner", path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend"))


def qr_scanner(key=None):
    """Mostra a câmera. Quando lê um QR Code, devolve {"texto": ..., "ts": ...}."""
    return _componente(key=key, default=None)
