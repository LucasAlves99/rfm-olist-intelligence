# pipeline/run_pipeline.py
"""Orquestrador end-to-end do pipeline RFM Olist.

Executa todas as etapas em sequência:
    1. Carregamento + quality checks
    2. Construção do RFM
    3. Scores e segmentação estratégica
    4. Clusterização + serialização do modelo
    5. CLV simples
    6. Exportação tipada para Power BI

Uso:
    python pipeline/run_pipeline.py
"""

# Standard library
import logging
import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no path antes dos imports locais.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Third-party
import pandas as pd

# Local
from src.config import CONFIG
from src.data_loader import load_all_data
from src.data_quality import (
    check_customers,
    check_orders,
    deduplicate_reviews,
    validate_snapshot,
)
from src.rfm import build_cohort_retention, build_orders_base, build_rfm
from src.segmentation import (
    apply_rfm_scores,
    apply_strategic_segments,
    assign_cluster_names,
    calculate_clv_simple,
)
from src.clustering import fit_and_save, predict_clusters
from src.export import (
    build_dim_calendario,
    build_dim_segmentos,
    export_orders_to_powerbi,
    export_rfm_to_powerbi,
    write_powerbi_csv,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def log_step(title: str) -> None:
    """Loga um cabeçalho de etapa do pipeline (banner padronizado)."""
    bar = "=" * 60
    logger.info(bar)
    logger.info(title)
    logger.info(bar)


def main() -> None:
    output_dir = Path(CONFIG["paths"]["powerbi_output"])
    output_dir.mkdir(parents=True, exist_ok=True)
    encoding = CONFIG["export"]["encoding"]

    # ── 1. Load + quality checks ──────────────────────────────────────────────
    log_step("ETAPA 1: Carregamento e Quality Checks")
    data = load_all_data(CONFIG["paths"]["raw_data"])
    check_orders(data["orders"])
    check_customers(data["customers"])
    data["reviews"] = deduplicate_reviews(data["reviews"])

    # ── 2. RFM ────────────────────────────────────────────────────────────────
    log_step("ETAPA 2: Construção do RFM")
    rfm = build_rfm(
        data,
        snapshot_date=CONFIG["rfm"]["snapshot_date"],
        status_filter=CONFIG["rfm"]["status_filter"],
    )

    # Valida que não há pedidos posteriores à snapshot fixada.
    snapshot = pd.Timestamp(CONFIG["rfm"]["snapshot_date"])
    orders_delivered = data["orders"][
        data["orders"]["order_status"] == CONFIG["rfm"]["status_filter"]
    ]
    validate_snapshot(orders_delivered, snapshot)

    # ── 3. Scores + Segmentação ───────────────────────────────────────────────
    log_step("ETAPA 3: Scores RFM e Segmentação Estratégica")
    rfm = apply_rfm_scores(rfm, q=CONFIG["rfm"]["q_score"])
    rfm = apply_strategic_segments(rfm)

    # ── 4. Clustering ─────────────────────────────────────────────────────────
    log_step("ETAPA 4: Clusterização e Serialização")
    pipeline = fit_and_save(rfm, CONFIG, output_dir=CONFIG["paths"]["models"])
    rfm["Cluster"] = predict_clusters(rfm, pipeline)
    rfm = assign_cluster_names(rfm)

    # ── 5. CLV simples ────────────────────────────────────────────────────────
    log_step("ETAPA 5: Customer Lifetime Value (CLV simples)")
    rfm = calculate_clv_simple(rfm)

    # ── 6. Exportação Power BI ────────────────────────────────────────────────
    log_step("ETAPA 6: Exportação para Power BI")

    # fato_rfm_clientes
    export_rfm_to_powerbi(rfm, output_dir / "fato_rfm_clientes.csv", encoding=encoding)

    # fato_pedidos (enriquecido com o cluster do cliente)
    orders_base = build_orders_base(data, status_filter=CONFIG["rfm"]["status_filter"])
    orders_enriched = orders_base.merge(
        rfm[["customer_unique_id", "Cluster", "Cluster_Name"]],
        on="customer_unique_id",
        how="left",
    )
    export_orders_to_powerbi(orders_enriched, output_dir / "fato_pedidos.csv", encoding=encoding)

    # fato_cohort (retenção por safra de aquisição — tabela pré-calculada p/ heatmap)
    cohort = build_cohort_retention(orders_base)
    write_powerbi_csv(cohort, output_dir / "fato_cohort.csv", encoding=encoding)

    # Dimensões (mesmo formato BR via helper compartilhado)
    write_powerbi_csv(build_dim_segmentos(), output_dir / "dim_segmentos.csv", encoding=encoding)
    write_powerbi_csv(
        build_dim_calendario(start="2016-01-01", end="2018-12-31"),
        output_dir / "dim_calendario.csv",
        encoding=encoding,
    )

    log_step("PIPELINE CONCLUÍDO COM SUCESSO!")
    logger.info(f"Arquivos gerados em: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
