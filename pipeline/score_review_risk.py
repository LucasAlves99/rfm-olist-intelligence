"""
Batch scoring do modelo de review ruim -> agregado por UF para o Power BI.

Carrega o modelo treinado (models/review_model.pkl), escora todos os pedidos
entregues e exporta data/powerbi/risco_review_uf.csv com o % de pedidos em
alto risco de insatisfação por estado (onde priorizar service recovery).

Uso:
    "C:/Users/Luk/anaconda3/python.exe" pipeline/score_review_risk.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.export import write_powerbi_csv  # noqa: E402
from train_review_model import build_features  # noqa: E402

OUT = ROOT / "data" / "powerbi" / "risco_review_uf.csv"


def main() -> None:
    X, _ = build_features()
    obj = joblib.load(ROOT / "models" / "review_model.pkl")
    model, thr = obj["model"], obj["threshold"]

    proba = model.predict_proba(X)[:, 1]
    df = X[["customer_state"]].copy()
    df["alto_risco"] = (proba >= thr).astype(int)

    agg = (
        df.groupby("customer_state")
        .agg(Pedidos=("alto_risco", "size"), Alto_Risco=("alto_risco", "sum"))
        .reset_index()
        .rename(columns={"customer_state": "UF"})
    )
    agg["Pct_Alto_Risco"] = (agg["Alto_Risco"] / agg["Pedidos"]).round(4)
    agg = agg.sort_values("Pct_Alto_Risco", ascending=False)

    write_powerbi_csv(agg, OUT)
    print(f"Exportado: {OUT}")
    print(agg.head(10).to_string(index=False))
    print(
        f"\nThreshold usado: {thr:.3f} | total pedidos: {agg.Pedidos.sum():,} | "
        f"% alto risco global: {agg.Alto_Risco.sum()/agg.Pedidos.sum():.1%}"
    )


if __name__ == "__main__":
    main()
