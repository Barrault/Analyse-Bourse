"""Tests du chargement de configuration (remplacent les anciens scripts sans assertion)."""
from config_loader import config, get_fee_structure


def test_config_exposes_main_sections():
    for section in ("indicators", "scoring", "trading", "fees", "backtest", "output"):
        assert config.get_section(section), section


def test_dotted_path_lookup():
    assert config.get("indicators.sma.long_window") == 200


def test_fee_structure_is_ordered_and_ends_with_percentage_tier():
    tiers = get_fee_structure()
    bounded = [t["max_amount"] for t in tiers if t["max_amount"] is not None]
    assert bounded == sorted(bounded)
    assert tiers[-1]["max_amount"] is None
    assert "percentage_fee" in tiers[-1]
