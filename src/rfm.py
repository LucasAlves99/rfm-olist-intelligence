# src/rfm.py
"""Construção da tabela RFM a partir das tabelas Olist."""

# Standard library
import logging

# Third-party
import pandas as pd

logger = logging.getLogger(__name__)


def build_orders_base(data: dict, status_filter: str = "delivered") -> pd.DataFrame:
    """Constrói a base order-centric com filtro de status e merges necessários.

    Args:
        data: Dicionário com DataFrames (orders, customers, order_items, payments, reviews).
        status_filter: Status de pedido a filtrar (padrão: 'delivered').

    Returns:
        DataFrame com uma linha por pedido enriquecido com pagamentos, itens e reviews.
    """
    orders = data["orders"]
    customers = data["customers"]
    order_items = data["order_items"]
    payments = data["payments"]
    reviews = data["reviews"]

    # Filtra apenas pedidos entregues
    orders_delivered = orders[orders["order_status"] == status_filter].copy()
    logger.info(
        f"Pedidos com status='{status_filter}': "
        f"{len(orders_delivered):,} de {len(orders):,} total"
    )

    # Agrega valor por pedido (itens)
    items_value = order_items.groupby("order_id", as_index=False).agg(
        total_items_value=("price", "sum"),
        n_items=("order_item_id", "count"),
    )

    # Agrega valor por pedido (pagamentos)
    pay_value = payments.groupby("order_id", as_index=False).agg(
        total_payment=("payment_value", "sum"),
        n_payments=("payment_sequential", "max"),
    )

    # Agrega review (média por pedido — já deduplicada antes)
    rev_value = reviews.groupby("order_id", as_index=False).agg(
        review_score=("review_score", "mean"),
    )

    # Monta base order-centric
    orders_base = (
        orders_delivered[["order_id", "customer_id", "order_purchase_timestamp"]]
        .merge(items_value, on="order_id", how="left")
        .merge(pay_value, on="order_id", how="left")
        .merge(rev_value, on="order_id", how="left")
    )

    # Adiciona customer_unique_id e estado
    orders_base = orders_base.merge(
        customers[["customer_id", "customer_unique_id", "customer_state"]],
        on="customer_id",
        how="left",
    )

    # Monetary: prioriza total_payment; fallback para total_items_value
    orders_base["monetary_value"] = orders_base["total_payment"].fillna(
        orders_base["total_items_value"]
    )

    # Categoria dominante por pedido (defensivo: só se 'products' foi carregado).
    if "products" in data:
        orders_base = orders_base.merge(
            _dominant_category_per_order(order_items, data["products"]),
            on="order_id",
            how="left",
        )
        orders_base["product_category"] = orders_base["product_category"].fillna("Não informado")

    logger.info(f"orders_base construída: {len(orders_base):,} linhas")
    return orders_base


