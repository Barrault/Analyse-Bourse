"""Tests du scoring technique et fondamental."""
from cac40_analyzer import compute_score, format_recommendation_summary


def test_value_stock_scores_higher_than_overvalued_stock_with_same_technicals(snapshot):
    strong = compute_score(snapshot(pe=3.3, pb=0.4, dy=3.0))["score"]
    weak = compute_score(snapshot(pe=16.8, pb=2.0, dy=3.0))["score"]
    assert strong - weak > 2.0


def test_loss_making_company_is_penalised_even_without_pe(snapshot):
    # yfinance renvoie trailingPE=None pour une perte : seul le BPA la révèle (S1)
    unknown = compute_score(snapshot(pe=None, pb=0.5, eps=None))["score"]
    losing = compute_score(snapshot(pe=None, pb=0.5, eps=-11.0))["score"]
    assert losing < unknown


def test_loss_making_company_gets_high_conviction_sell(snapshot):
    outcome = compute_score(snapshot(pe=None, pb=0.5, eps=-11.0, bullish=False))
    assert outcome["recommendation"] == "VENTE"
    assert outcome["confidence"] >= 0.9
    assert any("Vente de conviction" in reason for reason in outcome["reasons"])


def test_high_price_to_book_is_not_toxic(snapshot):
    # Profil type luxe : P/B élevé mais bénéficiaire -> pas de vente "de conviction" (S2)
    outcome = compute_score(snapshot(pe=18.0, pb=2.9, dy=1.5, eps=13.0, bullish=False))
    assert outcome["recommendation"] == "VENTE"
    assert not any("Vente de conviction" in reason for reason in outcome["reasons"])


def test_pe_contributes_once_per_bracket(snapshot):
    # Sans terme continu, deux PE de la même tranche donnent le même score (S3)
    assert compute_score(snapshot(pe=9.0))["score"] == compute_score(snapshot(pe=13.0))["score"]


def test_no_dividend_is_penalised(snapshot):
    with_dividend = compute_score(snapshot(dy=3.0))["score"]
    without = compute_score(snapshot(dy=0.0))["score"]
    assert without < with_dividend


def test_recommendation_summary_includes_price_and_action():
    summary = format_recommendation_summary(
        company_name="Pernod Ricard",
        recommendation="ACHAT",
        confidence=0.42,
        suggested_amount=16.67,
        price=152.34,
    )
    for expected in ("Pernod Ricard", "ACHAT", "152.34", "16.67"):
        assert expected in summary
