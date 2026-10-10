"""Perfis: senha individual (com hash) e biblioteca de ícones."""
import hashlib
import hmac
import secrets

ICONES = {
    "🏰 Medieval": ["🏰", "⚔️", "🛡️", "👑", "🗡️", "🏹", "🐴", "🧙‍♂️", "🧝", "🐉", "🧌", "🪓",
                   "🍺", "📜", "🔮", "🦄", "🏯", "🪄", "🤴", "👸", "🧛", "🦅", "🕯️", "⚜️"],
    "🎮 Games e fantasia": ["🎮", "🕹️", "👾", "🧙", "🧝‍♀️", "🧚", "🐲", "🔥", "❄️", "⚡", "💎", "🗿",
                           "🧿", "💀", "☠️", "🌋", "🌀", "🪬", "🧞", "🧜", "🦹", "🥷", "🎲", "🃏"],
    "🎬 Cinema e séries": ["🎬", "🍿", "🎞️", "📺", "🎥", "🎭", "🦸", "🦸‍♀️", "🧟", "👽", "🤖", "👻",
                          "🕵️", "🦖", "🛸", "🎃", "🦈", "🕷️", "🧛‍♀️", "🎟️", "📽️", "🌃", "🦇", "🔦"],
    "🐾 Animais": ["🐶", "🐱", "🦊", "🐼", "🐨", "🐯", "🦁", "🐸", "🐧", "🦉", "🐙", "🐢",
                  "🦥", "🦦", "🦜", "🐝", "🦋", "🐺", "🐻", "🐰", "🦒", "🐘", "🦩", "🐬"],
    "🍕 Comida": ["🍕", "🍔", "🌮", "🍣", "🍜", "🥑", "🍓", "🍩", "🍪", "🧁", "🥐", "🧀",
                 "🍉", "🍫", "☕", "🍷", "🍺", "🥥", "🌶️", "🍝", "🥩", "🍦", "🥨", "🍋"],
    "⚽ Esportes": ["⚽", "🏀", "🏈", "🎾", "🏐", "🏃", "🚴", "🏊", "🧗", "🥊", "🏋️", "🏄",
                   "⛳", "🏆", "🥇", "🛹", "⛷️", "🤿", "🏓", "🥋", "🏎️", "🎯", "🛶", "🧘"],
    "🌄 Natureza e viagem": ["🌻", "🌾", "🌄", "🏔️", "🌊", "🌵", "🌴", "🍀", "🌙", "☀️", "⭐", "🌈",
                            "🏕️", "🗺️", "✈️", "🧭", "🏝️", "🌸", "🍁", "🌲", "⛺", "🚐", "🗻", "🌅"],
    "🚀 Espaço e ciência": ["🚀", "🪐", "🌌", "☄️", "🛰️", "👨‍🚀", "👩‍🚀", "🔭", "🧪", "🧬", "⚛️", "💡",
                           "🌍", "🌑", "🔬", "🧲", "⚙️", "💻", "📡", "🦾"],
    "🎸 Música": ["🎸", "🎹", "🥁", "🎷", "🎺", "🎻", "🎤", "🎧", "🎵", "🪕", "📻", "💿"],
    "😎 Carinhas": ["😎", "🤓", "🥸", "🤠", "🥳", "😈", "🤡", "🤩", "😇", "🧐", "🙃", "🫠",
                   "😺", "🤖", "👹", "👺", "🤪", "😴", "🥶", "🤯"],
}

CORES = {
    "🟥": "#E50914", "🟦": "#0071EB", "🟨": "#F5B50C", "🟩": "#2BB24C", "🟪": "#8E44AD",
    "🟧": "#E67E22", "🟫": "#795548", "⬛": "#2B2B2B", "⬜": "#B0BEC5",
}

PADROES = [("😎", "#0071EB"), ("🌻", "#F5B50C"), ("🦊", "#E67E22"), ("🐉", "#2BB24C"),
           ("🎮", "#8E44AD"), ("🍕", "#E50914")]


def gerar_hash(senha: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(salt), 200_000).hex()
    return f"pbkdf2${salt}${h}"


def verificar(senha: str, armazenado: str) -> bool:
    try:
        _, salt, h = armazenado.split("$")
    except (ValueError, AttributeError):
        return False
    calc = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(salt), 200_000).hex()
    return hmac.compare_digest(calc, h)


def avatar_html(icone: str, cor: str, tamanho: int = 96, inline: bool = False) -> str:
    estilo = (f"width:{tamanho}px;height:{tamanho}px;border-radius:{max(6, tamanho // 6)}px;"
              f"background:{cor};display:{'inline-flex' if inline else 'flex'};align-items:center;"
              f"justify-content:center;font-size:{int(tamanho * 0.6)}px;line-height:1;"
              f"{'vertical-align:middle;margin-right:8px' if inline else 'margin:0 auto 6px'}")
    return f'<div style="{estilo}">{icone}</div>'
