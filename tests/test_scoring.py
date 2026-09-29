"""Tests du scoring technique et fondamental."""
from cac40_analyzer import compute_score, format_recommendation_summary
from config_loader import config


def test_fundamentals_do_not_change_score_nor_recommendation(snapshot):
    # Non testables : information seulement (DEC-24)
    cheap = compute_score(snapshot(pe=3.3, pb=0.4, dy=9.0, eps=5.0))
    expensive = compute_score(snapshot(pe=45.0, pb=9.0, dy=0.0, eps=5.0))
    assert cheap["score"] == expensive["score"] == cheap["technical_score"]
    assert cheap["recommendation"] == expensive["recommendation"] == "ACHAT"
    assert any("PE 3.3 | P/B 0.4 | dividende 9.0 %" in r for r in cheap["reasons"])


def test_loss_making_company_buy_is_filtered_out(snapshot):
    outcome = compute_score(snapshot(pe=None, pb=0.5, eps=-11.0))
    assert outcome["recommendation"] == "NEUTRE"
    assert any("Achat écarté" in reason for reason in outcome["reasons"])


def test_loss_filter_can_be_disabled(snapshot, monkeypatch):
    monkeypatch.setitem(config.get_section("fundamentals"), "exclude_loss_making", False)
    assert compute_score(snapshot(pe=None, pb=0.5, eps=-11.0))["recommendation"] == "ACHAT"


def test_loss_making_sell_is_flagged(snapshot):
    outcome = compute_score(snapshot(pe=None, pb=0.5, eps=-11.0, bullish=False))
    assert outcome["recommendation"] == "VENTE"
    assert any("Entreprise en perte" in reason for reason in outcome["reasons"])


def test_recommendation_summary_includes_price_and_action():
    summary = format_recommendation_summary(
        company_name="Pernod Ricard",
        recommendation="ACHAT",
        confidence=0.42,
        suggested_amount=16.67,
        price=152.34,
        technical_score=5.5,
    )
    for expected in ("Pernod Ricard", "ACHAT", "152.34", "16.67", "Score technique: +5.5"):
        assert expected in summary


def test_zero_weight_components_neither_score_nor_show_a_reason(snapshot):
    # RSI > 70 : poids mis à 0 faute d'effet mesuré (DEC-19)
    overbought = snapshot()
    overbought.rsi14 = 80.0
    outcome = compute_score(overbought)
    assert not any("RSI" in reason for reason in outcome["reasons"])
    assert outcome["technical_score"] == compute_score(snapshot())["technical_score"]
