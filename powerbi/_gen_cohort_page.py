"""Cria a pagina 'Retencao / Cohort' com um heatmap Deneb sobre fato_cohort."""
import json
from pathlib import Path

PAGES = Path(r"C:\Users\Luk\Desktop\RFM-Projeto\powerbi\RFM.Report\definition\pages")
PAGE_ID = "a1f2b3c4d5e6f7a8b9c0"
DENEB = "deneb7E15AEF80B9E4D4F8E12924291ECE89A"


def col(entity, prop):
    return {"field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
            "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop, "active": True}


def mea(entity, prop):
    return {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
            "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop, "displayName": prop}


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


# ---------- Spec do heatmap ----------
spec = {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "background": "transparent", "padding": 5, "width": "container", "height": "container",
    "title": {
        "text": "Retenção por safra de aquisição (cohort)",
        "subtitle": ["Base fortemente transacional: a retenção colapsa após o mês 0 — a maioria compra uma única vez."],
        "color": "#F4F4F5", "fontSize": 16, "fontWeight": 700,
        "subtitleColor": "#A1A1AA", "subtitleFontSize": 11, "anchor": "start", "offset": 12,
    },
    "config": {
        "view": {"stroke": None}, "font": "Segoe UI",
        "axis": {"domain": False, "ticks": False, "labelColor": "#C8C8D0", "titleColor": "#9aa0aa",
                 "labelFontSize": 10, "titleFontSize": 11, "grid": False},
        "legend": {"labelColor": "#C8C8D0", "titleColor": "#9aa0aa", "labelFontSize": 9, "titleFontSize": 10},
    },
    "data": {"name": "dataset"},
    "transform": [
        {"filter": "datum['MesIndice'] != null && datum['MesIndice'] <= 12"},
    ],
    "layer": [
        {"mark": {"type": "rect", "stroke": "#0A0A0F", "strokeWidth": 1, "cornerRadius": 2},
         "encoding": {"color": {
             "field": "Retencao Cohort", "type": "quantitative", "title": "Retenção",
             "scale": {"type": "sqrt", "domain": [0, 1],
                       "range": ["#14151D", "#3a2f5a", "#7C5BD0", "#BF6FF8", "#F2C94C", "#34D399"]},
             "legend": {"format": ".0%", "gradientLength": 160}}}},
        {"mark": {"type": "text", "fontSize": 8, "fontWeight": 600},
         "encoding": {
             "text": {"field": "Retencao Cohort", "type": "quantitative", "format": ".0%"},
             "color": {"condition": {"test": "datum['Retencao Cohort'] > 0.15", "value": "#0A0A0F"},
                       "value": "#8a8a96"}}},
    ],
    "encoding": {
        "x": {"field": "MesIndice", "type": "ordinal", "title": "Meses desde a 1ª compra",
              "axis": {"labelAngle": 0}},
        "y": {"field": "Safra", "type": "ordinal", "title": "Safra de aquisição",
              "sort": "ascending", "axis": {"labelFontSize": 9}},
        "tooltip": [{"field": "Safra"}, {"field": "MesIndice"},
                    {"field": "Retencao Cohort", "type": "quantitative", "format": ".2%"}],
    },
}

spec_str = "'" + json.dumps(spec, ensure_ascii=False).replace("'", "''") + "'"

visual = {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
    "name": "cohort_heatmap",
    "position": {"x": 32, "y": 24, "z": 1000, "height": 344, "width": 1216, "tabOrder": 1000},
    "visual": {
        "visualType": DENEB,
        "query": {"queryState": {"dataset": {"projections": [
            col("fato_cohort", "Safra"), col("fato_cohort", "MesIndice"),
            mea("_Saude", "Retencao Cohort")]}}},
        "objects": {
            "vega": [{"properties": {
                "provider": lit("'vegaLite'"),
                "jsonSpec": lit(spec_str),
                "jsonConfig": lit("'{}'"),
                "enableTooltips": lit("true"),
                "enableContextMenu": lit("true"),
                "enableHighlight": lit("false"),
                "enableSelection": lit("false"),
                "version": lit("'6.4.1'"),
            }}],
            "developer": [{"properties": {"version": lit("'1.9.1.0'")}}],
            "stateManagement": [{"properties": {
                "viewportHeight": lit("334D"), "viewportWidth": lit("1206D")}}],
        },
        "visualContainerObjects": {k: [{"properties": {"show": lit("false")}}]
                                   for k in ("border", "background", "title", "visualHeader")},
        "drillFilterOtherVisuals": True,
    },
}

# ---------- visual 2: Risco de review ruim por UF (modelo ML) ----------
spec_uf = {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "background": "transparent", "padding": 5, "width": "container", "height": "container",
    "title": {
        "text": "Risco de review ruim por UF (modelo preditivo)",
        "subtitle": ["% de pedidos com alta probabilidade de avaliação ≤ 2 — onde priorizar service recovery."],
        "color": "#F4F4F5", "fontSize": 15, "fontWeight": 700,
        "subtitleColor": "#A1A1AA", "subtitleFontSize": 11, "anchor": "start", "offset": 10,
    },
    "config": {"view": {"stroke": None}, "font": "Segoe UI",
               "axis": {"domain": False, "ticks": False, "gridColor": "rgba(255,255,255,0.06)",
                        "labelColor": "#C8C8D0", "titleColor": "#9aa0aa", "labelFontSize": 10, "titleFontSize": 10},
               "legend": {"disable": True}},
    "data": {"name": "dataset"},
    "transform": [
        {"window": [{"op": "rank", "as": "rk"}], "sort": [{"field": "Pct_Alto_Risco", "order": "descending"}]},
        {"filter": "datum.rk <= 14"},
        {"calculate": "format(datum['Pct_Alto_Risco'], '.1%')", "as": "lbl"},
    ],
    "layer": [
        {"mark": {"type": "bar", "cornerRadiusEnd": 4, "height": {"band": 0.72}},
         "encoding": {"color": {"field": "Pct_Alto_Risco", "type": "quantitative",
                                "scale": {"range": ["#F2C94C", "#E5484D"]}, "legend": None}}},
        {"mark": {"type": "text", "align": "left", "dx": 6, "color": "#C8C8D0", "fontSize": 10},
         "encoding": {"text": {"field": "lbl", "type": "nominal"}}},
    ],
    "encoding": {
        "y": {"field": "UF", "type": "nominal", "title": None,
              "sort": {"field": "Pct_Alto_Risco", "op": "max", "order": "descending"},
              "axis": {"labelFontSize": 10}},
        "x": {"field": "Pct_Alto_Risco", "type": "quantitative", "title": None,
              "axis": {"format": ".0%", "grid": True}},
        "tooltip": [{"field": "UF"}, {"field": "Pct_Alto_Risco", "type": "quantitative", "format": ".1%"},
                    {"field": "Pedidos", "type": "quantitative", "format": ",.0f"}],
    },
}
spec_uf_str = "'" + json.dumps(spec_uf, ensure_ascii=False).replace("'", "''") + "'"

visual_uf = {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
    "name": "review_uf",
    "position": {"x": 32, "y": 384, "z": 1001, "height": 312, "width": 1216, "tabOrder": 1001},
    "visual": {
        "visualType": DENEB,
        "query": {"queryState": {"dataset": {"projections": [
            col("risco_review_uf", "UF"), col("risco_review_uf", "Pct_Alto_Risco"),
            col("risco_review_uf", "Pedidos")]}}},
        "objects": {
            "vega": [{"properties": {
                "provider": lit("'vegaLite'"), "jsonSpec": lit(spec_uf_str), "jsonConfig": lit("'{}'"),
                "enableTooltips": lit("true"), "enableContextMenu": lit("true"),
                "enableHighlight": lit("false"), "enableSelection": lit("false"), "version": lit("'6.4.1'"),
            }}],
            "developer": [{"properties": {"version": lit("'1.9.1.0'")}}],
            "stateManagement": [{"properties": {"viewportHeight": lit("302D"), "viewportWidth": lit("1206D")}}],
        },
        "visualContainerObjects": {k: [{"properties": {"show": lit("false")}}]
                                   for k in ("border", "background", "title", "visualHeader")},
        "drillFilterOtherVisuals": True,
    },
}

# ---------- page.json ----------
dark = {"solid": {"color": lit("'#0A0A0F'")}}
page = {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
    "name": PAGE_ID,
    "displayName": "Retenção & Qualidade",
    "displayOption": "FitToPage",
    "height": 720, "width": 1280,
    "objects": {
        "background": [{"properties": {"color": dark, "transparency": lit("0D")}}],
        "outspace": [{"properties": {"color": dark, "transparency": lit("0D")}}],
    },
}

# ---------- escrever ----------
pdir = PAGES / PAGE_ID
(pdir / "visuals" / "cohort_heatmap").mkdir(parents=True, exist_ok=True)
(pdir / "visuals" / "review_uf").mkdir(parents=True, exist_ok=True)
(pdir / "page.json").write_text(json.dumps(page, ensure_ascii=False, indent=2), encoding="utf-8")
(pdir / "visuals" / "cohort_heatmap" / "visual.json").write_text(
    json.dumps(visual, ensure_ascii=False, indent=2), encoding="utf-8")
(pdir / "visuals" / "review_uf" / "visual.json").write_text(
    json.dumps(visual_uf, ensure_ascii=False, indent=2), encoding="utf-8")

# pages.json — adicionar ao final da ordem
pj = PAGES / "pages.json"
meta = json.loads(pj.read_text(encoding="utf-8"))
if PAGE_ID not in meta["pageOrder"]:
    meta["pageOrder"].append(PAGE_ID)
pj.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

print("Pagina cohort criada:", pdir)
print("pageOrder:", meta["pageOrder"])
