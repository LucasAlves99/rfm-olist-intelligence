"""Gera os 5 visuais Deneb da pagina P2 (Analise Detalhada).
Monta o spec Vega-Lite como dict, serializa, escapa aspas simples ('') e
embrulha no formato Literal.Value do Deneb. Sobrescreve os visual.json.
"""
import json
from pathlib import Path

BASE = Path(r"C:\Users\Luk\Desktop\RFM-Projeto\powerbi\RFM.Report\definition\pages\254456cb6d77b49f0482\visuals")
DENEB = "deneb7E15AEF80B9E4D4F8E12924291ECE89A"

CLUSTER_DOMAIN = [
    "Campeões",
    "Big Spenders (Não-Recorrentes)",
    "Novos / Ocasionais",
    "Em Risco / Hibernando",
]
CLUSTER_RANGE = ["#5E6AD2", "#BF6FF8", "#F2C94C", "#E5484D"]

AXIS_CFG = {
    "domain": False, "ticks": False, "gridColor": "rgba(255,255,255,0.06)",
    "labelColor": "#C8C8D0", "titleColor": "#9aa0aa",
    "labelFontSize": 9, "titleFontSize": 9,
}
BASE_CFG = {"view": {"stroke": None}, "font": "Segoe UI", "axis": AXIS_CFG}


def col(entity, prop, active=True):
    return {
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
        "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop, "active": active,
    }


def mea(entity, prop):
    return {
        "field": {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
        "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop, "displayName": prop,
    }


def wrap(spec):
    s = json.dumps(spec, ensure_ascii=False)
    return "'" + s.replace("'", "''") + "'"


def build(name, x, y, z, projections, spec, vw=378, vh=194):
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
        "name": name,
        "position": {"x": x, "y": y, "z": z, "height": 204, "width": 388, "tabOrder": z},
        "visual": {
            "visualType": DENEB,
            "query": {"queryState": {"dataset": {"projections": projections}}},
            "objects": {
                "vega": [{"properties": {
                    "provider": {"expr": {"Literal": {"Value": "'vegaLite'"}}},
                    "jsonSpec": {"expr": {"Literal": {"Value": wrap(spec)}}},
                    "jsonConfig": {"expr": {"Literal": {"Value": "'{}'"}}},
                    "enableTooltips": {"expr": {"Literal": {"Value": "true"}}},
                    "enableContextMenu": {"expr": {"Literal": {"Value": "true"}}},
                    "enableHighlight": {"expr": {"Literal": {"Value": "true"}}},
                    "enableSelection": {"expr": {"Literal": {"Value": "true"}}},
                    "selectionMaxDataPoints": {"expr": {"Literal": {"Value": "50D"}}},
                    "selectionMode": {"expr": {"Literal": {"Value": "'simple'"}}},
                    "version": {"expr": {"Literal": {"Value": "'6.4.1'"}}},
                }}],
                "developer": [{"properties": {"version": {"expr": {"Literal": {"Value": "'1.9.1.0'"}}}}}],
                "stateManagement": [{"properties": {
                    "viewportHeight": {"expr": {"Literal": {"Value": f"{vh}D"}}},
                    "viewportWidth": {"expr": {"Literal": {"Value": f"{vw}D"}}},
                }}],
            },
            "visualContainerObjects": {k: [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}]
                                       for k in ("border", "background", "title", "visualHeader")},
            "drillFilterOtherVisuals": True,
        },
    }


# ---------------- SPEC 1: Evolucao mensal (Receita + Clientes Ativos) ----------------
spec_evol = {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "background": "transparent", "padding": 0, "width": "container", "height": "container",
    "config": {**BASE_CFG, "legend": {"labelColor": "#C8C8D0", "labelFontSize": 9,
               "symbolSize": 60, "orient": "top", "title": None, "offset": 0}},
    "data": {"name": "dataset"},
    "encoding": {"x": {"field": "AnoMes", "type": "ordinal", "title": None,
        "axis": {"labelAngle": 0, "labelFontSize": 8,
                 "labelExpr": "split(datum.value, '-')[1] == '01' ? split(datum.value, '-')[0] : ''"}}},
    "layer": [
        {"mark": {"type": "area", "interpolate": "monotone", "line": {"color": "#A78BFA", "strokeWidth": 2},
                  "color": {"gradient": "linear", "x1": 1, "y1": 1, "x2": 1, "y2": 0,
                            "stops": [{"offset": 0, "color": "rgba(167,139,250,0.02)"},
                                      {"offset": 1, "color": "rgba(167,139,250,0.28)"}]}},
         "encoding": {"y": {"field": "Receita Pedidos", "type": "quantitative", "title": "Receita (R$)",
                            "axis": {"format": "~s", "grid": True}},
                      "tooltip": [{"field": "AnoMes"}, {"field": "Receita Pedidos", "format": ",.0f"}]}},
        {"mark": {"type": "line", "interpolate": "monotone", "strokeWidth": 2, "color": "#5E6AD2"},
         "encoding": {"y": {"field": "Clientes Ativos", "type": "quantitative", "title": "Clientes",
                            "axis": {"format": "~s", "grid": False}},
                      "tooltip": [{"field": "AnoMes"}, {"field": "Clientes Ativos", "format": ",.0f"}]}},
    ],
    "resolve": {"scale": {"y": "independent"}},
}

