# src/utils.py
"""Funções utilitárias reutilizáveis do projeto RFM Olist."""

# Standard library
import logging

# Third-party
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def gini_coefficient(values: pd.Series) -> float:
    """Calcula o Coeficiente de Gini para uma distribuição.

    Args:
        values: Série de valores não-negativos (ex: Monetary).

    Returns:
        Gini entre 0 (igualdade perfeita) e 1 (desigualdade extrema).
    """
    arr = np.sort(values.dropna().values)
    if len(arr) == 0 or arr.sum() == 0:
        return 0.0
    n = len(arr)
    idx = np.arange(1, n + 1)
    return float((2 * (idx * arr).sum()) / (n * arr.sum()) - (n + 1) / n)


def lorenz_curve(values: pd.Series) -> pd.DataFrame:
    """Calcula os pontos da Curva de Lorenz.

    Args:
        values: Série de valores monetários.

    Returns:
        DataFrame com colunas 'cumulative_customers_pct' e 'cumulative_monetary_pct'.
    """
    sorted_vals = values.sort_values().reset_index(drop=True)
    n = len(sorted_vals)
    df = pd.DataFrame(
        {
            "cumulative_customers_pct": ((sorted_vals.index + 1) / n) * 100,
            "cumulative_monetary_pct": (sorted_vals.cumsum() / sorted_vals.sum()) * 100,
        }
    )
    return df


def describe_skew(s: pd.Series) -> pd.Series:
    """Retorna estatísticas descritivas incluindo assimetria.

    Args:
        s: Série numérica.

    Returns:
        Série com count, mean, median, std, min, p25, p75, p95, max, skew.
    """
    return pd.Series(
        {
            "count": s.count(),
            "mean": s.mean(),
            "median": s.median(),
            "std": s.std(),
            "min": s.min(),
            "p25": s.quantile(0.25),
            "p75": s.quantile(0.75),
            "p95": s.quantile(0.95),
            "max": s.max(),
            "skew": s.skew(),
        }
    )
