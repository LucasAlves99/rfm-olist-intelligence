# src/export.py
"""Exportação tipada das tabelas para consumo no Power BI (Star Schema)."""

# Standard library
import logging
from pathlib import Path

# Third-party
import pandas as pd

logger = logging.getLogger(__name__)

# Formato BR esperado pelo Power BI PT-BR: ';' separador de campos, ',' decimal.
PBI_CSV_SEP = ";"
PBI_CSV_DECIMAL = ","
PBI_CSV_ENCODING = "utf-8-sig"  # BOM — necessário p/ PBI/Excel lerem acentos


def write_powerbi_csv(
    df: pd.DataFrame,
    output_path: str,
    encoding: str = PBI_CSV_ENCODING,
) -> None:
    """Escreve um DataFrame em CSV no formato esperado pelo Power BI PT-BR.

    Cria o diretório de destino se necessário e padroniza separador (';'),
    decimal (',') e encoding (utf-8-sig). Centraliza o I/O para evitar
    divergência de formato entre as tabelas exportadas.

    Args:
        df: DataFrame já tipado, pronto para exportação.
        output_path: Caminho de saída do CSV.
        encoding: Encoding do arquivo (padrão: 'utf-8-sig').
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(
        output_path,
        index=False,
        encoding=encoding,
        sep=PBI_CSV_SEP,
        decimal=PBI_CSV_DECIMAL,
    )
    logger.info(f"Exportado: {output_path} ({len(df):,} linhas × {df.shape[1]} colunas)")


def export_rfm_to_powerbi(
    rfm: pd.DataFrame,
    output_path: str,
    encoding: str = PBI_CSV_ENCODING,
) -> None:
    """Exporta a tabela RFM com tipagem explícita para Power BI.

    A função:
    - Força tipos numéricos otimizados (int16/int32/float32)
    - Padroniza categorias como string
    - Adiciona metadados de rastreabilidade (dt_exportacao, versao_modelo)
    - Usa encoding utf-8-sig (BOM) para compatibilidade com PBI/Excel

    Args:
        rfm: DataFrame RFM segmentado e com clusters nomeados.
        output_path: Caminho de saída do CSV.
        encoding: Encoding do arquivo (padrão: 'utf-8-sig' para Power BI).
    """
    df = rfm.copy()

    # ── Identificadores ──────────────────────────────────────────────────────
    df["customer_unique_id"] = df["customer_unique_id"].astype(str)

    # ── Métricas RFM ─────────────────────────────────────────────────────────
    df["Recency"] = df["Recency"].astype("int32")
    df["Frequency"] = df["Frequency"].astype("int16")
    df["Monetary"] = df["Monetary"].round(2).astype("float32")

    if "Avg_Order_Value" in df.columns:
        df["Avg_Order_Value"] = df["Avg_Order_Value"].round(2).astype("float32")
    if "Avg_Review" in df.columns:
        df["Avg_Review"] = df["Avg_Review"].round(2).astype("float32")
    if "CLV_12m" in df.columns:
        df["CLV_12m"] = df["CLV_12m"].round(2).astype("float32")

    # ── Scores RFM ───────────────────────────────────────────────────────────
    for col in ["R_score", "F_score", "M_score", "RFM_score"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int8")

    # ── Categorias (string explícita — pandas Category não é bem lido pelo PBI) ──
    cat_cols = [
        "RFM_bucket",
        "RFM_segment",
        "Revenue_segment",
        "Recency_segment",
        "Strategic_segment",
        "Cluster_Name",
    ]
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].astype(str)

    # ── Cluster ID ───────────────────────────────────────────────────────────
    if "Cluster" in df.columns:
        df["Cluster"] = df["Cluster"].astype("int8")

    # ── Metadados de rastreabilidade ─────────────────────────────────────────
    df["dt_exportacao"] = pd.Timestamp.today().normalize().strftime("%Y-%m-%d")
    df["versao_modelo"] = "v1.0"

    write_powerbi_csv(df, output_path, encoding=encoding)


def export_orders_to_powerbi(
    orders_enriched: pd.DataFrame,
    output_path: str,
    encoding: str = PBI_CSV_ENCODING,
) -> None:
    """Exporta a tabela de pedidos enriquecida para Power BI (fato_pedidos).

    Args:
        orders_enriched: DataFrame de pedidos com cluster e segmento.
        output_path: Caminho de saída do CSV.
        encoding: Encoding do arquivo.
    """
    df = orders_enriched.copy()

    # Tipos
    df["order_id"] = df["order_id"].astype(str)
    df["customer_unique_id"] = df["customer_unique_id"].astype(str)

    if "total_payment" in df.columns:
        df["total_payment"] = df["total_payment"].round(2).astype("float32")
    if "total_items_value" in df.columns:
        df["total_items_value"] = df["total_items_value"].round(2).astype("float32")
    if "review_score" in df.columns:
        df["review_score"] = df["review_score"].round(1).astype("float32")
    if "n_items" in df.columns:
        df["n_items"] = pd.to_numeric(df["n_items"], errors="coerce").astype("Int16")
    if "Cluster" in df.columns:
        df["Cluster"] = df["Cluster"].astype("Int8")
    if "Cluster_Name" in df.columns:
        df["Cluster_Name"] = df["Cluster_Name"].astype(str)
    if "payment_type" in df.columns:
        df["payment_type"] = df["payment_type"].astype(str)
    if "product_category" in df.columns:
        df["product_category"] = df["product_category"].astype(str)

    # Data de compra como string ISO
    if "order_purchase_timestamp" in df.columns:
        df["order_purchase_timestamp"] = pd.to_datetime(df["order_purchase_timestamp"]).dt.strftime(
            "%Y-%m-%d"
        )

    write_powerbi_csv(df, output_path, encoding=encoding)


def build_dim_segmentos() -> pd.DataFrame:
    """Cria a tabela dimensão com metadados dos clusters para Star Schema no PBI.

    Os 4 nomes refletem perfis distintos da base Olist:
    - Campeões: alta F + alto M + R recente (raros, mas valiosíssimos)
    - Big Spenders (Não-Recorrentes): alto ticket único, sem recorrência
    - Novos / Ocasionais: maioria da base, 1 compra, valor baixo, R recente
    - Em Risco / Hibernando: clientes antigos sem retornar (R alta)

    Returns:
        DataFrame com uma linha por cluster, incluindo cor, ação CRM e prioridade.
    """
    return pd.DataFrame(
        {
            "Cluster_Name": [
                "Campeões",
                "Big Spenders (Não-Recorrentes)",
                "Novos / Ocasionais",
                "Em Risco / Hibernando",
            ],
            "Descricao": [
                "Alta frequência E alto valor — base de elite, recorrência real",
                "Alto valor de compra mas sem recorrência — clientes premium 'one-shot'",
                "Compra única recente, valor baixo — maior parte da base Olist",
                "Recência alta, sem comprar há muito — alto risco de churn",
            ],
            "Cor_Hex": ["#5E6AD2", "#BF6FF8", "#F2C94C", "#E5484D"],
            "Acao_CRM": [
                "Programa VIP, ofertas exclusivas, embaixadores da marca",
                "Conversão para recorrência: ofertas categoria-aderentes, upsell pós-venda",
                "Incentivo à segunda compra: cupom 'volte logo', cross-sell, onboarding",
                "Win-back urgente: e-mail de reativação, desconto agressivo, pesquisa de churn",
            ],
            "Prioridade": [1, 1, 3, 2],
            "Cor_Power_BI": ["Iris", "Mauve", "Gold", "Radish"],
        }
    )


def build_dim_calendario(start: str = "2016-01-01", end: str = "2018-12-31") -> pd.DataFrame:
    """Cria uma tabela calendário completa para o Power BI.

    Args:
        start: Data inicial no formato YYYY-MM-DD.
        end: Data final no formato YYYY-MM-DD.

    Returns:
        DataFrame com uma linha por dia e colunas de hierarquia de datas.
    """
    dates = pd.date_range(start=start, end=end, freq="D")
    df = pd.DataFrame({"Data": dates.strftime("%Y-%m-%d")})

    dt = dates
    df["Ano"] = dt.year.astype("int16")
    df["Mes"] = dt.month.astype("int8")
    df["Dia"] = dt.day.astype("int8")
    df["Trimestre"] = dt.quarter.astype("int8")
    df["AnoMes"] = dt.strftime("%Y-%m")
    df["NomeMes"] = dt.strftime("%B")
    df["DiaSemana"] = dt.day_name()
    df["NumDiaSemana"] = (dt.dayofweek + 1).astype("int8")  # 1=Segunda
    df["FimDeSemana"] = dt.dayofweek.isin([5, 6])

    logger.info(f"dim_calendario criada: {len(df):,} datas ({start} → {end})")
    return df
