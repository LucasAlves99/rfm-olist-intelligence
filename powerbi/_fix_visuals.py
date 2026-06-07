"""Ajustes de legibilidade nos visuais Deneb da pagina Visao Executiva.
Edita os specs Vega/Vega-Lite embutidos (escapados) nos visual.json.
"""
import json
from pathlib import Path

BASE = Path(__file__).parent / "RFM.Report" / "definition" / "pages" / "3fb8c22c8b1d0093f1e5" / "visuals"


def load_spec(visual_path):
    vj = json.loads(visual_path.read_text(encoding="utf-8"))
    raw = vj["visual"]["objects"]["vega"][0]["properties"]["jsonSpec"]["expr"]["Literal"]["Value"]
    assert raw[0] == "'" and raw[-1] == "'", "formato inesperado do literal"
    inner = raw[1:-1].replace("''", "'")
    spec = json.loads(inner)
    return vj, spec


def save_spec(visual_path, vj, spec):
    spec_str = json.dumps(spec, ensure_ascii=False, indent=2)
    new_value = "'" + spec_str.replace("'", "''") + "'"
    vj["visual"]["objects"]["vega"][0]["properties"]["jsonSpec"]["expr"]["Literal"]["Value"] = new_value
    visual_path.write_text(json.dumps(vj, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- TREEMAP
def fix_treemap():
    p = BASE / "2963ce1ef4790a32ea9d" / "visual.json"
    vj, spec = load_spec(p)
    for mark in spec["marks"]:
        if mark.get("type") != "text":
            continue
        enter = mark["encode"]["enter"]
        upd = mark["encode"].setdefault("update", {})
        txt = enter.get("text", {})
        field = txt.get("field")
        signal = txt.get("signal", "")
        if field == "Cluster_Name":
            # titulo: oculta em tiles muito baixos
            upd["fillOpacity"] = {"signal": "(datum.y1 - datum.y0) > 50 ? 1 : 0"}
        elif "clientes" in signal:
            # subtitulo: so aparece quando ha espaco vertical e horizontal
            upd["fillOpacity"] = {"signal": "(datum.y1 - datum.y0) > 78 && (datum.x1 - datum.x0) > 90 ? 1 : 0"}
            upd["limit"] = {"signal": "datum.x1 - datum.x0 - 24"}
        elif "mi" in signal:
            # valor R$: fonte adaptativa ao tamanho do tile + limite de largura
            upd["fontSize"] = {"signal": "clamp(min((datum.y1 - datum.y0) * 0.32, (datum.x1 - datum.x0) * 0.20), 13, 26)"}
            upd["limit"] = {"signal": "datum.x1 - datum.x0 - 20"}
            enter.pop("fontSize", None)
    save_spec(p, vj, spec)
    print("treemap OK")


# ---------------------------------------------------------------- CLV vs TICKET
def fix_clv():
    p = BASE / "p1_clv_ticket" / "visual.json"
    vj, spec = load_spec(p)
    # margem direita p/ rotulos R$ nao cortarem
    spec["padding"] = {"left": 0, "top": 0, "bottom": 0, "right": 30}
    # rotulos mais legiveis
    for layer in spec["layer"]:
        m = layer.get("mark", {})
        if isinstance(m, dict) and m.get("type") == "text":
            m["color"] = "#E4E4E7"
            m["fontWeight"] = 600
            m["fontSize"] = 9
    save_spec(p, vj, spec)
    print("clv OK")


# ---------------------------------------------------------------- LORENZ / PARETO
def fix_lorenz():
    p = BASE / "p1_concentracao" / "visual.json"
    vj, spec = load_spec(p)
    for layer in spec["layer"]:
        enc = layer.get("encoding", {})
        m = layer.get("mark", {})
        mtype = m.get("type") if isinstance(m, dict) else None
        if mtype == "area":
            # area de Gini nao deve contribuir com titulo de eixo
            if "y" in enc:
                enc["y"]["title"] = None
            if "x" in enc:
                enc["x"]["title"] = None
        if mtype == "line" and enc.get("y", {}).get("field") == "pct_revenue":
            # curva de Lorenz: titulo limpo no eixo Y
            enc["y"]["title"] = "% receita acumulada"
    save_spec(p, vj, spec)
    print("lorenz OK")


if __name__ == "__main__":
    fix_treemap()
    fix_clv()
    fix_lorenz()
    print("Concluido.")
