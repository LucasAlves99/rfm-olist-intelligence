"""
Modelo de propensão à RECOMPRA (repeat-purchase) — Olist / RFM.

Objetivo de negócio: prever, a partir das características da PRIMEIRA compra,
se o cliente vai se tornar recorrente (>= 2 pedidos). Alimenta a priorização
de CRM (quem entre os Novos/Ocasionais tem maior chance de voltar).

Rigor metodológico:
- SEM data leakage: usa apenas features da 1ª compra. NÃO usa Frequency,
  Monetary total, CLV, Cluster, scores RFM (todos derivados do histórico
  completo => vazariam o alvo).
- Classe rara (~3% recompram) => métricas primárias = F1 (classe positiva),
  PR-AUC (average precision) e balanced accuracy. Acurácia pura é enganosa
  (prever "ninguém recompra" já dá ~97%).
- Comparação de vários algoritmos com StratifiedKFold CV.
- Diagnóstico de OVERFIT: gap entre treino, CV e teste.
- Tuning de threshold via probabilidades out-of-fold (sem vazar o teste).
- Seleção do melhor por (F1 CV) penalizando overfit, depois avaliação final
  num conjunto de teste hold-out nunca visto.

A infraestrutura de treino (modelos, CV, seleção, threshold, avaliação,
persistência) é compartilhada com train_review_model.py via pipeline/ml_common.py.

Uso:
    "C:/Users/Luk/anaconda3/python.exe" pipeline/train_repeat_model.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ml_common import (  # noqa: E402
    RANDOM_STATE,
    build_candidates,
    evaluate_holdout,
    make_preprocessor,
    permutation_top,
    run_cross_validation,
    save_artifacts,
    select_best,
    tune_threshold,
)

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "powerbi" / "fato_pedidos.csv"
OUT_MODEL = ROOT / "models" / "repeat_model.pkl"
OUT_METRICS = ROOT / "models" / "repeat_model_metrics.json"

NUMERIC = [
    "first_payment",
    "first_items_value",
    "n_items",
    "n_payments",
    "review_score",
    "freight_proxy",
    "avg_item_value",
    "review_missing",
    "month",
    "quarter",
    "dow",
    "year",
]
CATEG = ["state", "category"]


# ───────────────────────────── 1. Features (1ª compra) ─────────────────────────────
def build_features() -> tuple[pd.DataFrame, pd.Series]:
    """Constrói features da PRIMEIRA compra de cada cliente + alvo (recomprou?)."""
    p = pd.read_csv(DATA, sep=";", decimal=",", encoding="utf-8-sig")
    p["order_purchase_timestamp"] = pd.to_datetime(p["order_purchase_timestamp"])

    # alvo: cliente com >= 2 pedidos no total
    total_orders = p.groupby("customer_unique_id").size()
    target = (total_orders >= 2).astype(int).rename("repeat")

    # 1º pedido por cliente (ordena por data, pega o primeiro)
    first = (
        p.sort_values("order_purchase_timestamp")
        .groupby("customer_unique_id", as_index=False)
        .first()
        .set_index("customer_unique_id")
    )

    df = pd.DataFrame(index=first.index)
    df["first_payment"] = first["total_payment"]
    df["first_items_value"] = first["total_items_value"]
    df["n_items"] = first["n_items"]
    df["n_payments"] = first["n_payments"]
    df["review_score"] = first["review_score"]
    df["freight_proxy"] = (first["total_payment"] - first["total_items_value"]).clip(lower=0)
    df["avg_item_value"] = first["total_items_value"] / first["n_items"].replace(0, np.nan)
    df["review_missing"] = first["review_score"].isna().astype(int)
    df["review_score"] = df["review_score"].fillna(first["review_score"].median())
    # temporais da aquisição
    ts = first["order_purchase_timestamp"]
    df["month"] = ts.dt.month
    df["quarter"] = ts.dt.quarter
    df["dow"] = ts.dt.dayofweek
    df["year"] = ts.dt.year
    # categóricas
    df["state"] = first["customer_state"].astype(str)
    df["category"] = first["product_category"].astype(str)

    y = target.reindex(df.index).fillna(0).astype(int)
    return df, y


def candidate_models():
    return build_candidates(
        lambda: make_preprocessor(NUMERIC, CATEG),
        rf_kwargs={"n_estimators": 300, "max_depth": 12, "min_samples_leaf": 30},
        hgb_kwargs={
            "max_depth": 4,
            "learning_rate": 0.06,
            "max_iter": 400,
            "l2_regularization": 1.0,
        },
        include_smote=True,
    )


def main() -> None:
    print("=" * 78)
    print("MODELO DE PROPENSÃO À RECOMPRA — Olist (sem leakage, 1ª compra)")
    print("=" * 78)

    X, y = build_features()
    print(
        f"\nAmostras: {len(X):,} | recompradores: {y.sum():,} ({y.mean():.2%}) | features: {X.shape[1]}"
    )
    print(f"Features numéricas: {len(NUMERIC)} | categóricas: {len(CATEG)} (state, category)")

    # hold-out de teste (estratificado) — nunca usado em CV nem tuning
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
    )
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    models = candidate_models()
    results = run_cross_validation(models, X_tr, y_tr, cv)
    best_name = select_best(results)

    best = models[best_name]
    best_thr = tune_threshold(best, X_tr, y_tr, cv)

    proba_te, test_metrics = evaluate_holdout(
        best, X_tr, y_tr, X_te, y_te, best_thr, best_name,
        target_names=["nao_recompra", "recompra"],
    )
    print(
        f"\nPR-AUC contextual: baseline (taxa positiva) = {y.mean():.3f} | "
        f"PR-AUC teste = {average_precision_score(y_te, proba_te):.3f} | "
        f"ROC-AUC teste = {roc_auc_score(y_te, proba_te):.3f}"
    )

    imp = permutation_top(best, X_te, y_te, list(X.columns), n=8)

    metrics = {
        "problem": "repeat_purchase_propensity",
        "n_samples": int(len(X)),
        "positive_rate": round(float(y.mean()), 4),
        "random_state": RANDOM_STATE,
        "cv_folds": 5,
        "best_model": best_name,
        "best_threshold": round(best_thr, 4),
        "cv_results": results,
        "test": test_metrics,
        "top_features": [{"feature": f, "importance": round(float(v), 5)} for f, v in imp],
    }
    save_artifacts(best, best_thr, list(X.columns), metrics, OUT_MODEL, OUT_METRICS)


if __name__ == "__main__":
    main()
