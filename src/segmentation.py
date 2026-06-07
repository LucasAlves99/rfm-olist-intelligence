# src/segmentation.py
"""Segmentação estratégica RFM: scores, segmentos clássicos e nomenclatura de clusters."""

# Standard library
import logging
from typing import Optional

# Third-party
import pandas as pd

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Nomes de negócio para os 4 perfis de cluster (em ordem de "valor" da base).
# ATENÇÃO: NÃO usamos mapeamento por ID do cluster — o KMeans pode atribuir
# IDs diferentes a cada execução. Os nomes são derivados do PERFIL (R/F/M médios).
# ──────────────────────────────────────────────────────────────────────────────
BUSINESS_CLUSTER_NAMES = {
    "champions": "Campeões",  # alta F + alto M + R baixa
    "big_spenders": "Big Spenders (Não-Recorrentes)",  # alto M, F baixa, R variável
    "new_occasional": "Novos / Ocasionais",  # baixa F, baixo M, R recente
    "at_risk": "Em Risco / Hibernando",  # R alta (muito antigo)
}

# Cortes de % acumulada de receita para o segmento por valor (Pareto).
REVENUE_CUTOFF_ELITE = 0.05  # top 5% da receita
REVENUE_CUTOFF_HIGH = 0.15  # próximos 10%
REVENUE_CUTOFF_MID = 0.35  # próximos 20%

# Cortes de recência (em dias) para o segmento por atividade.
RECENCY_DAYS_ACTIVE = 30
RECENCY_DAYS_RECENT = 90
RECENCY_DAYS_WARM = 180

# Janela histórica da base Olist (≈24 meses), usada na frequência mensal do CLV.
HISTORY_MONTHS = 24


def apply_rfm_scores(rfm: pd.DataFrame, q: int = 5) -> pd.DataFrame:
    """Calcula scores R, F, M (1 a 5) e o bucket/score agregado.

    Args:
        rfm: DataFrame com colunas Recency, Frequency, Monetary.
        q: Número de quintis (padrão 5).

    Returns:
        DataFrame com colunas adicionais:
            - R_score, F_score, M_score (int, 1–5)
            - RFM_bucket (str, ex: '555')
            - RFM_score (int, soma dos 3 scores)
            - RFM_segment (str, segmento clássico de negócio)
    """
    required = {"Recency", "Frequency", "Monetary"}
    missing = required - set(rfm.columns)
    if missing:
        raise ValueError(f"rfm não tem as colunas necessárias: {missing}")

    rfm = rfm.copy()

    # Recency: menor = melhor → score maior
    rfm["R_score"] = pd.qcut(
        rfm["Recency"],
        q=q,
        labels=list(range(q, 0, -1)),
        duplicates="drop",
    )

    # Frequency / Monetary: maior = melhor
    rfm["F_score"] = pd.qcut(
        rfm["Frequency"].rank(method="first"),
        q=q,
        labels=list(range(1, q + 1)),
        duplicates="drop",
    )

    rfm["M_score"] = pd.qcut(
        rfm["Monetary"].rank(method="first"),
        q=q,
        labels=list(range(1, q + 1)),
        duplicates="drop",
    )

    # Bucket e score agregado
    rfm["RFM_bucket"] = (
        rfm["R_score"].astype(str) + rfm["F_score"].astype(str) + rfm["M_score"].astype(str)
    )
    rfm["RFM_score"] = (
        rfm["R_score"].astype(int) + rfm["F_score"].astype(int) + rfm["M_score"].astype(int)
    )

    # Segmento clássico
    rfm["RFM_segment"] = rfm.apply(_rfm_segment_row, axis=1)

    logger.info(
        f"RFM scores aplicados. Segmentos:\n{rfm['RFM_segment'].value_counts().to_string()}"
    )
    return rfm


def _rfm_segment_row(row: pd.Series) -> str:
    """Classifica um cliente em segmento clássico de negócio (uso interno).

    Nota: No Olist, Frequency é quase sempre 1 — as regras são ajustadas
    para não concentrar tudo em "New Customers".
    """
    r = int(row["R_score"])
    f = int(row["F_score"])
    m = int(row["M_score"])

    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if r >= 4 and f >= 3 and m >= 3:
        return "Loyal Customers"
    if r >= 4 and m >= 4 and f <= 3:
        return "Big Spenders (New/Occasional)"
    if r == 5 and f <= 2:
        return "New Customers"
    if r >= 3 and f <= 2 and m <= 2:
        return "Potential Loyalists"
    if r <= 2 and (f >= 4 or m >= 4):
        return "At Risk"
    if r == 1 and f == 1 and m == 1:
        return "Lost"
    return "Others"


