"""Utilitários compartilhados pelos scripts de treino supervisionado.

Tanto `train_repeat_model.py` (propensão à recompra) quanto
`train_review_model.py` (previsão de review ruim) seguem exatamente o mesmo
protocolo metodológico — só mudam as features, os hiperparâmetros e alguns
rótulos. Toda a "infraestrutura" comum (pré-processamento, modelos candidatos,
validação cruzada, seleção penalizando overfit, tuning de threshold, avaliação
no hold-out, importância por permutação e persistência) vive aqui para evitar
duplicação e divergência entre os dois pipelines.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import joblib
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
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

RANDOM_STATE = 42

# Métricas reportadas na validação cruzada. Para classes raras, F1/PR-AUC/balanced
# accuracy são as primárias — acurácia pura é enganosa.
SCORING = {
    "f1": "f1",
    "pr_auc": "average_precision",
    "roc_auc": "roc_auc",
    "balanced_acc": "balanced_accuracy",
    "accuracy": "accuracy",
    "recall": "recall",
    "precision": "precision",
}


def make_preprocessor(numeric: list[str], categ: list[str]) -> ColumnTransformer:
    """Pré-processador padrão: imputação+escala nas numéricas, OHE nas categóricas.

    O OneHotEncoder agrupa categorias raras (``min_frequency``) para controlar
    cardinalidade e overfit.
    """
    return ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]),
                numeric,
            ),
            (
                "cat",
                OneHotEncoder(
                    handle_unknown="infrequent_if_exist", min_frequency=0.01, sparse_output=False
                ),
                categ,
            ),
        ]
    )


def build_candidates(
    make_pre: Callable[[], ColumnTransformer],
    *,
    rf_kwargs: dict,
    hgb_kwargs: dict,
    include_smote: bool = False,
) -> dict[str, Pipeline]:
    """Monta o dicionário de modelos candidatos (mesma família nos dois pipelines).

    Args:
        make_pre: Fábrica que devolve um pré-processador novo a cada modelo.
        rf_kwargs: Hiperparâmetros específicos do RandomForest.
        hgb_kwargs: Hiperparâmetros específicos do HistGradientBoosting.
        include_smote: Se True, adiciona o candidato "SMOTE + LogisticRegression"
            (requer imbalanced-learn).
    """
    models: dict[str, Pipeline] = {
        "Baseline (DummyMostFreq)": Pipeline(
            [("pre", make_pre()), ("clf", DummyClassifier(strategy="most_frequent"))]
        ),
        "LogisticRegression": Pipeline(
            [
                ("pre", make_pre()),
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
                ("pre", make_pre()),
                (
                    "clf",
                    RandomForestClassifier(
                        class_weight="balanced_subsample",
                        n_jobs=-1,
                        random_state=RANDOM_STATE,
                        **rf_kwargs,
                    ),
                ),
            ]
        ),
        "HistGradientBoosting": Pipeline(
            [
                ("pre", make_pre()),
                (
                    "clf",
                    HistGradientBoostingClassifier(
                        early_stopping=True,
                        validation_fraction=0.15,
                        class_weight="balanced",
                        random_state=RANDOM_STATE,
                        **hgb_kwargs,
                    ),
                ),
            ]
        ),
    }

    if include_smote:
        from imblearn.over_sampling import SMOTE
        from imblearn.pipeline import Pipeline as ImbPipeline

        models["SMOTE + LogisticRegression"] = ImbPipeline(
            [
                ("pre", make_pre()),
                ("smote", SMOTE(random_state=RANDOM_STATE)),
                ("clf", LogisticRegression(max_iter=2000, C=0.5, random_state=RANDOM_STATE)),
            ]
        )

    return models


def run_cross_validation(
    models: dict[str, Pipeline],
    X_tr: pd.DataFrame,
    y_tr: pd.Series,
    cv: StratifiedKFold,
) -> dict[str, dict]:
    """Roda a CV 5-fold de todos os modelos e imprime a tabela comparativa.

    Returns:
        Dicionário {nome_modelo: métricas_arredondadas} (inclui ``overfit_gap``).
    """
    print("\n" + "-" * 80)
    print("VALIDAÇÃO CRUZADA (5-fold estratificada no treino) + diagnóstico de overfit")
    print("-" * 80)
    print(
        f"{'Modelo':<28}{'F1(CV)':>9}{'PR-AUC':>9}{'ROC':>8}"
        f"{'BalAcc':>8}{'Acc':>8}{'F1(tr)':>8}{'gap':>7}"
    )

    results: dict[str, dict] = {}
    for name, pipe in models.items():
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
    return results


def select_best(results: dict[str, dict]) -> str:
    """Escolhe o melhor modelo por F1(CV) penalizando overfit, ignorando o baseline."""

    def score(r: dict) -> float:
        return r["f1_cv"] - 0.5 * max(0.0, r["overfit_gap"] - 0.03)

    ranked = sorted(
        ((n, r) for n, r in results.items() if not n.startswith("Baseline")),
        key=lambda kv: score(kv[1]),
        reverse=True,
    )
    best_name = ranked[0][0]
    print(f"\n>>> Melhor modelo (F1 CV penalizando overfit): {best_name}")
    return best_name


def tune_threshold(
    model: Pipeline,
    X_tr: pd.DataFrame,
    y_tr: pd.Series,
    cv: StratifiedKFold,
) -> float:
    """Acha o threshold que maximiza F1 usando probabilidades out-of-fold (sem vazar teste)."""
    oof = cross_val_predict(model, X_tr, y_tr, cv=cv, method="predict_proba", n_jobs=-1)[:, 1]
    prec, rec, thr = precision_recall_curve(y_tr, oof)
    f1s = np.divide(2 * prec * rec, prec + rec, out=np.zeros_like(prec), where=(prec + rec) > 0)
    best_thr = float(thr[np.argmax(f1s[:-1])]) if len(thr) else 0.5
    print(f"Threshold ótimo (max F1 out-of-fold): {best_thr:.3f} (default = 0.500)")
    return best_thr


def evaluate_holdout(
    model: Pipeline,
    X_tr: pd.DataFrame,
    y_tr: pd.Series,
    X_te: pd.DataFrame,
    y_te: pd.Series,
    best_thr: float,
    best_name: str,
    target_names: list[str],
) -> tuple[np.ndarray, dict]:
    """Treina no treino completo, avalia no hold-out e imprime o relatório padrão.

    Returns:
        Tupla (proba_teste, bloco_de_métricas_para_JSON).
    """
    model.fit(X_tr, y_tr)
    proba = model.predict_proba(X_te)[:, 1]
    pred_def = (proba >= 0.5).astype(int)
    pred_tun = (proba >= best_thr).astype(int)

    print("\n" + "=" * 80)
    print(f"AVALIAÇÃO FINAL — TESTE hold-out 20% (n={len(X_te):,}) — {best_name}")
    print("=" * 80)
    for label, pred in [
        ("threshold=0.50 (default)", pred_def),
        (f"threshold={best_thr:.3f} (F1-ótimo)", pred_tun),
    ]:
        print(
            f"\n· {label}  ->  F1={f1_score(y_te, pred, zero_division=0):.3f} | "
            f"accuracy={(pred == y_te).mean():.3f}"
        )
        print(
            "  "
            + classification_report(
                y_te, pred, digits=3, zero_division=0, target_names=target_names
            ).replace("\n", "\n  ")
        )
        tn, fp, fn, tp = confusion_matrix(y_te, pred).ravel()
        print(f"  Matriz: TN={tn} FP={fp} FN={fn} TP={tp}")

    pr_auc = average_precision_score(y_te, proba)
    roc = roc_auc_score(y_te, proba)
    print(f"\nPR-AUC (teste): {pr_auc:.3f} | ROC-AUC (teste): {roc:.3f}")

    f1_tr_full = f1_score(
        y_tr, (model.predict_proba(X_tr)[:, 1] >= best_thr).astype(int), zero_division=0
    )
    f1_te_tun = f1_score(y_te, pred_tun, zero_division=0)
    print(
        f"Overfit check final: F1 treino={f1_tr_full:.3f} vs teste={f1_te_tun:.3f} "
        f"(gap={f1_tr_full - f1_te_tun:+.3f})"
    )

    test_metrics = {
        "f1_default": round(float(f1_score(y_te, pred_def, zero_division=0)), 4),
        "f1_tuned": round(float(f1_te_tun), 4),
        "accuracy_tuned": round(float((pred_tun == y_te).mean()), 4),
        "pr_auc": round(float(pr_auc), 4),
        "roc_auc": round(float(roc), 4),
        "overfit_gap_f1": round(float(f1_tr_full - f1_te_tun), 4),
    }
    return proba, test_metrics


def permutation_top(
    model: Pipeline,
    X_te: pd.DataFrame,
    y_te: pd.Series,
    feature_names: list[str],
    n: int = 10,
) -> list[tuple[str, float]]:
    """Importância por permutação (queda em PR-AUC). Retorna e imprime o top-N."""
    try:
        perm = permutation_importance(
            model,
            X_te,
            y_te,
            scoring="average_precision",
            n_repeats=5,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
        imp = sorted(zip(feature_names, perm.importances_mean), key=lambda kv: kv[1], reverse=True)[
            :n
        ]
        print("\nTop features (permutation importance, drop em PR-AUC):")
        for f, v in imp:
            print(f"  {f:<22} {v:+.4f}")
        return imp
    except Exception as e:  # noqa: BLE001
        print("permutation_importance pulado:", e)
        return []


def save_artifacts(
    model: Pipeline,
    best_thr: float,
    features: list[str],
    metrics: dict,
    out_model: Path,
    out_metrics: Path,
) -> None:
    """Persiste o modelo (+ threshold/features) e o JSON de métricas."""
    joblib.dump({"model": model, "threshold": best_thr, "features": features}, out_model)
    out_metrics.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nModelo salvo em {out_model}\nMétricas salvas em {out_metrics}")
