# src/config.py
"""Carrega e expõe o config.yaml centralizado do projeto."""

# Standard library
from pathlib import Path

# Third-party
import yaml


def load_config(path: str = "config/config.yaml") -> dict:
    """Carrega o arquivo de configuração YAML.

    Args:
        path: Caminho para o config.yaml (relativo à raiz do projeto).

    Returns:
        Dicionário com os parâmetros do projeto.

    Raises:
        FileNotFoundError: Se o arquivo não existir.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {config_path.resolve()}")

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


CONFIG = load_config()
