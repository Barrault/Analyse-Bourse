"""Tests de la confiance des signaux et du dimensionnement des ordres."""
import pytest

from cac40_analyzer import compute_score, order_amount_for_confidence, signal_confidence
from config_loader import config


def test_confidence_is_half_at_threshold_and_keeps_discriminating_beyond():
    assert signal_confidence(0) == 0.5
    # L'ancienne formule saturait à 1.0 dès 2 points au-dessus du seuil d'achat (S4)
    assert signal_confidence(2) < signal_confidence(4) < 1.0
    assert signal_confidence(config.get("scoring.confidence_scale")) == 1.0
    assert signal_confidence(100) == 1.0


def test_order_amount_scales_linearly_between_min_and_max():
    assert order_amount_for_confidence(0.0, min_order=100, max_order=1000) == 100
    assert order_amount_for_confidence(1.0, min_order=100, max_order=1000) == 1000
    assert order_amount_for_confidence(0.6, min_order=100, max_order=1000) == pytest.approx(550)


def test_only_buy_signals_get_a_suggested_amount(snapshot):
    bearish = compute_score(snapshot(pe=18.0, pb=2.9, bullish=False))
    assert bearish["recommendation"] == "VENTE"
    assert bearish["suggested_amount"] == 0.0

    bullish = compute_score(snapshot(pe=10.0, pb=1.1, dy=5.5, eps=5.0))
    assert bullish["recommendation"] == "ACHAT"
    assert bullish["suggested_amount"] == pytest.approx(order_amount_for_confidence(bullish["confidence"]), abs=0.01)
