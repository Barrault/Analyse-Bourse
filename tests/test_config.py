"""Tests du chargement de configuration."""
import pytest

from config_loader import config


def test_config_exposes_main_sections():
    for section in ("indicators", "scoring", "trading", "fees", "backtest", "output"):
        assert config.get_section(section), section


def test_dotted_path_lookup():
    assert config.get("indicators.sma.long_window") == 200


def test_missing_key_raises_instead_of_returning_none():
    with pytest.raises(KeyError, match="scoring.tresholds.buy"):
        config.get("scoring.tresholds.buy")


def test_missing_key_with_explicit_default():
    assert config.get("scoring.does_not_exist", default=42) == 42


def test_fee_structure_is_ordered_and_ends_with_percentage_tier():
    tiers = config.get("fees.structure")
    bounded = [t["max_amount"] for t in tiers if t["max_amount"] is not None]
    assert bounded == sorted(bounded)
    assert tiers[-1]["max_amount"] is None
    assert "percentage_fee" in tiers[-1]
