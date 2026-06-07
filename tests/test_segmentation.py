# tests/test_segmentation.py
"""Testes para src/segmentation.py."""

import pandas as pd
import pytest
from src.segmentation import (
    apply_rfm_scores,
    apply_strategic_segments,
    assign_cluster_names,
    derive_cluster_names_from_profile,
    build_cluster_profile,
    calculate_clv_simple,
    BUSINESS_CLUSTER_NAMES,
)


def make_rfm() -> pd.DataFrame:
    """DataFrame RFM mínimo para testes."""
    return pd.DataFrame(
        {
            "customer_unique_id": [f"u{i}" for i in range(20)],
            "Recency": [
                10,
                50,
                100,
                200,
                350,
                30,
                90,
                180,
                270,
                365,
                5,
                60,
                120,
                240,
                400,
                15,
                75,
                150,
                300,
                450,
            ],
            "Frequency": [3, 1, 2, 1, 1, 4, 1, 1, 2, 1, 5, 1, 3, 1, 1, 2, 1, 1, 2, 1],
            "Monetary": [
                500.0,
                100.0,
                250.0,
                80.0,
                60.0,
                700.0,
                150.0,
                90.0,
                200.0,
                50.0,
                900.0,
                120.0,
                300.0,
                70.0,
                45.0,
                400.0,
                130.0,
                110.0,
                180.0,
                40.0,
            ],
            "Avg_Order_Value": [
                166.7,
                100.0,
                125.0,
                80.0,
                60.0,
                175.0,
                150.0,
                90.0,
                100.0,
                50.0,
                180.0,
                120.0,
                100.0,
                70.0,
                45.0,
                200.0,
                130.0,
                110.0,
                90.0,
                40.0,
            ],
        }
    )


class TestApplyRfmScores:
    def test_has_score_columns(self):
        rfm = apply_rfm_scores(make_rfm())
        for col in ["R_score", "F_score", "M_score", "RFM_bucket", "RFM_score", "RFM_segment"]:
            assert col in rfm.columns

    def test_scores_in_range(self):
        rfm = apply_rfm_scores(make_rfm())
        for col in ["R_score", "F_score", "M_score"]:
            vals = rfm[col].astype(int)
            assert vals.between(1, 5).all(), f"{col} fora do intervalo 1-5"

    def test_rfm_score_is_sum_of_parts(self):
        rfm = apply_rfm_scores(make_rfm())
        expected = (
            rfm["R_score"].astype(int) + rfm["F_score"].astype(int) + rfm["M_score"].astype(int)
        )
        assert (rfm["RFM_score"] == expected).all()

    def test_raises_without_required_columns(self):
        bad = pd.DataFrame({"A": [1, 2, 3]})
        with pytest.raises(ValueError, match="colunas necessárias"):
            apply_rfm_scores(bad)

    def test_bucket_has_3_chars(self):
        rfm = apply_rfm_scores(make_rfm())
        assert rfm["RFM_bucket"].str.len().eq(3).all()


class TestApplyStrategicSegments:
    def test_has_segment_columns(self):
        rfm = apply_strategic_segments(make_rfm())
        for col in ["Revenue_segment", "Recency_segment", "Strategic_segment"]:
            assert col in rfm.columns

    def test_recency_segment_labels(self):
        rfm = apply_strategic_segments(make_rfm())
        valid = {"Ativo", "Recente", "Morno", "Em Risco"}
        assert set(rfm["Recency_segment"].unique()).issubset(valid)

    def test_revenue_segment_labels(self):
        rfm = apply_strategic_segments(make_rfm())
        valid = {"Elite (Top 5%)", "High Value (Next 10%)", "Mid Value (Next 20%)", "Base"}
        assert set(rfm["Revenue_segment"].unique()).issubset(valid)


def make_4_cluster_rfm() -> pd.DataFrame:
    """Cria RFM mock com 4 clusters de perfis bem distintos."""
    import numpy as np

    rng = np.random.default_rng(42)

    # Cluster 0: Campeões (alta F, alto M, R recente)
    c0 = pd.DataFrame(
        {
            "Recency": rng.integers(5, 30, 50),
            "Frequency": rng.integers(4, 10, 50),
            "Monetary": rng.uniform(800, 2000, 50),
            "Cluster": 0,
        }
    )
    # Cluster 1: Big Spenders (alto M, F=1-2, R variável)
    c1 = pd.DataFrame(
        {
            "Recency": rng.integers(20, 100, 50),
            "Frequency": rng.integers(1, 3, 50),
            "Monetary": rng.uniform(500, 1500, 50),
            "Cluster": 1,
        }
    )
    # Cluster 2: Novos / Ocasionais (F=1, M baixo, R recente)
    c2 = pd.DataFrame(
        {
            "Recency": rng.integers(10, 90, 100),
            "Frequency": [1] * 100,
            "Monetary": rng.uniform(50, 200, 100),
            "Cluster": 2,
        }
    )
    # Cluster 3: Em Risco (R alta — antigos)
    c3 = pd.DataFrame(
        {
            "Recency": rng.integers(300, 600, 80),
            "Frequency": rng.integers(1, 3, 80),
            "Monetary": rng.uniform(100, 400, 80),
            "Cluster": 3,
        }
    )
    df = pd.concat([c0, c1, c2, c3], ignore_index=True)
    df["customer_unique_id"] = [f"u{i}" for i in range(len(df))]
    df["Avg_Order_Value"] = df["Monetary"] / df["Frequency"]
    return df