def _dominant_category_per_order(order_items: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    """Deriva uma categoria de produto por pedido (a do item de maior preço).

    Pedidos multi-categoria são reduzidos à categoria do item mais caro — uma
    simplificação razoável para leitura gerencial (a categoria que "puxa" o ticket).
    O nome em português (snake_case) é prettificado para exibição.

    Args:
        order_items: Itens de pedido (order_id, product_id, price).
        products: Catálogo de produtos (product_id, product_category_name).

    Returns:
        DataFrame com colunas [order_id, product_category] (1 linha por pedido).
    """
    items = order_items.merge(
        products[["product_id", "product_category_name"]], on="product_id", how="left"
    )
    dominant = (
        items.sort_values("price", ascending=False)
        .drop_duplicates(subset="order_id")[["order_id", "product_category_name"]]
        .copy()
    )
    dominant["product_category"] = (
        dominant["product_category_name"]
        .fillna("nao_informado")
        .str.replace("_", " ", regex=False)
        .str.title()
    )
    return dominant[["order_id", "product_category"]]


def build_cohort_retention(orders_base: pd.DataFrame) -> pd.DataFrame:
    """Constrói a matriz de cohort de retenção por safra de aquisição.

    Para cada cliente, a "safra" é o mês da 1ª compra (YYYY-MM). Para cada pedido,
    o índice de período é a diferença em meses entre o mês do pedido e a safra.
    O resultado é uma tabela tidy (1 linha por safra × período) com a contagem de
    clientes distintos retidos e o % sobre o tamanho da safra.

    Args:
        orders_base: Base order-centric com customer_unique_id e order_purchase_timestamp.

    Returns:
        DataFrame com colunas [Safra, MesIndice, Clientes_Retidos, Tamanho_Safra, Pct_Retencao].
    """
    df = orders_base[["customer_unique_id", "order_purchase_timestamp"]].copy()
    df["order_purchase_timestamp"] = pd.to_datetime(df["order_purchase_timestamp"])

    # Safra = mês da 1ª compra do cliente.
    first_purchase = df.groupby("customer_unique_id")["order_purchase_timestamp"].transform("min")
    df["Safra"] = first_purchase.dt.strftime("%Y-%m")

    # Índice de período em meses (0 = mês de aquisição).
    df["MesIndice"] = (
        (df["order_purchase_timestamp"].dt.year - first_purchase.dt.year) * 12
        + (df["order_purchase_timestamp"].dt.month - first_purchase.dt.month)
    ).astype("int16")

    # Clientes distintos por safra × período.
    cohort = (
        df.groupby(["Safra", "MesIndice"], as_index=False)["customer_unique_id"]
        .nunique()
        .rename(columns={"customer_unique_id": "Clientes_Retidos"})
    )

    # Tamanho da safra = clientes distintos no período 0.
    sizes = cohort[cohort["MesIndice"] == 0][["Safra", "Clientes_Retidos"]].rename(
        columns={"Clientes_Retidos": "Tamanho_Safra"}
    )
    cohort = cohort.merge(sizes, on="Safra", how="left")
    cohort["Pct_Retencao"] = (cohort["Clientes_Retidos"] / cohort["Tamanho_Safra"]).round(4)

    cohort = cohort.sort_values(["Safra", "MesIndice"]).reset_index(drop=True)
    logger.info(
        f"cohort de retenção construída: {cohort['Safra'].nunique()} safras × "
        f"{cohort['MesIndice'].max() + 1} períodos | {len(cohort):,} linhas"
    )
    return cohort


def build_rfm(data: dict, snapshot_date: str, status_filter: str = "delivered") -> pd.DataFrame:
    """Constrói a tabela RFM a partir das tabelas Olist.

    Args:
        data: Dicionário com as tabelas brutas (orders, customers, etc.).
        snapshot_date: Data de referência para cálculo da Recency (formato YYYY-MM-DD).
            Deve ser fixada e versionada — não usar max() dinâmico.
        status_filter: Status de pedido a filtrar.

    Returns:
        DataFrame com uma linha por customer_unique_id contendo:
            - Recency (int): Dias desde a última compra até a snapshot_date.
            - Frequency (int): Número de pedidos únicos entregues.
            - Monetary (float): Soma do valor pago.
            - Avg_Order_Value (float): Ticket médio por pedido.
            - Items (int): Total de itens comprados.
            - Avg_Review (float): Nota média de reviews (pode ter NaN).

    Raises:
        ValueError: Se snapshot_date for anterior à última compra dos dados.
    """
    snap = pd.Timestamp(snapshot_date)
    orders_base = build_orders_base(data, status_filter)

    # Valida snapshot
    max_date = orders_base["order_purchase_timestamp"].max()
    if max_date > snap:
        raise ValueError(
            f"snapshot_date '{snapshot_date}' é anterior à data máxima dos dados ({max_date.date()}). "
            "Ajuste o config.yaml ou filtre os dados."
        )

    rfm = orders_base.groupby("customer_unique_id", as_index=False).agg(
        Recency=("order_purchase_timestamp", lambda x: (snap - x.max()).days),
        Frequency=("order_id", "nunique"),
        Monetary=("monetary_value", "sum"),
        Avg_Order_Value=("monetary_value", "mean"),
        Items=("n_items", "sum"),
        Avg_Review=("review_score", "mean"),
    )

    logger.info(
        f"RFM construída: {len(rfm):,} clientes únicos | "
        f"Recency médio={rfm['Recency'].mean():.1f} dias | "
        f"Monetary médio=R${rfm['Monetary'].mean():.2f}"
    )
    return rfm
