# tests/test_config.py
"""Testes para src/config.py (carregamento do YAML centralizado)."""

import pytest

from src.config import CONFIG, load_config


def test_config_global_tem_secoes_esperadas():
    for secao in ["paths", "rfm", "clustering", "export"]:
        assert secao in CONFIG
    assert CONFIG["clustering"]["k_clusters"] == 4


def test_load_config_arquivo_inexistente():
    with pytest.raises(FileNotFoundError):
        load_config("config/nao_existe.yaml")


def test_load_config_le_yaml(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("rfm:\n  q_score: 5\n", encoding="utf-8")
    cfg = load_config(str(p))
    assert cfg["rfm"]["q_score"] == 5
