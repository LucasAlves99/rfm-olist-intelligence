"""Tools que o Claude pode chamar via Tool Use.

Cada tool roda uma query DuckDB sobre os datamarts em Parquet
(lazy loading + cache em RAM via singleton).
"""

# Standard library
import json
import logging
from pathlib import Path
from typing import Any

# Third-party
import duckdb

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Conexão DuckDB singleton (1x por processo)
# ──────────────────────────────────────────────────────────────────────────────
_CONN: duckdb.DuckDBPyConnection | None = None
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def get_connection() -> duckdb.DuckDBPyConnection:
    """Retorna conexão DuckDB com as 4 tabelas registradas como views."""
    global _CONN
    if _CONN is not None:
        return _CONN

    conn = duckdb.connect()
    tables = {
        "fato_rfm_clientes": _DATA_DIR / "fato_rfm_clientes.parquet",
        "fato_pedidos": _DATA_DIR / "fato_pedidos.parquet",
        "dim_segmentos": _DATA_DIR / "dim_segmentos.parquet",
        "dim_calendario": _DATA_DIR / "dim_calendario.parquet",
    }
    for name, path in tables.items():
        if path.exists():
            conn.execute(
                f"CREATE OR REPLACE VIEW {name} AS "
                f"SELECT * FROM read_parquet('{path.as_posix()}')"
            )
            logger.info(f"View criada: {name}")
        else:
            logger.warning(f"Parquet não encontrado: {path}")

    _CONN = conn
    return conn


# ──────────────────────────────────────────────────────────────────────────────
# Implementações das tools
# ──────────────────────────────────────────────────────────────────────────────


def get_cluster_summary() -> dict[str, Any]:
    """Retorna estatísticas agregadas dos 4 clusters."""
    conn = get_connection()
    df = conn.execute(
        """
        SELECT
            Cluster_Name,
            COUNT(*) AS n_clientes,
            ROUND(AVG(Recency), 1) AS recency_media_dias,
            ROUND(AVG(Frequency), 2) AS frequency_media,
            ROUND(AVG(Monetary), 2) AS monetary_medio,
            ROUND(SUM(Monetary), 2) AS receita_total,
            ROUND(AVG(CLV_12m), 2) AS clv_12m_medio,
            ROUND(AVG(Avg_Review), 2) AS review_score_medio
        FROM fato_rfm_clientes
        GROUP BY Cluster_Name
        ORDER BY receita_total DESC
    """
    ).df()
    return {"clusters": df.to_dict(orient="records")}


def filter_by_state(state: str, cluster_name: str | None = None) -> dict[str, Any]:
    """Filtra clientes por UF (opcionalmente por cluster).

    Args:
        state: Sigla do estado (ex: 'SP', 'RJ', 'MG'). Case-insensitive.
        cluster_name: Nome do cluster (opcional). Ex: 'Em Risco / Hibernando'.

    Returns:
        Estatísticas agregadas dos clientes filtrados.
    """
    conn = get_connection()
    where = ["fp.customer_state = ?"]
    params: list[Any] = [state.upper()]

    if cluster_name:
        where.append("frc.Cluster_Name = ?")
        params.append(cluster_name)

    where_sql = " AND ".join(where)

    df = conn.execute(
        f"""
        SELECT
            COUNT(DISTINCT frc.customer_unique_id) AS n_clientes,
            ROUND(AVG(frc.Recency), 1) AS recency_media,
            ROUND(AVG(frc.Frequency), 2) AS frequency_media,
            ROUND(AVG(frc.Monetary), 2) AS monetary_medio,
            ROUND(SUM(frc.Monetary), 2) AS receita_total,
            ROUND(AVG(frc.CLV_12m), 2) AS clv_medio
        FROM fato_rfm_clientes frc
        JOIN (
            SELECT DISTINCT customer_unique_id, customer_state
            FROM fato_pedidos
        ) fp ON fp.customer_unique_id = frc.customer_unique_id
        WHERE {where_sql}
    """,
        params,
    ).df()

    if df.iloc[0]["n_clientes"] == 0:
        return {"filtro": {"state": state, "cluster_name": cluster_name}, "encontrado": False}

    return {
        "filtro": {"state": state.upper(), "cluster_name": cluster_name},
        "encontrado": True,
        "resultado": df.iloc[0].to_dict(),
    }


