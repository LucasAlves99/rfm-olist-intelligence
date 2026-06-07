# tests/test_rfm.py
"""Testes para src/rfm.py."""

import pandas as pd
import pytest
from src.rfm import build_rfm, build_orders_base


def make_mock_data() -> dict:
    """Cria um dataset mock mínimo para testes."""
    orders = pd.DataFrame(
        {
            "order_id": ["o1", "o2", "o3", "o4"],
            "customer_id": ["c1", "c2", "c1", "c3"],
            "order_status": ["delivered", "delivered", "delivered", "canceled"],
            "order_purchase_timestamp": pd.to_datetime(
                ["2018-01-01", "2018-03-15", "2018-06-01", "2018-07-01"]
            ),
        }
    )
    customers = pd.DataFrame(
        {
            "customer_id": ["c1", "c2", "c3"],
            "customer_unique_id": ["u1", "u2", "u3"],
            "customer_state": ["SP", "RJ", "MG"],
        }
    )
    order_items = pd.DataFrame(
        {
            "order_id": ["o1", "o2", "o3"],
            "order_item_id": [1, 1, 1],
            "price": [100.0, 200.0, 150.0],
        }
    )
    payments = pd.DataFrame(
        {
            "order_id": ["o1", "o2", "o3"],
            "payment_value": [110.0, 210.0, 160.0],
            "payment_sequential": [1, 1, 1],
        }
    )
    reviews = pd.DataFrame(
        {
            "order_id": ["o1", "o2", "o3"],
            "review_score": [5, 4, 5],
            "review_creation_date": pd.to_datetime(["2018-01-10", "2018-03-20", "2018-06-10"]),
        }
    )
    return {
        "orders": orders,
        "customers": customers,
        "order_items": order_items,
        "payments": payments,
        "reviews": reviews,
    }


class TestBuildRfm:
    def test_has_required_columns(self):
        """RFM deve ter as 3 colunas obrigatórias."""
        data = make_mock_data()
        rfm = build_rfm(data, snapshot_date="2018-09-04")
        assert {"Recency", "Frequency", "Monetary"}.issubset(rfm.columns)

    def test_one_row_per_unique_customer(self):
        """Deve ter uma linha por customer_unique_id."""
        data = make_mock_data()
        rfm = build_rfm(data, snapshot_date="2018-09-04")
        assert rfm["customer_unique_id"].is_unique

    def test_recency_is_non_negative(self):
        """Recência deve ser >= 0."""
        data = make_mock_data()
        rfm = build_rfm(data, snapshot_date="2018-09-04")
        assert (rfm["Recency"] >= 0).all()

    def test_frequency_is_positive(self):
        """Frequency deve ser >= 1."""
        data = make_mock_data()
        rfm = build_rfm(data, snapshot_date="2018-09-04")
        assert (rfm["Frequency"] >= 1).all()

    def test_monetary_is_positive(self):
        """Monetary deve ser > 0."""
        data = make_mock_data()
        rfm = build_rfm(data, snapshot_date="2018-09-04")
        assert (rfm["Monetary"] > 0).all()

    def test_filters_only_delivered(self):
        """Deve ignorar pedidos com status != 'delivered'."""
        data = make_mock_data()
        rfm = build_rfm(data, snapshot_date="2018-09-04")
        # u3 tem apenas pedido cancelado → não deve aparecer no RFM
        assert "u3" not in rfm["customer_unique_id"].values

    def test_repeated_customer_aggregated(self):
        """Cliente com 2 pedidos (u1) deve ter Frequency=2."""
        data = make_mock_data()
        rfm = build_rfm(data, snapshot_date="2018-09-04")
        u1 = rfm[rfm["customer_unique_id"] == "u1"].iloc[0]
        assert u1["Frequency"] == 2

    def test_snapshot_before_max_date_raises(self):
        """Snapshot anterior à data máxima deve lançar ValueError."""
        data = make_mock_data()
        with pytest.raises(ValueError, match="snapshot_date"):
            build_rfm(data, snapshot_date="2017-01-01")
