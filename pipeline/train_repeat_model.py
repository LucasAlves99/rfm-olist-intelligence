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

Uso:
    "C:/Users/Luk/anaconda3/python.exe" pipeline/train_repeat_model.py
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

from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline

warnings.filterwarnings("ignore")

RANDOM_STATE = 42
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "powerbi" / "fato_pedidos.csv"
OUT_MODEL = ROOT / "models" / "repeat_model.pkl"
OUT_METRICS = ROOT / "models" / "repeat_model_metrics.json"


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


def make_preprocessor() -> ColumnTransformer:
    from sklearn.impute import SimpleImputer

    return ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]),
                NUMERIC,
            ),
            # agrupa categorias raras (min_frequency) p/ controlar cardinalidade/overfit
            (
                "cat",
                OneHotEncoder(
                    handle_unknown="infrequent_if_exist", min_frequency=0.01, sparse_output=False
                ),
                CATEG,
            ),
        ]
    )


# ───────────────────────────── 2. Modelos candidatos ─────────────────────────────
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
                        n_estimators=300,
                        max_depth=12,
                        min_samples_leaf=30,
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
                        max_depth=4,
                        learning_rate=0.06,
                        max_iter=400,
                        l2_regularization=1.0,
                        early_stopping=True,
                        validation_fraction=0.15,
                        class_weight="balanced",
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
        "SMOTE + LogisticRegression": ImbPipeline(
            [
                ("pre", pre()),
                ("smote", SMOTE(random_state=RANDOM_STATE)),
                ("clf", LogisticRegression(max_iter=2000, C=0.5, random_state=RANDOM_STATE)),
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
    results = {}

    print("\n" + "-" * 78)
    print("VALIDAÇÃO CRUZADA (5-fold estratificada no treino) + diagnóstico de overfit")
    print("-" * 78)
    header = (
        f"{'Modelo':<28}{'F1(CV)':>9}{'PR-AUC':>9}{'ROC':>8}{'BalAcc':>8}{'F1(tr)':>8}{'gap':>7}"
    )
    print(header)
    for name, pipe in models.items():
        cvres = cross_validate(
            pipe, X_tr, y_tr, cv=cv, scoring=SCORING, return_train_score=True, n_jobs=-1
        )
        f1_cv = cvres["test_f1"].mean()
        f1_tr = cvres["train_f1"].mean()
        gap = f1_tr - f1_cv  # indicador de overfit
        results[name] = {
            "f1_cv": round(f1_cv, 4),
            "f1_cv_std": round(cvres["test_f1"].std(), 4),
            "f1_train": round(f1_tr, 4),
            "overfit_gap": round(gap, 4),
            "pr_auc_cv": round(cvres["test_pr_auc"].mean(), 4),
            "roc_auc_cv": round(cvres["test_roc_auc"].mean(), 4),
            "balanced_acc_cv": round(cvres["test_balanced_acc"].mean(), 4),
            "accuracy_cv": round(cvres["test_accuracy"].mean(), 4),
            "recall_cv": round(cvres["test_recall"].mean(), 4),
            "precision_cv": round(cvres["test_precision"].mean(), 4),
        }
        print(
            f"{name:<28}{f1_cv:>9.3f}{results[name]['pr_auc_cv']:>9.3f}"
            f"{results[name]['roc_auc_cv']:>8.3f}{results[name]['balanced_acc_cv']:>8.3f}"
            f"{f1_tr:>8.3f}{gap:>7.3f}"
        )

    # ── seleção: melhor F1(CV) penalizando overfit (gap) e ignorando o baseline ──
    def score_sel(r):
        return r["f1_cv"] - 0.5 * max(0.0, r["overfit_gap"] - 0.03)

    ranked = sorted(
        ((n, r) for n, r in results.items() if not n.startswith("Baseline")),
        key=lambda kv: score_sel(kv[1]),
        reverse=True,
    )
    best_name = ranked[0][0]
    print(f"\n>>> Melhor modelo (F1 CV penalizando overfit): {best_name}")

    # ───────────────────── 3. Tuning de threshold (OOF, sem vazar teste) ─────────────────────
    best = models[best_name]
    oof_proba = cross_val_predict(best, X_tr, y_tr, cv=cv, method="predict_proba", n_jobs=-1)[:, 1]
    prec, rec, thr = precision_recall_curve(y_tr, oof_proba)
    f1s = np.divide(2 * prec * rec, prec + rec, out=np.zeros_like(prec), where=(prec + rec) > 0)
    best_thr = float(thr[np.argmax(f1s[:-1])]) if len(thr) else 0.5
    print(f"Threshold ótimo (max F1 out-of-fold): {best_thr:.3f} (default = 0.500)")

    # ───────────────────── 4. Avaliação final no TESTE hold-out ─────────────────────
    best.fit(X_tr, y_tr)
    proba_te = best.predict_proba(X_te)[:, 1]
    pred_def = (proba_te >= 0.5).astype(int)
    pred_tun = (proba_te >= best_thr).astype(int)

    print("\n" + "=" * 78)
    print(f"AVALIAÇÃO FINAL NO TESTE (hold-out 20%, n={len(X_te):,}) — {best_name}")
    print("=" * 78)
    for label, pred in [
        ("threshold=0.50 (default)", pred_def),
        (f"threshold={best_thr:.3f} (F1-ótimo)", pred_tun),
    ]:
        print(f"\n· {label}")
        print(
            f"  F1(classe positiva): {f1_score(y_te, pred):.3f} | "
            f"accuracy: {(pred == y_te).mean():.3f}"
        )
        print(
            "  "
            + classification_report(
                y_te, pred, digits=3, target_names=["nao_recompra", "recompra"]
            ).replace("\n", "\n  ")
        )
        tn, fp, fn, tp = confusion_matrix(y_te, pred).ravel()
        print(f"  Matriz: TN={tn} FP={fp} FN={fn} TP={tp}")
    print(
        f"\nPR-AUC (teste): {average_precision_score(y_te, proba_te):.3f} | "
        f"ROC-AUC (teste): {roc_auc_score(y_te, proba_te):.3f}"
    )

    # overfit final: F1 treino vs teste (no threshold ótimo)
    f1_train_full = f1_score(y_tr, (best.predict_proba(X_tr)[:, 1] >= best_thr).astype(int))
    f1_test_tun = f1_score(y_te, pred_tun)
    print(
        f"Overfit check (F1 treino={f1_train_full:.3f} vs teste={f1_test_tun:.3f}, "
        f"gap={f1_train_full - f1_test_tun:.3f})"
    )

    # ───────────────────── 5. Importância das features (permutação) ─────────────────────
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
        imp = sorted(zip(X.columns, perm.importances_mean), key=lambda kv: kv[1], reverse=True)[:8]
        print("\nTop features (permutation importance, drop em PR-AUC):")
        for f, v in imp:
            print(f"  {f:<20} {v:+.4f}")
    except Exception as e:  # noqa
        imp = []
        print("permutation_importance pulado:", e)

    # ───────────────────── 6. Persistência ─────────────────────
    import joblib

    joblib.dump({"model": best, "threshold": best_thr, "features": list(X.columns)}, OUT_MODEL)
    metrics = {
        "problem": "repeat_purchase_propensity",
        "n_samples": int(len(X)),
        "positive_rate": round(float(y.mean()), 4),
        "random_state": RANDOM_STATE,
        "cv_folds": 5,
        "best_model": best_name,
        "best_threshold": round(best_thr, 4),
        "cv_results": results,
        "test": {
            "f1_default": round(float(f1_score(y_te, pred_def)), 4),
            "f1_tuned": round(float(f1_test_tun), 4),
            "accuracy_tuned": round(float((pred_tun == y_te).mean()), 4),
            "pr_auc": round(float(average_precision_score(y_te, proba_te)), 4),
            "roc_auc": round(float(roc_auc_score(y_te, proba_te)), 4),
            "overfit_gap_f1": round(float(f1_train_full - f1_test_tun), 4),
        },
        "top_features": [{"feature": f, "importance": round(float(v), 5)} for f, v in imp],
    }
    OUT_METRICS.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nModelo salvo em {OUT_MODEL}")
    print(f"Métricas salvas em {OUT_METRICS}")


if __name__ == "__main__":
    main()
