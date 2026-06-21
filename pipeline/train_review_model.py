"""
Modelo de previsão de REVIEW RUIM (insatisfação) — Olist.

Objetivo de negócio: prever, no momento da ENTREGA (antes do cliente avaliar),
se o pedido vai receber review ruim (score <= 2). Permite *service recovery*
proativo (contato/cupom) nos pedidos de alto risco — alavanca de NPS/retenção.

Rigor metodológico:
- SEM data leakage: usa apenas o que é conhecido até a entrega (atraso, prazo,
  tempo de entrega, frete, preço, itens, categoria, UF, pagamento, sazonalidade).
  NÃO usa o próprio review nem nada posterior.
- Classe ~15% positiva (review ruim) => F1 (classe positiva), PR-AUC e balanced
  accuracy como métricas primárias; acurácia reportada mas não decisiva.
- Comparação de vários algoritmos com StratifiedKFold CV.
- Diagnóstico de OVERFIT: gap treino vs CV vs teste.
- Tuning de threshold via probabilidades out-of-fold (sem vazar o teste).
- Avaliação final em teste hold-out + análise de LIFT (valor de negócio).

A infraestrutura de treino (modelos, CV, seleção, threshold, avaliação,
persistência) é compartilhada com train_repeat_model.py via pipeline/ml_common.py.

Uso:
    "C:/Users/Luk/anaconda3/python.exe" pipeline/train_review_model.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
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
RAW = ROOT / "data" / "raw"
OUT_MODEL = ROOT / "models" / "review_model.pkl"
OUT_METRICS = ROOT / "models" / "review_model_metrics.json"

NUMERIC = [
    "atraso_dias",
    "tempo_entrega_dias",
    "prazo_estimado_dias",
    "atrasou",
    "price_total",
    "freight_total",
    "freight_ratio",
    "valor_por_item",
    "n_items",
    "n_sellers",
    "n_products",
    "payment_value",
    "installments",
    "n_payment_methods",
    "mes",
    "dow",
]
CATEG = ["cat", "customer_state", "payment_type"]


# ─────────────────────── 1. Feature engineering (até a entrega) ───────────────────────
def build_features() -> tuple[pd.DataFrame, pd.Series]:
    orders = pd.read_csv(RAW / "olist_orders_dataset.csv")
    items = pd.read_csv(RAW / "olist_order_items_dataset.csv")
    pays = pd.read_csv(RAW / "olist_order_payments_dataset.csv")
    revs = pd.read_csv(RAW / "olist_order_reviews_dataset.csv")
    custs = pd.read_csv(RAW / "olist_customers_dataset.csv")
    prods = pd.read_csv(RAW / "olist_products_dataset.csv")
    trans = pd.read_csv(RAW / "product_category_name_translation.csv")

    # só pedidos entregues e com datas válidas
    for c in [
        "order_purchase_timestamp",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]:
        orders[c] = pd.to_datetime(orders[c], errors="coerce")
    o = (
        orders[orders["order_status"] == "delivered"]
        .dropna(
            subset=[
                "order_delivered_customer_date",
                "order_estimated_delivery_date",
                "order_purchase_timestamp",
            ]
        )
        .copy()
    )

    o["atraso_dias"] = (
        o["order_delivered_customer_date"] - o["order_estimated_delivery_date"]
    ).dt.days
    o["tempo_entrega_dias"] = (
        o["order_delivered_customer_date"] - o["order_purchase_timestamp"]
    ).dt.days
    o["prazo_estimado_dias"] = (
        o["order_estimated_delivery_date"] - o["order_purchase_timestamp"]
    ).dt.days
    o["atrasou"] = (o["atraso_dias"] > 0).astype(int)
    o["mes"] = o["order_purchase_timestamp"].dt.month
    o["dow"] = o["order_purchase_timestamp"].dt.dayofweek

    # itens: agrega por pedido + categoria dominante (maior preço)
    prods = prods.merge(trans, on="product_category_name", how="left")
    prods["cat"] = prods["product_category_name_english"].fillna("desconhecida")
    items = items.merge(prods[["product_id", "cat"]], on="product_id", how="left")
    agg = (
        items.groupby("order_id")
        .agg(
            price_total=("price", "sum"),
            freight_total=("freight_value", "sum"),
            n_items=("order_item_id", "count"),
            n_sellers=("seller_id", "nunique"),
            n_products=("product_id", "nunique"),
        )
        .reset_index()
    )
    cat = items.sort_values("price", ascending=False).drop_duplicates("order_id")[
        ["order_id", "cat"]
    ]

    # pagamentos
    pa = (
        pays.groupby("order_id")
        .agg(
            payment_value=("payment_value", "sum"),
            installments=("payment_installments", "max"),
            n_payment_methods=("payment_sequential", "max"),
        )
        .reset_index()
    )
    ptype = pays.sort_values("payment_value", ascending=False).drop_duplicates("order_id")[
        ["order_id", "payment_type"]
    ]

    # reviews (alvo): dedup por pedido
    rv = revs.drop_duplicates("order_id")[["order_id", "review_score"]]

    # UF do cliente
    o = o.merge(custs[["customer_id", "customer_state"]], on="customer_id", how="left")

    df = (
        o.merge(agg, on="order_id", how="inner")
        .merge(cat, on="order_id", how="left")
        .merge(pa, on="order_id", how="left")
        .merge(ptype, on="order_id", how="left")
        .merge(rv, on="order_id", how="inner")
    )

    df["freight_ratio"] = df["freight_total"] / df["price_total"].replace(0, np.nan)
    df["valor_por_item"] = df["price_total"] / df["n_items"].replace(0, np.nan)

    y = (df["review_score"] <= 2).astype(int).rename("review_ruim")
    feats = df[NUMERIC + CATEG].copy()
    feats["cat"] = feats["cat"].astype(str)
    feats["customer_state"] = feats["customer_state"].astype(str)
    feats["payment_type"] = feats["payment_type"].astype(str)
    return feats, y


def candidate_models():
    return build_candidates(
        lambda: make_preprocessor(NUMERIC, CATEG),
        rf_kwargs={"n_estimators": 400, "max_depth": 14, "min_samples_leaf": 20},
        hgb_kwargs={
            "max_depth": 5,
            "learning_rate": 0.07,
            "max_iter": 500,
            "l2_regularization": 1.0,
        },
    )


def print_lift(y_te: pd.Series, proba: np.ndarray) -> None:
    """LIFT — valor de negócio: captura de reviews ruins nos top decis de risco."""
    print("\nLIFT (valor de negócio) — ordenando o teste por risco previsto:")
    dfl = (
        pd.DataFrame({"y": y_te.values, "p": proba})
        .sort_values("p", ascending=False)
        .reset_index(drop=True)
    )
    base = y_te.mean()
    for q in (0.10, 0.20, 0.30):
        k = int(len(dfl) * q)
        cap = dfl.iloc[:k]["y"].sum() / y_te.sum()
        rate = dfl.iloc[:k]["y"].mean()
        print(
            f"  top {int(q*100):>2}% risco: captura {cap:.1%} dos reviews ruins | "
            f"taxa {rate:.1%} (lift {rate/base:.2f}x)"
        )


def main() -> None:
    print("=" * 80)
    print("MODELO DE PREVISÃO DE REVIEW RUIM (insatisfação) — Olist  [sem leakage]")
    print("=" * 80)

    X, y = build_features()
    print(
        f"\nAmostras: {len(X):,} | review ruim (<=2): {y.sum():,} ({y.mean():.2%}) | features: {X.shape[1]}"
    )
    print(f"Numéricas: {len(NUMERIC)} | categóricas: {len(CATEG)} (cat, UF, payment_type)")

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
    )
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    models = candidate_models()
    results = run_cross_validation(models, X_tr, y_tr, cv)
    best_name = select_best(results)

    best = models[best_name]
    best_thr = tune_threshold(best, X_tr, y_tr, cv)

    proba, test_metrics = evaluate_holdout(
        best, X_tr, y_tr, X_te, y_te, best_thr, best_name,
        target_names=["ok", "review_ruim"],
    )
    print(f"(baseline PR-AUC = taxa positiva = {y.mean():.3f})")

    print_lift(y_te, proba)
    imp = permutation_top(best, X_te, y_te, list(X.columns), n=10)

    metrics = {
        "problem": "bad_review_prediction (score<=2)",
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
