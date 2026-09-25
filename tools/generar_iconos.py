"""Genera los iconos del proyecto (agente, owner, extension de Chrome).

Dev-only: requiere Pillow (`requirements-dev.txt`), NO se empaqueta en los
.exe. Los archivos que produce SI se commitean (son estaticos, no secretos):
    assets/icons/agent.ico + .png   -> --icon de build.ps1
    assets/icons/owner.ico + .png   -> --icon de build-owner.ps1
    validator_app/proxy/extension/icon.png (+ icon16.png / icon48.png)

Uso: python tools/generar_iconos.py
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parent.parent
ICONS_DIR = RAIZ / "assets" / "icons"
EXTENSION_DIR = RAIZ / "validator_app" / "proxy" / "extension"

# Se dibuja a resolucion alta y se reduce (antialiasing por supersampling);
# evita el aspecto "dentado" que dan las primitivas de ImageDraw a bajo tamano.
LIENZO = 512
TAMANOS_ICO = [16, 32, 48, 256]

AZUL_AGENTE = (39, 128, 227)  # ttkbootstrap "cosmo" primary
NAVY_OWNER = (27, 42, 74)
AMBAR_OWNER = (243, 156, 18)  # ttkbootstrap "superhero" warning/accent
VERDE_EXTENSION = (10, 125, 44)  # color exacto del icon.png anterior
BLANCO = (255, 255, 255)


def _fondo_redondeado(color, radio_frac=0.22):
    """Cuadrado con esquinas redondeadas del color dado, fondo transparente."""
    img = Image.new("RGBA", (LIENZO, LIENZO), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radio = int(LIENZO * radio_frac)
    draw.rounded_rectangle([0, 0, LIENZO - 1, LIENZO - 1], radius=radio, fill=color)
    return img, draw


def generar_icono_agente() -> Image.Image:
    """Cuadrado azul con un pin de ubicacion blanco (identidad "trabajo de
    campo / cobertura")."""
    img, draw = _fondo_redondeado(AZUL_AGENTE)
    cx, cy = LIENZO // 2, int(LIENZO * 0.42)
    r = int(LIENZO * 0.19)
    # Cabeza circular del pin + punta triangular hacia abajo.
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BLANCO)
    punta = int(LIENZO * 0.30)
    draw.polygon(
        [
            (cx - int(r * 0.62), cy + int(r * 0.62)),
            (cx + int(r * 0.62), cy + int(r * 0.62)),
            (cx, cy + r + punta),
        ],
        fill=BLANCO,
    )
    # Hueco del pin (color de fondo, transparente encima del blanco).
    r2 = int(r * 0.42)
    draw.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], fill=(*AZUL_AGENTE, 255))
    return img


def generar_icono_owner() -> Image.Image:
    """Cuadrado navy oscuro con una llave ambar (identidad "administracion /
    credenciales")."""
    img, draw = _fondo_redondeado(NAVY_OWNER)
    # Llave: circulo (cabeza) + vastago rectangular + dos dientes.
    cx, cy = int(LIENZO * 0.40), int(LIENZO * 0.38)
    r = int(LIENZO * 0.14)
    grosor = int(LIENZO * 0.09)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=AMBAR_OWNER, width=grosor)
    vastago_x0 = cx + int(r * 0.55)
    vastago_x1 = int(LIENZO * 0.82)
    vastago_y0 = cy - grosor // 2
    vastago_y1 = cy + grosor // 2
    draw.rectangle([vastago_x0, vastago_y0, vastago_x1, vastago_y1], fill=AMBAR_OWNER)
    diente_ancho = int(LIENZO * 0.05)
    diente_alto = int(LIENZO * 0.10)
    for dx in (0, diente_ancho * 2):
        x0 = vastago_x1 - diente_ancho - dx
        draw.rectangle(
            [x0, vastago_y1, x0 + diente_ancho, vastago_y1 + diente_alto],
            fill=AMBAR_OWNER,
        )
    return img


def generar_icono_extension(lienzo: int) -> Image.Image:
    """Cuadrado verde (mismo color que el icono anterior) con una flecha
    circular blanca (identidad "renovar sesion"). Sin esquinas redondeadas:
    Chrome ya recorta el icono en su propia UI."""
    img = Image.new("RGB", (lienzo, lienzo), VERDE_EXTENSION)
    draw = ImageDraw.Draw(img)
    cx, cy = lienzo // 2, lienzo // 2
    r = int(lienzo * 0.30)
    grosor = max(2, int(lienzo * 0.09))
    # Arco de ~270 grados (deja un hueco para la "flecha" de refresco).
    bbox = [cx - r, cy - r, cx + r, cy + r]
    draw.arc(bbox, start=-40, end=230, fill=BLANCO, width=grosor)
    # Cabeza de flecha en el extremo del arco (start=-40).
    ang = math.radians(-40)
    punta_x = cx + r * math.cos(ang)
    punta_y = cy + r * math.sin(ang)
    tam = int(lienzo * 0.11)
    draw.polygon(
        [
            (punta_x, punta_y - tam),
            (punta_x + tam, punta_y + tam * 0.3),
            (punta_x - tam * 0.2, punta_y + tam),
        ],
        fill=BLANCO,
    )
    return img


def guardar_ico(img: Image.Image, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, format="ICO", sizes=[(t, t) for t in TAMANOS_ICO])


def guardar_png(img: Image.Image, destino: Path, tamano: int | None = None) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    salida = img.resize((tamano, tamano), Image.LANCZOS) if tamano else img
    salida.save(destino, format="PNG")


def main() -> int:
    agente = generar_icono_agente()
    guardar_png(agente, ICONS_DIR / "agent.png")
    guardar_ico(agente, ICONS_DIR / "agent.ico")

    owner = generar_icono_owner()
    guardar_png(owner, ICONS_DIR / "owner.png")
    guardar_ico(owner, ICONS_DIR / "owner.ico")

    guardar_png(generar_icono_extension(128), EXTENSION_DIR / "icon.png")
    guardar_png(generar_icono_extension(48), EXTENSION_DIR / "icon48.png")
    guardar_png(generar_icono_extension(16), EXTENSION_DIR / "icon16.png")

    print("Generados:")
    for p in [
        ICONS_DIR / "agent.ico", ICONS_DIR / "agent.png",
        ICONS_DIR / "owner.ico", ICONS_DIR / "owner.png",
        EXTENSION_DIR / "icon.png", EXTENSION_DIR / "icon48.png",
        EXTENSION_DIR / "icon16.png",
    ]:
        print(f"  {p.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
