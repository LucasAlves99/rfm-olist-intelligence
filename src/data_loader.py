# src/data_loader.py
"""Carrega os CSVs da Olist em DataFrames pandas.

Espera os arquivos em data/raw/ (configurável via config.yaml).
Para uso em Colab/Kaggle, usar o notebook SELF_CONTAINED.ipynb.
"""

# Standard library
import logging
from pathlib import Path

# Third-party
import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_FILES = {
    "orders": "olist_orders_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
}

# Arquivos opcionais: enriquecem fato_pedidos com categoria de produto.
# Ausência NÃO interrompe o pipeline (categoria entra como coluna defensiva).
OPTIONAL_FILES = {
    "products": "olist_products_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

PARSE_DATES = {
    "orders": ["order_purchase_timestamp", "order_delivered_customer_date"],
}


def load_all_data(raw_dir: str = "data/raw") -> dict:
    """Carrega os 5 datasets Olist como DataFrames pandas.

    Args:
        raw_dir: Pasta contendo os 5 CSVs Olist (default: data/raw).

    Returns:
        Dicionário com DataFrames: orders, customers, order_items,
        payments, reviews (obrigatórios) e, se presentes, products e
        category_translation (opcionais, para categoria de produto).

    Raises:
        FileNotFoundError: Se a pasta ou algum dos 5 CSVs obrigatórios não existir.
    """
    raw_path = Path(raw_dir).resolve()
    if not raw_path.is_dir():
        raise FileNotFoundError(
            f"Pasta de dados não encontrada: {raw_path}\n"
            "Baixe o dataset em https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce "
            "e extraia em data/raw/."
        )

    data: dict[str, pd.DataFrame] = {}
    for key, filename in REQUIRED_FILES.items():
        path = raw_path / filename
        if not path.exists():
            raise FileNotFoundError(f"Arquivo ausente: {path}")
        kwargs = {"parse_dates": PARSE_DATES[key]} if key in PARSE_DATES else {}
        data[key] = pd.read_csv(path, **kwargs)
        logger.info(f"{key}: {data[key].shape[0]:,} linhas × {data[key].shape[1]} colunas")

    # Opcionais: não falham se ausentes (mantém pipeline reproduzível em ambientes mínimos).
    for key, filename in OPTIONAL_FILES.items():
        path = raw_path / filename
        if path.exists():
            data[key] = pd.read_csv(path)
            logger.info(f"{key}: {data[key].shape[0]:,} linhas × {data[key].shape[1]} colunas")
        else:
            logger.warning(f"Opcional ausente (categoria desabilitada): {path}")

    return data


# Alias retrocompatível: o notebook REFATORADO importa load_from_project_root.
load_from_project_root = load_all_data
