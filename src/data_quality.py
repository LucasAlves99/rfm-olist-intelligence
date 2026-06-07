# src/data_quality.py
"""Validações e quality checks para as tabelas Olist."""

# Standard library
import logging

# Third-party
import pandas as pd

logger = logging.getLogger(__name__)


def check_orders(orders: pd.DataFrame) -> None:
    """Valida a tabela de pedidos.

    Args:
        orders: DataFrame de pedidos.

    Raises:
        AssertionError: Se houver duplicatas em order_id ou datas faltantes.
    """
    assert orders["order_id"].is_unique, "Duplicatas em order_id!"
    assert (
        orders["order_purchase_timestamp"].notna().all()
    ), "Datas faltantes em order_purchase_timestamp!"
    logger.info(
        f"orders OK: {len(orders):,} linhas, "
        f"{orders['customer_id'].nunique():,} clientes únicos"
    )


def check_customers(customers: pd.DataFrame) -> None:
    """Valida a tabela de clientes.

    Args:
        customers: DataFrame de clientes.
    """
    assert customers["customer_id"].is_unique, "customer_id duplicado!"
    n_null = customers["customer_unique_id"].isna().sum()
    if n_null > 0:
        logger.warning(f"{n_null} customer_unique_id nulos detectados — serão removidos no merge")
    logger.info(
        f"customers OK: {len(customers):,} linhas, "
        f"{customers['customer_unique_id'].nunique():,} clientes únicos"
    )


def deduplicate_reviews(reviews: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicatas de reviews — mantém a mais recente por order_id.

    O dataset Olist tem múltiplos registros por order_id na tabela de reviews.
    Esse comportamento é conhecido e deve ser tratado antes do merge.

    Args:
        reviews: DataFrame de reviews bruto.

    Returns:
        DataFrame deduplicado com uma review por order_id.
    """
    before = len(reviews)
    reviews = (
        reviews.sort_values("review_creation_date")
        .drop_duplicates("order_id", keep="last")
        .reset_index(drop=True)
    )
    logger.info(f"Reviews deduplicadas: {before:,} → {len(reviews):,}")
    return reviews


def validate_snapshot(orders_base: pd.DataFrame, snapshot_date: pd.Timestamp) -> None:
    """Garante que não há pedidos posteriores à snapshot_date.

    Args:
        orders_base: DataFrame de pedidos filtrados.
        snapshot_date: Data de referência do RFM.

    Raises:
        AssertionError: Se houver pedidos após a snapshot.
    """
    max_date = orders_base["order_purchase_timestamp"].max()
    assert max_date <= snapshot_date, (
        f"Pedidos posteriores à snapshot_date detectados! "
        f"max={max_date}, snapshot={snapshot_date}"
    )
    logger.info(f"Snapshot OK: max_date={max_date.date()}, snapshot={snapshot_date.date()}")


def quality_report(df: pd.DataFrame, name: str) -> dict:
    """Gera relatório de qualidade de um DataFrame.

    Args:
        df: DataFrame a inspecionar.
        name: Nome da tabela (para identificação no relatório).

    Returns:
        Dicionário com linhas, nulos por coluna e tipos.
    """
    report = {
        "tabela": name,
        "linhas": len(df),
        "nulls_por_coluna": df.isna().sum().to_dict(),
        "tipos": df.dtypes.astype(str).to_dict(),
    }
    null_cols = {c: v for c, v in report["nulls_por_coluna"].items() if v > 0}
    if null_cols:
        logger.warning(f"[{name}] Colunas com nulos: {null_cols}")
    else:
        logger.info(f"[{name}] Sem nulos detectados ({report['linhas']:,} linhas)")
    return report
