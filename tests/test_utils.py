# tests/test_utils.py
"""Testes para src/utils.py."""

import pandas as pd
import pytest
from src.utils import gini_coefficient, lorenz_curve, describe_skew


class TestGiniCoefficient:
    def test_perfect_equality(self):
        """Distribuição igual deve ter Gini = 0."""
        s = pd.Series([10, 10, 10, 10])
        assert gini_coefficient(s) == pytest.approx(0, abs=1e-10)

    def test_extreme_inequality(self):
        """Quase tudo concentrado em um cliente → Gini próximo de 1."""
        s = pd.Series([0, 0, 0, 0, 100])
        assert gini_coefficient(s) > 0.7

    def test_handles_empty_series(self):
        """Série vazia deve retornar 0.0."""
        assert gini_coefficient(pd.Series([], dtype=float)) == 0.0

    def test_handles_all_zeros(self):
        """Série com todos zeros deve retornar 0.0."""
        assert gini_coefficient(pd.Series([0, 0, 0])) == 0.0

    def test_handles_nan(self):
        """NaNs devem ser ignorados no cálculo."""
        s = pd.Series([10.0, float("nan"), 10.0, 10.0])
        result = gini_coefficient(s)
        assert 0 <= result <= 1

    def test_returns_float(self):
        """Deve retornar um float."""
        s = pd.Series([1, 2, 3, 4, 5])
        assert isinstance(gini_coefficient(s), float)

    def test_real_distribution(self):
        """Distribuição típica de RFM deve ter Gini entre 0.3 e 0.9."""
        import numpy as np

        rng = np.random.default_rng(42)
        s = pd.Series(rng.exponential(scale=200, size=1000))
        g = gini_coefficient(s)
        assert 0.3 < g < 0.9


class TestLorenzCurve:
    def test_returns_dataframe(self):
        """Deve retornar um DataFrame com as colunas esperadas."""
        s = pd.Series([1, 2, 3, 4, 5])
        df = lorenz_curve(s)
        assert isinstance(df, pd.DataFrame)
        assert "cumulative_customers_pct" in df.columns
        assert "cumulative_monetary_pct" in df.columns

    def test_starts_at_zero_ends_at_100(self):
        """Primeiro valor deve ser próximo de 0% e último próximo de 100%."""
        s = pd.Series([10, 20, 30, 40])
        df = lorenz_curve(s)
        assert df["cumulative_monetary_pct"].iloc[-1] == pytest.approx(100, abs=1e-5)

    def test_monotonically_increasing(self):
        """Curva deve ser monotonicamente crescente."""
        s = pd.Series([5, 15, 25, 55])
        df = lorenz_curve(s)
        assert (df["cumulative_monetary_pct"].diff().dropna() >= 0).all()


class TestDescribeSkew:
    def test_returns_all_stats(self):
        """Deve retornar todas as estatísticas esperadas."""
        s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        result = describe_skew(s)
        expected_keys = [
            "count",
            "mean",
            "median",
            "std",
            "min",
            "p25",
            "p75",
            "p95",
            "max",
            "skew",
        ]
        for key in expected_keys:
            assert key in result.index

    def test_correct_mean(self):
        s = pd.Series([2, 4, 6])
        result = describe_skew(s)
        assert result["mean"] == pytest.approx(4.0)
