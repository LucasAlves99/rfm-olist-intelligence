# tests/test_clustering.py
"""Testes para src/clustering.py (pipeline KMeans + serialização)."""

import json

import numpy as np
import pandas as pd
import pytest
from sklearn.pipeline import Pipeline

from src.clustering import (
    build_pipeline,
    elbow_silhouette,
    fit_and_save,
    predict_clusters,
    prepare_features,
)


@pytest.fixture
def rfm():
    """RFM sintético com variação suficiente para KMeans/silhouette."""
    rng = np.random.default_rng(42)
    n = 80
    return pd.DataFrame(
        {
            "Recency": rng.integers(1, 400, n),
            "Frequency": rng.integers(1, 10, n),
            "Monetary": rng.uniform(10, 5000, n),
        }
    )


@pytest.fixture
def config():
    return {
        "clustering": {
            "k_clusters": 4,
            "random_state": 42,
            "n_init": 5,
            "features": ["Recency", "Frequency_log", "Monetary_log"],
        },
        "rfm": {"snapshot_date": "2018-09-04"},
    }


def test_prepare_features_aplica_log(rfm):
    X = prepare_features(rfm)
    assert X.shape == (len(rfm), 3)
    # coluna 0 = Recency cru; 1 = log1p(Frequency); 2 = log1p(Monetary)
    np.testing.assert_allclose(X[:, 0], rfm["Recency"].values)
    np.testing.assert_allclose(X[:, 1], np.log1p(rfm["Frequency"].values))


def test_build_pipeline_estrutura():
    pipe = build_pipeline(k=3)
    assert isinstance(pipe, Pipeline)
    assert "scaler" in pipe.named_steps
    assert pipe.named_steps["kmeans"].n_clusters == 3


def test_fit_and_save_persiste_artefatos(rfm, config, tmp_path):
    pipe = fit_and_save(rfm, config, output_dir=str(tmp_path))
    assert isinstance(pipe, Pipeline)
    assert (tmp_path / "rfm_pipeline.pkl").exists()

    meta_path = tmp_path / "model_metadata.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["k_clusters"] == 4
    assert meta["n_samples"] == len(rfm)
    assert "silhouette_score" in meta


def test_predict_clusters_retorna_labels(rfm, config, tmp_path):
    pipe = fit_and_save(rfm, config, output_dir=str(tmp_path))
    labels = predict_clusters(rfm, pipe)
    assert labels.name == "Cluster"
    assert len(labels) == len(rfm)
    assert labels.nunique() <= 4


def test_elbow_silhouette_colunas(rfm):
    res = elbow_silhouette(rfm, k_range=range(2, 4))
    assert list(res.columns) == ["K", "Inertia", "Silhouette"]
    assert len(res) == 2