def apply_strategic_segments(rfm: pd.DataFrame) -> pd.DataFrame:
    """Aplica segmentação estratégica por receita e recência.

    Args:
        rfm: DataFrame com colunas Recency e Monetary.

    Returns:
        DataFrame com colunas adicionais:
            - cum_revenue_pct (float): % acumulada de receita
            - Revenue_segment (str): Elite / High Value / Mid Value / Base
            - Recency_segment (str): Ativo / Recente / Morno / Em Risco
            - Strategic_segment (str): combinação revenue + recência
    """
    rfm = rfm.copy().sort_values("Monetary", ascending=False).reset_index(drop=True)

    # Segmentação por contribuição de receita
    rfm["cum_revenue_pct"] = rfm["Monetary"].cumsum() / rfm["Monetary"].sum()
    rfm["Revenue_segment"] = rfm["cum_revenue_pct"].apply(_revenue_segment)

    # Segmentação por recência real (dias)
    rfm["Recency_segment"] = rfm["Recency"].apply(_recency_segment)

    # Segmento final combinando os dois
    rfm["Strategic_segment"] = rfm["Revenue_segment"] + " - " + rfm["Recency_segment"]

    logger.info(
        f"Segmentos estratégicos aplicados:\n"
        f"{rfm['Strategic_segment'].value_counts().head(10).to_string()}"
    )
    return rfm


def _revenue_segment(cum_pct: float) -> str:
    if cum_pct <= REVENUE_CUTOFF_ELITE:
        return "Elite (Top 5%)"
    elif cum_pct <= REVENUE_CUTOFF_HIGH:
        return "High Value (Next 10%)"
    elif cum_pct <= REVENUE_CUTOFF_MID:
        return "Mid Value (Next 20%)"
    return "Base"


def _recency_segment(days: int) -> str:
    if days <= RECENCY_DAYS_ACTIVE:
        return "Ativo"
    elif days <= RECENCY_DAYS_RECENT:
        return "Recente"
    elif days <= RECENCY_DAYS_WARM:
        return "Morno"
    return "Em Risco"


def build_cluster_profile(rfm: pd.DataFrame) -> pd.DataFrame:
    """Calcula o perfil médio de cada cluster (Recency, Frequency, Monetary).

    Args:
        rfm: DataFrame com colunas Cluster, Recency, Frequency, Monetary.

    Returns:
        DataFrame com uma linha por cluster e colunas:
            R_mean, F_mean, M_mean, AOV_mean (se Avg_Order_Value existir),
            n_clientes.
    """
    agg_dict = {
        "R_mean": ("Recency", "mean"),
        "F_mean": ("Frequency", "mean"),
        "M_mean": ("Monetary", "mean"),
        "n_clientes": ("Recency", "count"),
    }
    if "Avg_Order_Value" in rfm.columns:
        agg_dict["AOV_mean"] = ("Avg_Order_Value", "mean")

    return rfm.groupby("Cluster").agg(**agg_dict).reset_index()