def revenue_concentration(top_pct: float = 0.20) -> dict[str, Any]:
    """Calcula a concentração de receita (Pareto) no top N% dos clientes.

    Args:
        top_pct: Fração (0.0 - 1.0) representando o top N%. Default 0.20 (Pareto clássico).
    """
    conn = get_connection()
    df = conn.execute(
        f"""
        WITH ordenado AS (
            SELECT
                customer_unique_id,
                Monetary,
                ROW_NUMBER() OVER (ORDER BY Monetary DESC) AS rn,
                COUNT(*) OVER () AS total
            FROM fato_rfm_clientes
        ),
        flag AS (
            SELECT
                Monetary,
                CASE WHEN rn <= total * {top_pct} THEN 1 ELSE 0 END AS in_top
            FROM ordenado
        )
        SELECT
            ROUND(SUM(CASE WHEN in_top = 1 THEN Monetary ELSE 0 END), 2) AS receita_top,
            ROUND(SUM(Monetary), 2) AS receita_total,
            COUNT(*) AS n_clientes,
            SUM(in_top) AS n_top
        FROM flag
    """
    ).df()

    row = df.iloc[0]
    pct_receita = row["receita_top"] / row["receita_total"]
    return {
        "top_pct_clientes": top_pct,
        "n_clientes_no_top": int(row["n_top"]),
        "receita_no_top": float(row["receita_top"]),
        "receita_total": float(row["receita_total"]),
        "pct_receita_concentrada": round(pct_receita, 4),
    }


def get_top_customers(cluster_name: str | None = None, limit: int = 10) -> dict[str, Any]:
    """Retorna os top N clientes ordenados por CLV projetado."""
    conn = get_connection()
    where = ""
    params: list[Any] = []
    if cluster_name:
        where = "WHERE Cluster_Name = ?"
        params.append(cluster_name)

    df = conn.execute(
        f"""
        SELECT
            customer_unique_id,
            Cluster_Name,
            Recency,
            Frequency,
            ROUND(Monetary, 2) AS Monetary,
            ROUND(CLV_12m, 2) AS CLV_12m
        FROM fato_rfm_clientes
        {where}
        ORDER BY CLV_12m DESC
        LIMIT {limit}
    """,
        params,
    ).df()

    return {
        "filtro_cluster": cluster_name,
        "limite": limit,
        "clientes": df.to_dict(orient="records"),
    }


def state_distribution(metric: str = "receita") -> dict[str, Any]:
    """Distribuição por UF.

    Args:
        metric: "receita" (default) ou "clientes".
    """
    conn = get_connection()

    if metric == "clientes":
        agg = "COUNT(DISTINCT customer_unique_id)"
        col_name = "n_clientes"
    else:
        agg = "SUM(monetary_value)"
        col_name = "receita_total"

    df = conn.execute(
        f"""
        SELECT
            customer_state AS UF,
            {agg} AS valor
        FROM fato_pedidos
        WHERE customer_state IS NOT NULL
        GROUP BY customer_state
        ORDER BY valor DESC
        LIMIT 10
    """
    ).df()

    df.columns = ["UF", col_name]
    total = df[col_name].sum()
    df["pct"] = (df[col_name] / total * 100).round(2)

    return {
        "metric": metric,
        "top_estados": df.to_dict(orient="records"),
    }


def overall_kpis() -> dict[str, Any]:
    """KPIs gerais da base."""
    conn = get_connection()
    df = conn.execute(
        """
        SELECT
            COUNT(*) AS total_clientes,
            ROUND(SUM(Monetary), 2) AS receita_total,
            ROUND(AVG(Monetary), 2) AS ticket_medio,
            ROUND(AVG(Recency), 1) AS recency_media,
            ROUND(AVG(Frequency), 2) AS frequency_media,
            SUM(CASE WHEN Frequency = 1 THEN 1 ELSE 0 END) AS clientes_1_compra,
            SUM(CASE WHEN Recency > 365 THEN 1 ELSE 0 END) AS clientes_em_risco
        FROM fato_rfm_clientes
    """
    ).df()

    row = df.iloc[0]
    return {
        "total_clientes": int(row["total_clientes"]),
        "receita_total_brl": float(row["receita_total"]),
        "ticket_medio_brl": float(row["ticket_medio"]),
        "recency_media_dias": float(row["recency_media"]),
        "frequency_media": float(row["frequency_media"]),
        "clientes_1_compra": int(row["clientes_1_compra"]),
        "pct_1_compra": round(row["clientes_1_compra"] / row["total_clientes"], 4),
        "clientes_em_risco": int(row["clientes_em_risco"]),
        "pct_em_risco": round(row["clientes_em_risco"] / row["total_clientes"], 4),
    }


