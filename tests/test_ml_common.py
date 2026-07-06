# tests/test_ml_common.py
"""Testes para pipeline/ml_common.py (infra de treino compartilhada)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline

# pipeline/ não é um pacote — adiciona ao path como os próprios scripts fazem.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

import ml_common as mc  # noqa: E402

NUMERIC = ["x1", "x2"]
CATEG = ["g"]


@pytest.fixture
def dataset():
    """Dataset binário sintético separável (rápido e determinístico)."""
    rng = np.random.default_rng(0)
    n = 200
    x1 = rng.normal(0, 1, n)
    x2 = rng.normal(0, 1, n)
    logit = 1.5 * x1 - 1.0 * x2
    y = (logit + rng.normal(0, 0.5, n) > 0).astype(int)
    X = pd.DataFrame({"x1": x1, "x2": x2, "g": rng.choice(["a", "b", "c"], n)})
    return X, pd.Series(y, name="target")


def test_make_preprocessor_estrutura():
    pre = mc.make_preprocessor(NUMERIC, CATEG)
    assert isinstance(pre, ColumnTransformer)
    names = [name for name, _, _ in pre.transformers]
    assert names == ["num", "cat"]


def test_build_candidates_smote_toggle():
    base = mc.build_candidates(
        lambda: mc.make_preprocessor(NUMERIC, CATEG),
        rf_kwargs={"n_estimators": 50, "max_depth": 5, "min_samples_leaf": 10},
        hgb_kwargs={"max_depth": 3, "learning_rate": 0.1, "max_iter": 50, "l2_regularization": 1.0},
    )
    assert "SMOTE + LogisticRegression" not in base
    assert {"Baseline (DummyMostFreq)", "LogisticRegression", "RandomForest"}.issubset(base)
    # hiperparâmetros repassados ao RF
    assert base["RandomForest"].named_steps["clf"].n_estimators == 50

    with_smote = mc.build_candidates(
        lambda: mc.make_preprocessor(NUMERIC, CATEG),
        rf_kwargs={"n_estimators": 50, "max_depth": 5, "min_samples_leaf": 10},
        hgb_kwargs={"max_depth": 3, "learning_rate": 0.1, "max_iter": 50, "l2_regularization": 1.0},
        include_smote=True,
    )
    assert "SMOTE + LogisticRegression" in with_smote


def test_select_best_ignora_baseline_e_penaliza_overfit():
    results = {
        "Baseline (DummyMostFreq)": {"f1_cv": 0.99, "overfit_gap": 0.0},
        "ModelA": {"f1_cv": 0.50, "overfit_gap": 0.00},  # score = 0.50
        "ModelB": {"f1_cv": 0.52, "overfit_gap": 0.20},  # score = 0.52 - 0.085 = 0.435
    }
    assert mc.select_best(results) == "ModelA"


def test_scoring_tem_metricas_primarias():
    for k in ["f1", "pr_auc", "roc_auc", "balanced_acc"]:
        assert k in mc.SCORING


def test_fluxo_end_to_end(dataset, tmp_path):
    """Smoke do fluxo completo com um único modelo leve."""
    X, y = dataset
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, stratify=y, random_state=42)
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    models = {
        "LogisticRegression": Pipeline(
            [
                ("pre", mc.make_preprocessor(NUMERIC, CATEG)),
                ("clf", LogisticRegression(max_iter=500)),
            ]
        )
    }

    results = mc.run_cross_validation(models, X_tr, y_tr, cv)
    assert "overfit_gap" in results["LogisticRegression"]

    best_name = mc.select_best(results)
    assert best_name == "LogisticRegression"

    thr = mc.tune_threshold(models[best_name], X_tr, y_tr, cv)
    assert 0.0 <= thr <= 1.0

    proba, test_metrics = mc.evaluate_holdout(
        models[best_name], X_tr, y_tr, X_te, y_te, thr, best_name, target_names=["neg", "pos"]
    )
    assert len(proba) == len(y_te)
    assert {"f1_tuned", "pr_auc", "roc_auc"}.issubset(test_metrics)

    out_model = tmp_path / "m.pkl"
    out_metrics = tmp_path / "m.json"
    mc.save_artifacts(models[best_name], thr, list(X.columns), {"k": 1}, out_model, out_metrics)
    assert out_model.exists() and out_metrics.exists()