def derive_cluster_names_from_profile(rfm: pd.DataFrame) -> dict:
    """Deriva o mapeamento {cluster_id: nome_de_negocio} a partir do perfil R/F/M.

    Estratégia (robusta a mudanças de IDs entre execuções do KMeans):

    1. **Em Risco / Hibernando** = cluster com MAIOR Recency média (clientes mais antigos)
    2. **Campeões**              = cluster com MAIOR (Frequency × Monetary) entre os restantes
    3. **Big Spenders**          = cluster com MAIOR Monetary entre os 2 restantes
    4. **Novos / Ocasionais**    = o último cluster restante

    Garante que K=4 produz **4 nomes DISTINTOS** sempre, independentemente do
    ID atribuído pelo KMeans em cada treino.

    Args:
        rfm: DataFrame com colunas Cluster, Recency, Frequency, Monetary.

    Returns:
        Dicionário {cluster_id (int): nome de negócio (str)}.

    Raises:
        ValueError: Se houver número inesperado de clusters (suportado: 4).
    """
    profile = build_cluster_profile(rfm)
    n_clusters = len(profile)

    if n_clusters != 4:
        logger.warning(
            f"derive_cluster_names_from_profile foi calibrado para K=4 "
            f"(detectado K={n_clusters}). Nomes podem ficar genéricos."
        )

    # Score combinado de "valor + recorrência" (usado para identificar Campeões)
    profile["FxM_score"] = profile["F_mean"] * profile["M_mean"]

    mapping: dict = {}
    remaining = profile.copy()

    # 1) Em Risco / Hibernando = maior Recency média
    at_risk_id = int(remaining.loc[remaining["R_mean"].idxmax(), "Cluster"])
    mapping[at_risk_id] = BUSINESS_CLUSTER_NAMES["at_risk"]
    remaining = remaining[remaining["Cluster"] != at_risk_id]

    # 2) Campeões = maior FxM_score entre os restantes
    if len(remaining) > 0:
        champ_id = int(remaining.loc[remaining["FxM_score"].idxmax(), "Cluster"])
        mapping[champ_id] = BUSINESS_CLUSTER_NAMES["champions"]
        remaining = remaining[remaining["Cluster"] != champ_id]

    # 3) Big Spenders = maior Monetary entre os 2 restantes (alto M, F baixa)
    if len(remaining) > 0:
        spender_id = int(remaining.loc[remaining["M_mean"].idxmax(), "Cluster"])
        mapping[spender_id] = BUSINESS_CLUSTER_NAMES["big_spenders"]
        remaining = remaining[remaining["Cluster"] != spender_id]

    # 4) Novos / Ocasionais = o que sobrar (baixo M, baixa F, R relativamente recente)
    for cid in remaining["Cluster"].astype(int).tolist():
        mapping[cid] = BUSINESS_CLUSTER_NAMES["new_occasional"]

    # Log do perfil + nome atribuído (auditoria)
    logger.info("Perfil dos clusters → nome de negócio derivado:")
    for _, row in profile.iterrows():
        cid = int(row["Cluster"])
        logger.info(
            f"  Cluster {cid}: R̄={row['R_mean']:.0f}d | F̄={row['F_mean']:.2f} | "
            f"M̄=R${row['M_mean']:.2f} | n={int(row['n_clientes']):,} → {mapping[cid]}"
        )

    return mapping


def assign_cluster_names(
    rfm: pd.DataFrame,
    mapping: Optional[dict] = None,
) -> pd.DataFrame:
    """Atribui nomes de negócio aos clusters DERIVADOS DO PERFIL R/F/M.

    Por padrão, calcula o mapeamento automaticamente a partir do perfil de cada
    cluster — o que é robusto a mudanças de ID entre execuções do KMeans.

    Args:
        rfm: DataFrame com colunas Cluster, Recency, Frequency, Monetary.
        mapping: (Opcional) Dicionário {cluster_id (int): nome (str)} para
            forçar nomes específicos (ex: em testes). Se None, deriva
            automaticamente via derive_cluster_names_from_profile().

    Returns:
        DataFrame com coluna 'Cluster_Name' adicionada.

    Raises:
        ValueError: Se algum cluster ficar sem nome no mapping fornecido.
    """
    rfm = rfm.copy()

    if mapping is None:
        mapping = derive_cluster_names_from_profile(rfm)

    rfm["Cluster_Name"] = rfm["Cluster"].map(mapping)

    if rfm["Cluster_Name"].isna().any():
        unmapped = rfm[rfm["Cluster_Name"].isna()]["Cluster"].unique().tolist()
        raise ValueError(
            f"Clusters sem nome no mapping: {unmapped}. "
            "Verifique se o mapping cobre todos os IDs de cluster presentes."
        )

    logger.info(f"Cluster_Name atribuído:\n{rfm['Cluster_Name'].value_counts().to_string()}")
    return rfm


def calculate_clv_simple(rfm: pd.DataFrame, horizon_months: int = 12) -> pd.DataFrame:
    """Calcula uma projeção simples de Customer Lifetime Value (CLV).

    Fórmula: AOV × frequência mensal estimada × horizonte

    Args:
        rfm: DataFrame com colunas Avg_Order_Value e Frequency.
        horizon_months: Horizonte de projeção em meses (padrão: 12).

    Returns:
        DataFrame com colunas adicionais:
            - Freq_Mensal (float): frequência mensal estimada
            - CLV_12m (float): CLV projetado no horizonte dado
    """
    rfm = rfm.copy()
    rfm["Freq_Mensal"] = rfm["Frequency"] / HISTORY_MONTHS
    rfm["CLV_12m"] = (rfm["Avg_Order_Value"] * rfm["Freq_Mensal"] * horizon_months).round(2)
    logger.info(f"CLV simples calculado. Média CLV_12m: R${rfm['CLV_12m'].mean():.2f}")
    return rfm
