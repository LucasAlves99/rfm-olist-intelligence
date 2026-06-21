# tests/test_data_loader.py
"""Testes para src/data_loader.py (carregamento dos CSVs Olist)."""

import pandas as pd
import pytest

from src.data_loader import OPTIONAL_FILES, REQUIRED_FILES, load_all_data


def _write_minimal_dataset(raw_dir, with_optional=False):
    """Cria CSVs mínimos com os nomes esperados pelo loader."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    frames = {
        "orders": pd.DataFrame(
            {
                "order_id": ["o1"],
                "customer_id": ["c1"],
                "order_status": ["delivered"],
                "order_purchase_timestamp": ["2018-01-01 10:00:00"],
                "order_delivered_customer_date": ["2018-01-05 10:00:00"],
            }
        ),
        "customers": pd.DataFrame(
            {"customer_id": ["c1"], "customer_unique_id": ["u1"], "customer_state": ["SP"]}
        ),
        "order_items": pd.DataFrame(
            {"order_id": ["o1"], "order_item_id": [1], "product_id": ["p1"], "price": [10.0]}
        ),
        "payments": pd.DataFrame(
            {"order_id": ["o1"], "payment_sequential": [1], "payment_value": [10.0]}
        ),
        "reviews": pd.DataFrame(
            {"order_id": ["o1"], "review_score": [5], "review_creation_date": ["2018-01-06"]}
        ),
    }
    for key, df in frames.items():
        df.to_csv(raw_dir / REQUIRED_FILES[key], index=False)

    if with_optional:
        pd.DataFrame({"product_id": ["p1"], "product_category_name": ["cama_mesa_banho"]}).to_csv(
            raw_dir / OPTIONAL_FILES["products"], index=False
        )
        pd.DataFrame(
            {"product_category_name": ["cama_mesa_banho"], "product_category_name_english": ["bed"]}
        ).to_csv(raw_dir / OPTIONAL_FILES["category_translation"], index=False)


def test_load_all_data_carrega_obrigatorios(tmp_path):
    raw = tmp_path / "raw"
    _write_minimal_dataset(raw)

    data = load_all_data(str(raw))

    assert set(REQUIRED_FILES).issubset(data)
    assert "products" not in data  # opcional ausente
    # parse_dates aplicado em orders
    assert pd.api.types.is_datetime64_any_dtype(data["orders"]["order_purchase_timestamp"])


def test_load_all_data_inclui_opcionais_quando_presentes(tmp_path):
    raw = tmp_path / "raw"
    _write_minimal_dataset(raw, with_optional=True)

    data = load_all_data(str(raw))

    assert "products" in data
    assert "category_translation" in data


def test_load_all_data_pasta_inexistente():
    with pytest.raises(FileNotFoundError):
        load_all_data("pasta/que/nao/existe")


def test_load_all_data_arquivo_obrigatorio_ausente(tmp_path):
    raw = tmp_path / "raw"
    _write_minimal_dataset(raw)
    (raw / REQUIRED_FILES["reviews"]).unlink()  # remove um obrigatório

    with pytest.raises(FileNotFoundError):
        load_all_data(str(raw))
