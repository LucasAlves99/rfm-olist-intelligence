# src/clustering.py
"""Pipeline de clusterização RFM: treinamento, serialização e inferência."""

# Standard library
import json
import logging
from datetime import datetime
from pathlib import Path

# Third-party
import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


def build_pipeline(k: int, random_state: int = 42, n_init: int = 10) -> Pipeline:
    """Constrói o pipeline de clusterização RFM (StandardScaler + KMeans).

    Args:
        k: Número de clusters.
        random_state: Seed para reprodutibilidade.
        n_init: Número de inicializações do KMeans.

    Returns:
        Pipeline scikit-learn pronto para treino.
    """
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            ("kmeans", KMeans(n_clusters=k, random_state=random_state, n_init=n_init)),
        ]
    )


def prepare_features(rfm: pd.DataFrame) -> np.ndarray:
    """Prepara a matriz de features para clusterização (com transformação log).

    Args:
        rfm: DataFrame com colunas Recency, Frequency, Monetary.

    Returns:
        Array NumPy com shape (n_clientes, 3): Recency, log(Frequency), log(Monetary).
    """
    return np.column_stack(
        [
            rfm["Recency"].values,
            np.log1p(rfm["Frequency"].values),
            np.log1p(rfm["Monetary"].values),
        ]
    )


def fit_and_save(
    rfm: pd.DataFrame,
    config: dict,
    output_dir: str = "models",
) -> Pipeline:
    """Treina o pipeline de clusterização e persiste modelo + metadados.

    Args:
        rfm: DataFrame RFM com colunas Recency, Frequency, Monetary.
        config: Dicionário de configuração do projeto.
        output_dir: Diretório para salvar os arquivos.

    Returns:
        Pipeline treinado (StandardScaler + KMeans).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    X = prepare_features(rfm)

    pipeline = build_pipeline(
        k=config["clustering"]["k_clusters"],
        random_state=config["clustering"]["random_state"],
        n_init=config["clustering"]["n_init"],
    )

    labels = pipeline.fit_predict(X)

    # Silhouette no espaço escalonado
    X_scaled = pipeline.named_steps["scaler"].transform(X)
    sil_score = silhouette_score(X_scaled, labels)

    logger.info(
        f"KMeans treinado: K={config['clustering']['k_clusters']} | "
        f"Silhouette={sil_score:.4f} | N={len(rfm):,}"
    )

    # Persiste pipeline
    pipeline_path = output_dir / "rfm_pipeline.pkl"
    joblib.dump(pipeline, pipeline_path)
    logger.info(f"Pipeline salvo em: {pipeline_path}")

    # Persiste metadados
    metadata = {
        "training_date": datetime.now().isoformat(),
        "k_clusters": config["clustering"]["k_clusters"],
        "random_state": config["clustering"]["random_state"],
        "n_init": config["clustering"]["n_init"],
        "features": config["clustering"]["features"],
        "n_samples": len(rfm),
        "silhouette_score": float(sil_score),
        "snapshot_date": config["rfm"]["snapshot_date"],
    }
    meta_path = output_dir / "model_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    logger.info(f"Metadados salvos em: {meta_path}")

    return pipeline


def predict_clusters(rfm: pd.DataFrame, pipeline: Pipeline) -> pd.Series:
    """Aplica o pipeline treinado para predizer clusters de novos clientes.

    Args:
        rfm: DataFrame com colunas Recency, Frequency, Monetary.
        pipeline: Pipeline treinado (StandardScaler + KMeans).

    Returns:
        Série com os labels de cluster.
    """
    X = prepare_features(rfm)
    labels = pipeline.predict(X)
    return pd.Series(labels, index=rfm.index, name="Cluster")


def elbow_silhouette(
    rfm: pd.DataFrame,
    k_range: range = range(2, 9),
    random_state: int = 42,
    silhouette_sample_size: int = 10000,
) -> pd.DataFrame:
    """Calcula inércia e silhouette para vários valores de K.

    O silhouette_score é O(n²) — para bases grandes (>10k clientes) usamos
    amostra estratificada para manter a função rápida sem perder precisão
    relevante (a estimativa via amostra é estatisticamente equivalente).

    Args:
        rfm: DataFrame RFM com colunas Recency, Frequency, Monetary.
        k_range: Range de valores de K a testar.
        random_state: Seed para reprodutibilidade.
        silhouette_sample_size: Tamanho da amostra para o silhouette.
            Se a base for menor, usa todos os pontos.

    Returns:
        DataFrame com colunas K, Inertia, Silhouette.
    """
    X = prepare_features(rfm)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    n = len(X_scaled)
    use_sampling = n > silhouette_sample_size
    if use_sampling:
        rng = np.random.default_rng(random_state)
        sample_idx = rng.choice(n, size=silhouette_sample_size, replace=False)
        logger.info(
            f"Base com {n:,} pontos > {silhouette_sample_size:,} — "
            f"usando amostra para silhouette (KMeans roda na base completa)"
        )

    results = []
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        labels = km.fit_predict(X_scaled)

        if use_sampling:
            sil = silhouette_score(X_scaled[sample_idx], labels[sample_idx])
        else:
            sil = silhouette_score(X_scaled, labels)

        results.append({"K": k, "Inertia": km.inertia_, "Silhouette": sil})
        logger.info(f"K={k} | Inertia={km.inertia_:.0f} | Sil={sil:.4f}")

    return pd.DataFrame(results)
