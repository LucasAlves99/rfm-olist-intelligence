# tests/test_export.py
"""Testes para src/export.py (exportação tipada para Power BI)."""

import pandas as pd
import pytest

from src.export import (
    build_dim_calendario,
    build_dim_segmentos,
    export_orders_to_powerbi,
    export_rfm_to_powerbi,
    write_powerbi_csv,
)


def test_write_powerbi_csv_formato_br(tmp_path):
    """Deve usar separador ';', decimal ',' e BOM (utf-8-sig)."""
    df = pd.DataFrame({"a": [1.5], "b": ["x"]})
    out = tmp_path / "sub" / "saida.csv"

    write_powerbi_csv(df, out)

    assert out.exists()  # cria diretório pai
    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM
    text = raw.decode("utf-8-sig")
    assert ";" in text
    assert "1,5" in text  # decimal vírgula


def test_export_rfm_adiciona_metadados_e_tipa(tmp_path):
    rfm = pd.DataFrame(
        {
            "customer_unique_id": ["a", "b"],
            "Recency": [10, 20],
            "Frequency": [1, 2],
            "Monetary": [100.123, 200.456],
            "Avg_Order_Value": [100.1, 100.2],
            "R_score": [5, 4],
            "RFM_segment": ["Champions", "Lost"],
            "Cluster": [0, 1],
            "Cluster_Name": ["Campeões", "Em Risco"],
        }
    )
    out = tmp_path / "fato_rfm.csv"

    export_rfm_to_powerbi(rfm, out)

    df = pd.read_csv(out, sep=";", decimal=",", encoding="utf-8-sig")
    assert "dt_exportacao" in df.columns
    assert "versao_modelo" in df.columns
    assert (df["versao_modelo"] == "v1.0").all()
    # Monetary arredondado a 2 casas
    assert df["Monetary"].iloc[0] == pytest.approx(100.12, abs=0.01)


def test_export_orders_lida_com_colunas_opcionais(tmp_path):
    orders = pd.DataFrame(
        {
            "order_id": ["o1", "o2"],
            "customer_unique_id": ["a", "b"],
            "total_payment": [50.0, 75.0],
            "order_purchase_timestamp": ["2018-01-01", "2018-02-01"],
        }
    )
    out = tmp_path / "fato_pedidos.csv"

    export_orders_to_powerbi(orders, out)

    df = pd.read_csv(out, sep=";", decimal=",", encoding="utf-8-sig")
    assert len(df) == 2
    assert set(["order_id", "customer_unique_id", "total_payment"]).issubset(df.columns)


def test_build_dim_segmentos_estrutura():
    dim = build_dim_segmentos()
    assert len(dim) == 4
    for col in ["Cluster_Name", "Descricao", "Cor_Hex", "Acao_CRM", "Prioridade", "Cor_Power_BI"]:
        assert col in dim.columns
    assert dim["Cluster_Name"].is_unique


def test_build_dim_calendario_intervalo_e_colunas():
    dim = build_dim_calendario(start="2018-01-01", end="2018-01-31")
    assert len(dim) == 31
    for col in ["Data", "Ano", "Mes", "Dia", "Trimestre", "FimDeSemana"]:
        assert col in dim.columns
    assert dim["Ano"].iloc[0] == 2018
    assert dim["FimDeSemana"].dtype == bool
