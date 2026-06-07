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

Uso:
    "C:/Users/Luk/anaconda3/python.exe" pipeline/train_review_model.py
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import (
    StratifiedKFold,
    cross_val_predict,
    cross_validate,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore")

RANDOM_STATE = 42
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT_MODEL = ROOT / "models" / "review_model.pkl"
OUT_METRICS = ROOT / "models" / "review_model_metrics.json"


# ───────────────────────────── 1. Feature engineering (até a entrega) ─────────────────────────────
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


def make_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [
            (
                "num",
                Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]),
                NUMERIC,
            ),
            (
                "cat",
                OneHotEncoder(
                    handle_unknown="infrequent_if_exist", min_frequency=0.01, sparse_output=False
                ),
                CATEG,
            ),
        ]
    )


def candidate_models() -> dict[str, Pipeline]:
    pre = make_preprocessor
    return {
        "Baseline (DummyMostFreq)": Pipeline(
            [("pre", pre()), ("clf", DummyClassifier(strategy="most_frequent"))]
        ),
        "LogisticRegression": Pipeline(
            [
                ("pre", pre()),
                (
                    "clf",
                    LogisticRegression(
                        class_weight="balanced", max_iter=2000, C=0.5, random_state=RANDOM_STATE
                    ),
                ),
            ]
        ),
        "RandomForest": Pipeline(
            [
                ("pre", pre()),
                (
                    "clf",
                    RandomForestClassifier(
                        n_estimators=400,
                        max_depth=14,
                        min_samples_leaf=20,
                        class_weight="balanced_subsample",
                        n_jobs=-1,
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
        "HistGradientBoosting": Pipeline(
            [
                ("pre", pre()),
                (
                    "clf",
                    HistGradientBoostingClassifier(
                        max_depth=5,
                        learning_rate=0.07,
                        max_iter=500,
                        l2_regularization=1.0,
                        early_stopping=True,
                        validation_fraction=0.15,
                        class_weight="balanced",
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
    }


SCORING = {
    "f1": "f1",
    "pr_auc": "average_precision",
    "roc_auc": "roc_auc",
    "balanced_acc": "balanced_accuracy",
    "accuracy": "accuracy",
    "recall": "recall",
    "precision": "precision",
}


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
    results = {}

    print("\n" + "-" * 80)
    print("VALIDAÇÃO CRUZADA (5-fold) + diagnóstico de overfit  (gap = F1_treino - F1_CV)")
    print("-" * 80)
    print(
        f"{'Modelo':<28}{'F1(CV)':>9}{'PR-AUC':>9}{'ROC':>8}{'BalAcc':>8}{'Acc':>8}{'F1(tr)':>8}{'gap':>7}"
    )
    for name, pipe in candidate_models().items():
        r = cross_validate(
            pipe, X_tr, y_tr, cv=cv, scoring=SCORING, return_train_score=True, n_jobs=-1
        )
        f1cv, f1tr = r["test_f1"].mean(), r["train_f1"].mean()
        results[name] = {
            "f1_cv": round(f1cv, 4),
            "f1_cv_std": round(r["test_f1"].std(), 4),
            "f1_train": round(f1tr, 4),
            "overfit_gap": round(f1tr - f1cv, 4),
            "pr_auc_cv": round(r["test_pr_auc"].mean(), 4),
            "roc_auc_cv": round(r["test_roc_auc"].mean(), 4),
            "balanced_acc_cv": round(r["test_balanced_acc"].mean(), 4),
            "accuracy_cv": round(r["test_accuracy"].mean(), 4),
            "recall_cv": round(r["test_recall"].mean(), 4),
            "precision_cv": round(r["test_precision"].mean(), 4),
        }
        s = results[name]
        print(
            f"{name:<28}{f1cv:>9.3f}{s['pr_auc_cv']:>9.3f}{s['roc_auc_cv']:>8.3f}"
            f"{s['balanced_acc_cv']:>8.3f}{s['accuracy_cv']:>8.3f}{f1tr:>8.3f}{s['overfit_gap']:>7.3f}"
        )

    def sel(r):
        return r["f1_cv"] - 0.5 * max(0.0, r["overfit_gap"] - 0.03)

    ranked = sorted(
        ((n, r) for n, r in results.items() if not n.startswith("Baseline")),
        key=lambda kv: sel(kv[1]),
        reverse=True,
    )
    best_name = ranked[0][0]
    print(f"\n>>> Melhor modelo (F1 CV penalizando overfit): {best_name}")

    best = candidate_models()[best_name]
    oof = cross_val_predict(best, X_tr, y_tr, cv=cv, method="predict_proba", n_jobs=-1)[:, 1]
    prec, rec, thr = precision_recall_curve(y_tr, oof)
    f1s = np.divide(2 * prec * rec, prec + rec, out=np.zeros_like(prec), where=(prec + rec) > 0)
    best_thr = float(thr[np.argmax(f1s[:-1])]) if len(thr) else 0.5
    print(f"Threshold ótimo (max F1 out-of-fold): {best_thr:.3f}")

    best.fit(X_tr, y_tr)
    proba = best.predict_proba(X_te)[:, 1]
    pred_def = (proba >= 0.5).astype(int)
    pred_tun = (proba >= best_thr).astype(int)

    print("\n" + "=" * 80)
    print(f"AVALIAÇÃO FINAL — TESTE hold-out 20% (n={len(X_te):,}) — {best_name}")
    print("=" * 80)
    for label, pred in [
        ("threshold=0.50", pred_def),
        (f"threshold={best_thr:.3f} (F1-ótimo)", pred_tun),
    ]:
        print(
            f"\n· {label}  ->  F1={f1_score(y_te, pred, zero_division=0):.3f} | "
            f"accuracy={(pred == y_te).mean():.3f}"
        )
        print(
            "  "
            + classification_report(
                y_te, pred, digits=3, zero_division=0, target_names=["ok", "review_ruim"]
            ).replace("\n", "\n  ")
        )
        tn, fp, fn, tp = confusion_matrix(y_te, pred).ravel()
        print(f"  Matriz: TN={tn} FP={fp} FN={fn} TP={tp}")
    pr_auc = average_precision_score(y_te, proba)
    roc = roc_auc_score(y_te, proba)
    print(f"\nPR-AUC (teste): {pr_auc:.3f}  (baseline={y.mean():.3f}) | ROC-AUC (teste): {roc:.3f}")

    f1_tr_full = f1_score(
        y_tr, (best.predict_proba(X_tr)[:, 1] >= best_thr).astype(int), zero_division=0
    )
    f1_te_tun = f1_score(y_te, pred_tun, zero_division=0)
    print(
        f"Overfit check final: F1 treino={f1_tr_full:.3f} vs teste={f1_te_tun:.3f} "
        f"(gap={f1_tr_full - f1_te_tun:+.3f})"
    )

    # LIFT — valor de negócio: top decis por probabilidade
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

    try:
        perm = permutation_importance(
            best,
            X_te,
            y_te,
            scoring="average_precision",
            n_repeats=5,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
        imp = sorted(zip(X.columns, perm.importances_mean), key=lambda kv: kv[1], reverse=True)[:10]
        print("\nTop features (permutation importance, drop em PR-AUC):")
        for f, v in imp:
            print(f"  {f:<22} {v:+.4f}")
    except Exception as e:  # noqa
        imp = []
        print("permutation_importance pulado:", e)

    import joblib

    joblib.dump({"model": best, "threshold": best_thr, "features": list(X.columns)}, OUT_MODEL)
    metrics = {
        "problem": "bad_review_prediction (score<=2)",
        "n_samples": int(len(X)),
        "positive_rate": round(float(y.mean()), 4),
        "random_state": RANDOM_STATE,
        "cv_folds": 5,
        "best_model": best_name,
        "best_threshold": round(best_thr, 4),
        "cv_results": results,
        "test": {
            "f1_default": round(float(f1_score(y_te, pred_def, zero_division=0)), 4),
            "f1_tuned": round(float(f1_te_tun), 4),
            "accuracy_tuned": round(float((pred_tun == y_te).mean()), 4),
            "pr_auc": round(float(pr_auc), 4),
            "roc_auc": round(float(roc), 4),
            "overfit_gap_f1": round(float(f1_tr_full - f1_te_tun), 4),
        },
        "top_features": [{"feature": f, "importance": round(float(v), 5)} for f, v in imp],
    }
    OUT_METRICS.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nModelo salvo em {OUT_MODEL}\nMétricas salvas em {OUT_METRICS}")


if __name__ == "__main__":
    main()