# ---------------- SPEC 2: Receita & Clientes por segmento ----------------
spec_seg = {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "background": "transparent", "padding": 0, "width": "container", "height": "container",
    "config": {**BASE_CFG, "legend": {"disable": True}},
    "data": {"name": "dataset"},
    "transform": [{"calculate": "'R$ ' + format(datum['Receita Total'], ',.2s')", "as": "lbl"}],
    "layer": [
        {"mark": {"type": "bar", "cornerRadiusEnd": 4, "height": {"band": 0.7}},
         "encoding": {"color": {"field": "Cluster_Name", "type": "nominal",
                                "scale": {"domain": CLUSTER_DOMAIN, "range": CLUSTER_RANGE}, "legend": None}}},
        {"mark": {"type": "text", "align": "left", "dx": 6, "color": "#F4F4F5", "fontSize": 10, "fontWeight": 600},
         "encoding": {"text": {"field": "lbl", "type": "nominal"}}},
    ],
    "encoding": {
        "y": {"field": "Cluster_Name", "type": "nominal", "title": None,
              "sort": {"field": "Receita Total", "op": "sum", "order": "descending"},
              "axis": {"labelLimit": 120, "labelFontSize": 9}},
        "x": {"field": "Receita Total", "type": "quantitative", "title": None,
              "axis": {"format": "~s", "grid": True}},
        "tooltip": [{"field": "Cluster_Name"}, {"field": "Receita Total", "format": ",.0f"},
                    {"field": "Total Clientes", "format": ",.0f"}],
    },
}

# ---------------- SPEC 3: Receita em risco por segmento ----------------
spec_risco = {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "background": "transparent", "padding": 0, "width": "container", "height": "container",
    "config": {**BASE_CFG, "legend": {"disable": True}},
    "data": {"name": "dataset"},
    "transform": [{"calculate": "'R$ ' + format(datum['Receita em Risco'], ',.2s')", "as": "lbl"}],
    "layer": [
        {"mark": {"type": "bar", "cornerRadiusEnd": 4, "height": {"band": 0.7}},
         "encoding": {"color": {"field": "Cluster_Name", "type": "nominal",
                                "scale": {"domain": CLUSTER_DOMAIN, "range": CLUSTER_RANGE}, "legend": None}}},
        {"mark": {"type": "text", "align": "left", "dx": 6, "color": "#F4F4F5", "fontSize": 10, "fontWeight": 600},
         "encoding": {"text": {"field": "lbl", "type": "nominal"}}},
    ],
    "encoding": {
        "y": {"field": "Cluster_Name", "type": "nominal", "title": None,
              "sort": {"field": "Receita em Risco", "op": "sum", "order": "descending"},
              "axis": {"labelLimit": 120, "labelFontSize": 9}},
        "x": {"field": "Receita em Risco", "type": "quantitative", "title": None,
              "axis": {"format": "~s", "grid": True}},
        "tooltip": [{"field": "Cluster_Name"}, {"field": "Receita em Risco", "format": ",.0f"},
                    {"field": "Clientes em Risco", "format": ",.0f"}],
    },
}

