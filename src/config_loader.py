"""
Configuration Loader - Charge les paramètres depuis config/config.yaml
"""
# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Any, Dict

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.yaml"

_MISSING = object()


class ConfigLoader:
    """Accès en lecture à la configuration YAML, par chemin pointé."""

    def __init__(self, path: Path = CONFIG_PATH):
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            self._config: Dict[str, Any] = yaml.safe_load(f) or {}
        if not self._config:
            raise ValueError("Configuration file is empty or invalid")

    def get(self, path: str, default: Any = _MISSING) -> Any:
        """
        Récupère une valeur par chemin pointé (ex: 'indicators.sma.short_window').

        Sans `default`, une clé absente lève KeyError : une faute de frappe dans le YAML
        doit échouer immédiatement plutôt que produire un `None` silencieux.
        """
        value: Any = self._config
        for key in path.split("."):
            if isinstance(value, dict) and key in value:
                value = value[key]
            elif default is _MISSING:
                raise KeyError(f"Clé de configuration manquante : '{path}' (dans {CONFIG_PATH.name})")
            else:
                return default
        return value

    def get_section(self, section: str) -> Dict[str, Any]:
        """Récupère une section complète de la configuration (KeyError si absente)."""
        return self.get(section)


# Instance partagée par tous les modules
config = ConfigLoader()
