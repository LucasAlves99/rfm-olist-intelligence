"""Gera o PNG do background do dashboard via Pillow (sem cairo).

Uso:
    python powerbi/_make_png_background.py
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

# Cores do projeto — paleta Linear Minimal (alinhada com mockup/wireframe/agent)
COLORS = {
    "bg_top":         (8, 9, 10),       # #08090A — near-true-black
    "bg_bottom":      (14, 15, 17),     # #0E0F11 — bg-elev-1
    "card":           (19, 20, 24),     # #131418 — bg-elev-2
    "border":         (40, 42, 50),     # #282A32 — sutil
    "text_primary":   (244, 244, 245),  # #F4F4F5 — zinc-100
    "text_secondary": (161, 161, 170),  # #A1A1AA — zinc-400
    "text_muted":     (139, 139, 146),  # #8B8B92 — text-3
    "champions":      (94, 106, 210),   # #5E6AD2 — iris
    "big_spenders":   (191, 111, 248),  # #BF6FF8 — mauve
    "novos":          (242, 201, 76),   # #F2C94C — gold
    "em_risco":       (229, 72, 77),    # #E5484D — radish red
}

WIDTH, HEIGHT = 1920, 1080


def get_font(size: int, bold: bool = False):
    """Tenta carregar Segoe UI; cai em Arial se não achar."""
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def make_gradient_bg(img: Image.Image, color_top: tuple, color_bottom: tuple) -> None:
    """Aplica um gradiente vertical no fundo da imagem."""
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(color_top[0] * (1 - ratio) + color_bottom[0] * ratio)
        g = int(color_top[1] * (1 - ratio) + color_bottom[1] * ratio)
        b = int(color_top[2] * (1 - ratio) + color_bottom[2] * ratio)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))


def rounded_rect(draw: ImageDraw.Draw, xy, radius=10, fill=None, outline=None, width=1):
    """Desenha um retângulo com cantos arredondados."""
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_card(draw: ImageDraw.Draw, x: int, y: int, w: int, h: int, accent_color: tuple):
    """Desenha um card com borda esquerda colorida."""
    rounded_rect(draw, (x, y, x + w, y + h), radius=10, fill=COLORS["card"],
                 outline=COLORS["border"], width=1)
    # Faixa colorida na esquerda
    draw.rectangle((x, y + 2, x + 4, y + h - 2), fill=accent_color)


def make_background():
    img = Image.new("RGB", (WIDTH, HEIGHT), COLORS["bg_top"])
    make_gradient_bg(img, COLORS["bg_top"], COLORS["bg_bottom"])
    draw = ImageDraw.Draw(img, "RGBA")

    # ============= HEADER =============
    # fundo do header
    draw.rectangle((0, 0, WIDTH, 110), fill=COLORS["bg_top"])

    # Faixa colorida no topo (4 cores em gradient)
    section_w = WIDTH // 4
    for i, color in enumerate([COLORS["champions"], COLORS["big_spenders"],
                                COLORS["novos"], COLORS["em_risco"]]):
        draw.rectangle((i * section_w, 0, (i + 1) * section_w, 4), fill=color)

    # Logo / círculo
    draw.ellipse((38, 33, 82, 77), outline=COLORS["champions"], width=3)
    draw.ellipse((50, 45, 70, 65), fill=COLORS["champions"])

    # Títulos
    font_title = get_font(28, bold=True)
    font_subtitle = get_font(13)
    font_label = get_font(11)
    font_kpi_label = get_font(11)
    font_kpi_value = get_font(40, bold=True)
    font_section = get_font(11, bold=True)
    font_panel = get_font(16, bold=True)
    font_panel_sub = get_font(12)

    draw.text((105, 28), "Segmentação de Clientes Olist",
              font=font_title, fill=COLORS["text_primary"])
    draw.text((105, 70), "RFM · CLUSTERIZAÇÃO · INTELIGÊNCIA DE CRM",
              font=font_subtitle, fill=COLORS["text_secondary"])

    # Divisores verticais e info do header
    info_groups = [
        (640, "SNAPSHOT", "04/09/2018"),
        (800, "BASE", "93.358 CLIENTES"),
        (1020, "MODELO", "K-MEANS K=4"),
    ]
    for x, label, value in info_groups:
        draw.line((x, 20, x, 90), fill=COLORS["border"], width=1)
        draw.text((x + 20, 38), label, font=font_label, fill=COLORS["text_muted"])
        draw.text((x + 20, 60), value, font=get_font(15, bold=True),
                  fill=COLORS["text_primary"])

    # ============= KPI ROW =============
    draw.text((40, 145), "INDICADORES PRINCIPAIS",
              font=font_section, fill=COLORS["text_secondary"])

    kpi_data = [
        (40, "TOTAL DE CLIENTES", COLORS["champions"]),
        (505, "RECEITA TOTAL", COLORS["big_spenders"]),
        (970, "TICKET MÉDIO", COLORS["novos"]),
        (1435, "CLIENTES EM RISCO", COLORS["em_risco"]),
    ]
    for x, label, accent in kpi_data:
        draw_card(draw, x, 170, 445, 110, accent)
        draw.text((x + 20, 195), label, font=font_kpi_label, fill=COLORS["text_secondary"])

    # ============= ROW 1 - VISUAIS PRINCIPAIS =============
    panels_row1 = [
        (40, 310, 600, 350, "Distribuição de Receita por Cluster",
         "Tamanho proporcional à receita total · Cor por cluster",
         COLORS["champions"]),
        (660, 310, 600, 350, "Concentração de Receita (Pareto)",
         "Curva de Lorenz · Coeficiente de Gini",
         COLORS["novos"]),
        (1280, 310, 600, 350, "Perfil dos Clusters (R × F × M)",
         "Recency × Frequency · Tamanho = Monetary",
         COLORS["big_spenders"]),
    ]
    for x, y, w, h, title, sub, accent in panels_row1:
        rounded_rect(draw, (x, y, x + w, y + h), radius=10,
                     fill=COLORS["card"], outline=COLORS["border"], width=1)
        draw.text((x + 20, y + 25), title, font=font_panel, fill=COLORS["text_primary"])
        draw.text((x + 20, y + 50), sub, font=font_panel_sub, fill=COLORS["text_muted"])
        draw.line((x + 20, y + 73, x + 160, y + 73), fill=accent, width=2)

    # ============= ROW 2 - DETALHAMENTO =============
    panels_row2 = [
        (40, 680, 600, 350, "Distribuição Geográfica",
         "Clientes por estado · Cor por densidade de receita",
         COLORS["champions"]),
        (660, 680, 600, 350, "Evolução Mensal de Receita",
         "Últimos 24 meses · Quebra por cluster",
         COLORS["big_spenders"]),
        (1280, 680, 600, 350, "Top 50 Champions",
         "Clientes de maior valor · Drill-down por UF",
         COLORS["champions"]),
    ]
    for x, y, w, h, title, sub, accent in panels_row2:
        rounded_rect(draw, (x, y, x + w, y + h), radius=10,
                     fill=COLORS["card"], outline=COLORS["border"], width=1)
        draw.text((x + 20, y + 25), title, font=font_panel, fill=COLORS["text_primary"])
        draw.text((x + 20, y + 50), sub, font=font_panel_sub, fill=COLORS["text_muted"])
        draw.line((x + 20, y + 73, x + 160, y + 73), fill=accent, width=2)

    # ============= FOOTER =============
    draw.line((40, 1050, 1880, 1050), fill=COLORS["border"], width=1)
    draw.text((40, 1060), "Fonte: Olist Brazilian E-Commerce · Pipeline reproduzível em src/",
              font=font_label, fill=COLORS["text_muted"])

    footer_right = "K-Means K=4 · Silhouette 0.369 · Snapshot 2018-09-04"
    bbox = draw.textbbox((0, 0), footer_right, font=font_label)
    text_w = bbox[2] - bbox[0]
    draw.text((1880 - text_w, 1060), footer_right,
              font=font_label, fill=COLORS["text_muted"])

    return img


if __name__ == "__main__":
    img = make_background()
    out = Path("powerbi/dashboard_background_dark.png")
    img.save(out, "PNG", optimize=True)
    size_kb = out.stat().st_size / 1024
    print(f"PNG gerado: {out} ({size_kb:.1f} KB, {WIDTH}×{HEIGHT})")
