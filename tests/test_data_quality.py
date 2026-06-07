# tests/test_data_quality.py
"""Testes para src/data_quality.py."""

import pandas as pd
import pytest
from src.data_quality import (
    check_orders,
    check_customers,
    deduplicate_reviews,
    validate_snapshot,
    quality_report,
)


class TestCheckOrders:
    def test_valid_orders_passes(self):
        orders = pd.DataFrame(
            {
                "order_id": ["o1", "o2", "o3"],
                "customer_id": ["c1", "c2", "c3"],
                "order_purchase_timestamp": pd.to_datetime(
                    ["2018-01-01", "2018-02-01", "2018-03-01"]
                ),
            }
        )
        check_orders(orders)  # Não deve lançar

    def test_duplicate_order_id_raises(self):
        orders = pd.DataFrame(
            {
                "order_id": ["o1", "o1"],
                "customer_id": ["c1", "c2"],
                "order_purchase_timestamp": pd.to_datetime(["2018-01-01", "2018-01-02"]),
            }
        )
        with pytest.raises(AssertionError, match="Duplicatas em order_id"):
            check_orders(orders)

    def test_null_date_raises(self):
        orders = pd.DataFrame(
            {
                "order_id": ["o1", "o2"],
                "customer_id": ["c1", "c2"],
                "order_purchase_timestamp": [pd.Timestamp("2018-01-01"), pd.NaT],
            }
        )
        with pytest.raises(AssertionError, match="Datas faltantes"):
            check_orders(orders)


class TestCheckCustomers:
    def test_valid_customers_passes(self):
        customers = pd.DataFrame(
            {
                "customer_id": ["c1", "c2"],
                "customer_unique_id": ["u1", "u2"],
            }
        )
        check_customers(customers)  # Não deve lançar

    def test_duplicate_customer_id_raises(self):
        customers = pd.DataFrame(
            {
                "customer_id": ["c1", "c1"],
                "customer_unique_id": ["u1", "u2"],
            }
        )
        with pytest.raises(AssertionError, match="customer_id duplicado"):
            check_customers(customers)


class TestDeduplicateReviews:
    def test_removes_duplicates(self):
        reviews = pd.DataFrame(
            {
                "order_id": ["o1", "o1", "o2"],
                "review_score": [3, 5, 4],
                "review_creation_date": pd.to_datetime(["2018-01-01", "2018-01-10", "2018-02-01"]),
            }
        )
        result = deduplicate_reviews(reviews)
        assert len(result) == 2
        assert result["order_id"].is_unique

    def test_keeps_latest_review(self):
        reviews = pd.DataFrame(
            {
                "order_id": ["o1", "o1"],
                "review_score": [3, 5],
                "review_creation_date": pd.to_datetime(["2018-01-01", "2018-01-10"]),
            }
        )
        result = deduplicate_reviews(reviews)
        assert result.iloc[0]["review_score"] == 5

    def test_no_duplicates_unchanged(self):
        reviews = pd.DataFrame(
            {
                "order_id": ["o1", "o2"],
                "review_score": [4, 5],
                "review_creation_date": pd.to_datetime(["2018-01-01", "2018-02-01"]),
            }
        )
        result = deduplicate_reviews(reviews)
        assert len(result) == 2


class TestValidateSnapshot:
    def test_valid_snapshot_passes(self):
        orders = pd.DataFrame(
            {
                "order_purchase_timestamp": pd.to_datetime(["2018-08-01", "2018-09-03"]),
            }
        )
        validate_snapshot(orders, pd.Timestamp("2018-09-04"))  # Não deve lançar

    def test_orders_after_snapshot_raises(self):
        orders = pd.DataFrame(
            {
                "order_purchase_timestamp": pd.to_datetime(["2018-09-05", "2018-10-01"]),
            }
        )
        with pytest.raises(AssertionError, match="posteriores à snapshot_date"):
            validate_snapshot(orders, pd.Timestamp("2018-09-04"))


class TestQualityReport:
    def test_returns_dict(self):
        df = pd.DataFrame({"a": [1, 2, None], "b": ["x", "y", "z"]})
        result = quality_report(df, "test_table")
        assert isinstance(result, dict)
        assert result["tabela"] == "test_table"
        assert result["linhas"] == 3
        assert result["nulls_por_coluna"]["a"] == 1
