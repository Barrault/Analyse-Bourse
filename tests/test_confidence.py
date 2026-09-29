"""Tests de la confiance calibrée (DEC-20) et du montant suggéré."""
import pytest

from cac40_analyzer import compute_score, order_amount_for_confidence, outperformance_probability
from config_loader import config


def test_probability_is_read_from_the_calibrated_table():
    calibration = config.get("scoring.confidence_calibration")
    edges, probabilities = calibration["score_edges"], calibration["probabilities"]
    assert outperformance_probability(edges[0] - 1) == probabilities[0]
    assert outperformance_probability(edges[-1]) == probabilities[-1]  # borne incluse à droite
    assert outperformance_probability(100) == probabilities[-1]


def test_calibrated_probabilities_never_decrease_with_the_score():
    probabilities = config.get("scoring.confidence_calibration.probabilities")
    assert probabilities == sorted(probabilities)


def test_confidence_is_the_probability_of_being_right(snapshot):
    buy = compute_score(snapshot(pe=10.0, pb=1.1, dy=5.5, eps=5.0))
    sell = compute_score(snapshot(pe=18.0, pb=2.9, bullish=False))
    assert buy["recommendation"] == "ACHAT"
    assert buy["confidence"] == pytest.approx(buy["p_outperform"], abs=1e-3)
    assert sell["recommendation"] == "VENTE"
    assert sell["confidence"] == pytest.approx(1 - sell["p_outperform"], abs=1e-3)


def test_fundamentals_do_not_change_the_confidence(snapshot):
    # Seul le score technique est calibrable : les fondamentaux changent la recommandation
    # et les motifs, pas la probabilité (DEC-20)
    losing = compute_score(snapshot(pe=None, pb=0.5, eps=-11.0))
    healthy = compute_score(snapshot(pe=10.0, pb=1.1, eps=5.0))
    assert losing["p_outperform"] == healthy["p_outperform"]


def test_only_buy_signals_get_a_suggested_amount(snapshot):
    bearish = compute_score(snapshot(pe=18.0, pb=2.9, bullish=False))
    assert bearish["suggested_amount"] == 0.0
    bullish = compute_score(snapshot(pe=10.0, pb=1.1, dy=5.5, eps=5.0))
    assert bullish["suggested_amount"] == pytest.approx(order_amount_for_confidence(bullish["confidence"]), abs=0.01)