# ---------------- SPEC 4: Top categorias por receita ----------------
spec_cat = {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "background": "transparent", "padding": 0, "width": "container", "height": "container",
    "config": {**BASE_CFG, "legend": {"disable": True}},
    "data": {"name": "dataset"},
    "transform": [
        {"filter": "datum['product_category'] != null && datum['Receita Pedidos'] != null"},
        {"window": [{"op": "rank", "as": "rk"}],
         "sort": [{"field": "Receita Pedidos", "order": "descending"}]},
        {"filter": "datum.rk <= 10"},
        {"calculate": "'R$ ' + format(datum['Receita Pedidos'], ',.2s')", "as": "lbl"},
    ],
    "layer": [
        {"mark": {"type": "bar", "cornerRadiusEnd": 4, "height": {"band": 0.72},
                  "color": {"gradient": "linear", "x1": 0, "x2": 1, "y1": 0, "y2": 0,
                            "stops": [{"offset": 0, "color": "#6D5BD0"}, {"offset": 1, "color": "#BF6FF8"}]}}},
        {"mark": {"type": "text", "align": "left", "dx": 6, "color": "#C8C8D0", "fontSize": 9},
         "encoding": {"text": {"field": "lbl", "type": "nominal"}}},
    ],
    "encoding": {
        "y": {"field": "product_category", "type": "nominal", "title": None,
              "sort": {"field": "Receita Pedidos", "op": "sum", "order": "descending"},
              "axis": {"labelLimit": 110, "labelFontSize": 8.5,
                       "labelExpr": "replace(slice(datum.value, 0, 16), '_', ' ')"}},
        "x": {"field": "Receita Pedidos", "type": "quantitative", "title": None,
              "axis": {"format": "~s", "grid": True}},
        "tooltip": [{"field": "product_category"}, {"field": "Receita Pedidos", "format": ",.0f"}],
    },
}

# ---------------- SPEC 5: Frequencia x Ticket medio (bolhas) ----------------
spec_freq = {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "background": "transparent", "padding": 0, "width": "container", "height": "container",
    "config": {**BASE_CFG, "legend": {"labelColor": "#C8C8D0", "labelFontSize": 8, "symbolSize": 50,
               "orient": "top", "columns": 2, "title": None, "offset": 2}},
    "data": {"name": "dataset"},
    "mark": {"type": "circle", "opacity": 0.85, "stroke": "#0A0A0F", "strokeWidth": 1},
    "encoding": {
        "x": {"field": "Frequency Media", "type": "quantitative", "title": "Frequencia media",
              "scale": {"zero": False, "nice": True}, "axis": {"grid": True}},
        "y": {"field": "Ticket Medio", "type": "quantitative", "title": "Ticket medio (R$)",
              "scale": {"zero": False, "nice": True}, "axis": {"format": "~s", "grid": True}},
        "size": {"field": "Receita Total", "type": "quantitative",
                 "scale": {"range": [200, 2600]}, "legend": None},
        "color": {"field": "Cluster_Name", "type": "nominal",
                  "scale": {"domain": CLUSTER_DOMAIN, "range": CLUSTER_RANGE}, "legend": {"title": None}},
        "tooltip": [{"field": "Cluster_Name"}, {"field": "Frequency Media", "format": ",.2f"},
                    {"field": "Ticket Medio", "format": ",.2f"},
                    {"field": "Receita Total", "format": ",.0f"}],
    },
}

# Feedback visual de seleção (cross-filter): escurece o que não foi clicado.
# O cross-filter da página já vem de enableSelection=true; isto é só o realce.
SEL = {"condition": {"test": "datum.__selected__ === 'off'", "value": 0.22}, "value": 1}
for _sp in (spec_evol, spec_seg, spec_risco, spec_cat, spec_freq):
    _sp["encoding"]["opacity"] = SEL

visuals = [
    ("p2_uf", 26, 196, 5000,
     [col("dim_calendario", "AnoMes"), mea("_KPIs", "Receita Pedidos"), mea("_KPIs", "Clientes Ativos")],
     spec_evol),
    ("p2_evolucao", 446, 196, 6000,
     [col("dim_segmentos", "Cluster_Name"), mea("_KPIs", "Receita Total"), mea("_KPIs", "Total Clientes")],
     spec_seg),
    ("p2_review_cluster", 866, 196, 5500,
     [col("dim_segmentos", "Cluster_Name"), mea("_Saude", "Receita em Risco"), mea("_Saude", "Clientes em Risco")],
     spec_risco),
    ("p2_top_champions", 26, 464, 5200,
     [col("fato_pedidos", "product_category"), mea("_KPIs", "Receita Pedidos")],
     spec_cat),
    # p2_review_recency agora é HTML Content (Plano de Ação) — não regenerar aqui.
]

for name, x, y, z, proj, spec in visuals:
    obj = build(name, x, y, z, proj, spec)
    fp = BASE / name / "visual.json"
    fp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK {name} -> {fp}")

print("done")