def run_custom_sql(sql: str) -> dict[str, Any]:
    """Executa SQL customizado nos datamarts (apenas SELECT).

    Use com cuidado — apenas pra perguntas que não cabem nas tools dedicadas.

    Args:
        sql: Query SQL (apenas SELECT). Tabelas disponíveis:
            fato_rfm_clientes, fato_pedidos, dim_segmentos, dim_calendario.
    """
    sql_clean = sql.strip().lower()
    if not sql_clean.startswith(("select", "with")):
        return {"erro": "Apenas SELECT/WITH é permitido."}

    forbidden = ["insert", "update", "delete", "drop", "create", "alter", "attach"]
    if any(f in sql_clean for f in forbidden):
        return {"erro": "Operação não permitida (somente leitura)."}

    try:
        conn = get_connection()
        df = conn.execute(sql).df()
        # Limita a 100 linhas pra não inundar contexto
        if len(df) > 100:
            df = df.head(100)
        return {"rows": df.to_dict(orient="records"), "n_rows": len(df)}
    except Exception as e:
        return {"erro": str(e)}


# ──────────────────────────────────────────────────────────────────────────────
# Schema dos tools (para a API da Anthropic)
# ──────────────────────────────────────────────────────────────────────────────

TOOLS_SCHEMA = [
    {
        "name": "get_cluster_summary",
        "description": (
            "Retorna estatísticas agregadas dos 4 clusters: n clientes, "
            "recency/frequency/monetary médios, receita total, CLV médio, "
            "review score médio. Use quando o usuário pedir visão geral, "
            "comparação entre clusters ou diagnóstico."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "filter_by_state",
        "description": (
            "Filtra clientes por UF e opcionalmente por cluster. Retorna "
            "métricas agregadas. Use quando o usuário pergunta sobre um "
            "estado específico ou cruza estado+cluster."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "state": {"type": "string", "description": "Sigla do estado, ex: 'SP', 'RJ'"},
                "cluster_name": {
                    "type": "string",
                    "description": "Nome do cluster (opcional). Ex: 'Em Risco / Hibernando'",
                },
            },
            "required": ["state"],
        },
    },
    {
        "name": "revenue_concentration",
        "description": (
            "Calcula concentração de receita (Pareto) no top N% dos "
            "clientes. Use pra responder perguntas sobre concentração, "
            "Pareto, Gini, top X% etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "top_pct": {
                    "type": "number",
                    "description": "Fração 0.0-1.0 do topo. Default 0.20.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_top_customers",
        "description": (
            "Retorna top N clientes ordenados por CLV 12m projetado, "
            "opcionalmente filtrados por cluster."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cluster_name": {"type": "string", "description": "Cluster (opcional)"},
                "limit": {"type": "integer", "description": "Quantidade. Default 10."},
            },
            "required": [],
        },
    },
    {
        "name": "state_distribution",
        "description": "Top 10 estados por receita ou volume de clientes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": ["receita", "clientes"],
                    "description": "Métrica a agrupar. Default 'receita'.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "overall_kpis",
        "description": "KPIs globais da base (total clientes, receita, ticket médio, % em risco, etc.).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "run_custom_sql",
        "description": (
            "Executa SQL customizado de leitura nos datamarts. Use apenas "
            "quando nenhuma tool dedicada cobre a pergunta. Tabelas: "
            "fato_rfm_clientes, fato_pedidos, dim_segmentos, dim_calendario."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "Query SELECT/WITH"},
            },
            "required": ["sql"],
        },
    },
]


TOOL_FUNCTIONS = {
    "get_cluster_summary": get_cluster_summary,
    "filter_by_state": filter_by_state,
    "revenue_concentration": revenue_concentration,
    "get_top_customers": get_top_customers,
    "state_distribution": state_distribution,
    "overall_kpis": overall_kpis,
    "run_custom_sql": run_custom_sql,
}


def dispatch_tool(name: str, arguments: dict) -> str:
    """Dispatcher: chama a tool pelo nome e retorna o resultado como JSON string."""
    if name not in TOOL_FUNCTIONS:
        return json.dumps({"erro": f"Tool desconhecida: {name}"})
    try:
        result = TOOL_FUNCTIONS[name](**arguments)
        return json.dumps(result, default=str, ensure_ascii=False)
    except Exception as e:
        logger.exception(f"Erro ao executar {name}")
        return json.dumps({"erro": str(e)})
