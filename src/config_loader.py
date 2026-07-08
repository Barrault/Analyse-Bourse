"""
Configuration Loader - Charge les paramètres depuis config.yaml
"""
# -*- coding: utf-8 -*-
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

class ConfigLoader:
    """Gestionnaire de configuration pour le CAC40 Analyzer."""

    _instance: Optional['ConfigLoader'] = None
    _config: Optional[Dict[str, Any]] = None

    def __new__(cls):
        """Singleton pattern - une seule instance de configuration."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialise le loader de configuration."""
        if self._config is None:
            self._config = self._load_config()

    @staticmethod
    def _load_config() -> Dict[str, Any]:
        """Charge le fichier config.yaml."""
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        if config is None:
            raise ValueError("Configuration file is empty or invalid")

        return config

    def get(self, path: str, default: Any = None) -> Any:
        """
        Récupère une valeur de la configuration par chemin (ex: 'indicators.sma.short_window').

        Args:
            path: Chemin dans la config, séparé par des points (ex: "indicators.sma.short_window")
            default: Valeur par défaut si non trouvée

        Returns:
            La valeur de la configuration
        """
        keys = path.split('.')
        value = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_section(self, section: str) -> Dict[str, Any]:
        """Récupère une section complète de la configuration."""
        return self._config.get(section, {})

    def reload(self):
        """Recharge la configuration depuis le fichier."""
        self._config = self._load_config()

    def get_all(self) -> Dict[str, Any]:
        """Retourne toute la configuration."""
        return self._config.copy()


# Instance globale singleton
config = ConfigLoader()


# ==================== Fonctions de commodité ====================

def get_indicator_params(indicator_name: str) -> Dict[str, Any]:
    """Récupère les paramètres d'un indicateur."""
    return config.get_section('indicators').get(indicator_name, {})


def get_scoring_weights() -> Dict[str, Any]:
    """Récupère tous les poids de scoring."""
    return config.get_section('scoring')


def get_trading_params() -> Dict[str, Any]:
    """Récupère les paramètres de trading."""
    return config.get_section('trading')


def get_fee_structure() -> list:
    """Récupère la structure tarifaire."""
    return config.get('fees.structure', [])


def get_backtest_params() -> Dict[str, Any]:
    """Récupère les paramètres de backtest."""
    return config.get_section('backtest')


# Validation basique
if __name__ == "__main__":
    print("Configuration Loader Test\n")
    print("✓ Configuration loaded successfully\n")
    print(f"✓ SMA short window: {get_indicator_params('sma')['short_window']}")
    print(f"✓ Buy threshold: {config.get('scoring.thresholds.buy')}")
    print(f"✓ Initial cash: {get_trading_params()['initial_cash']}")
    print(f"✓ Backtest period: {config.get('backtest.start_date')} to {config.get('backtest.end_date')}")