class TestBuildClusterProfile:
    def test_returns_one_row_per_cluster(self):
        rfm = make_4_cluster_rfm()
        profile = build_cluster_profile(rfm)
        assert len(profile) == 4
        assert set(profile["Cluster"]) == {0, 1, 2, 3}

    def test_has_expected_columns(self):
        rfm = make_4_cluster_rfm()
        profile = build_cluster_profile(rfm)
        for col in ["R_mean", "F_mean", "M_mean", "n_clientes"]:
            assert col in profile.columns


class TestDeriveClusterNamesFromProfile:
    def test_returns_4_distinct_names(self):
        """Com K=4, deve retornar 4 nomes distintos."""
        rfm = make_4_cluster_rfm()
        mapping = derive_cluster_names_from_profile(rfm)
        assert len(mapping) == 4
        assert len(set(mapping.values())) == 4, f"Nomes duplicados: {mapping}"

    def test_at_risk_is_highest_recency_cluster(self):
        """Cluster com maior Recency média deve ser 'Em Risco / Hibernando'."""
        rfm = make_4_cluster_rfm()
        # Cluster 3 foi construído com R alta
        mapping = derive_cluster_names_from_profile(rfm)
        assert mapping[3] == BUSINESS_CLUSTER_NAMES["at_risk"]

    def test_champions_has_highest_FxM(self):
        """Cluster 'Campeões' deve ter maior F×M."""
        rfm = make_4_cluster_rfm()
        # Cluster 0 tem alta F E alto M
        mapping = derive_cluster_names_from_profile(rfm)
        assert mapping[0] == BUSINESS_CLUSTER_NAMES["champions"]

    def test_robust_to_id_permutation(self):
        """A nomeação deve depender do PERFIL, não do ID do cluster."""
        rfm = make_4_cluster_rfm()

        # Permuta os IDs: 0↔3, 1↔2
        rfm_permuted = rfm.copy()
        perm = {0: 3, 1: 2, 2: 1, 3: 0}
        rfm_permuted["Cluster"] = rfm_permuted["Cluster"].map(perm)

        m1 = derive_cluster_names_from_profile(rfm)
        m2 = derive_cluster_names_from_profile(rfm_permuted)

        # O cluster que era 0 (Campeões) virou 3 — m2[3] deve ser 'Campeões'
        assert m2[3] == m1[0] == BUSINESS_CLUSTER_NAMES["champions"]
        # O cluster que era 3 (At Risk) virou 0 — m2[0] deve ser 'Em Risco'
        assert m2[0] == m1[3] == BUSINESS_CLUSTER_NAMES["at_risk"]


class TestAssignClusterNames:
    def test_auto_derives_from_profile(self):
        """Sem mapping explícito, deriva do perfil."""
        rfm = make_4_cluster_rfm()
        rfm = assign_cluster_names(rfm)
        assert "Cluster_Name" in rfm.columns
        assert rfm["Cluster_Name"].notna().all()
        # 4 nomes distintos
        assert rfm["Cluster_Name"].nunique() == 4

    def test_at_risk_assigned_correctly(self):
        rfm = make_4_cluster_rfm()
        rfm = assign_cluster_names(rfm)
        # Clientes com Recency > 300 devem ser 'Em Risco / Hibernando'
        old_clients = rfm[rfm["Recency"] > 300]
        assert (old_clients["Cluster_Name"] == BUSINESS_CLUSTER_NAMES["at_risk"]).all()

    def test_raises_on_missing_mapping(self):
        rfm = make_rfm().head(4).copy()
        rfm["Cluster"] = [0, 1, 2, 99]
        # mapping fornecido mas incompleto
        bad_map = {0: "A", 1: "B", 2: "C"}  # falta 99
        with pytest.raises(ValueError, match="sem nome"):
            assign_cluster_names(rfm, mapping=bad_map)

    def test_custom_mapping_overrides_auto(self):
        rfm = make_4_cluster_rfm()
        custom = {0: "Grupo A", 1: "Grupo B", 2: "Grupo C", 3: "Grupo D"}
        rfm = assign_cluster_names(rfm, mapping=custom)
        assert set(rfm["Cluster_Name"].unique()) == set(custom.values())


class TestCalculateClvSimple:
    def test_has_clv_column(self):
        rfm = calculate_clv_simple(make_rfm())
        assert "CLV_12m" in rfm.columns

    def test_clv_is_non_negative(self):
        rfm = calculate_clv_simple(make_rfm())
        assert (rfm["CLV_12m"] >= 0).all()
