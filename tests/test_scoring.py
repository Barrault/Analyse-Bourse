"""Tests du scoring technique et fondamental."""
import pandas as pd
import pytest

from cac40_analyzer import IndicatorSnapshot, compute_score, format_recommendation_summary


def make_snapshot(pe=None, pb=None, dy=None, eps=None, bullish=True):
    """Instantané aux indicateurs techniques haussiers (ou baissiers) et fondamentaux donnés."""
    if bullish:
        technicals = dict(close=100.0, sma20=100.0, sma50=100.0, sma200=95.0, rsi14=55.0,
                          macd=1.0, macd_hist=0.5, bb_lower=95.0)
    else:
        technicals = dict(close=80.0, sma20=85.0, sma50=90.0, sma200=100.0, rsi14=40.0,
                          macd=-1.0, macd_hist=-0.5, bb_lower=75.0)
    return IndicatorSnapshot(
        date=pd.Timestamp("2024-01-01"),
        macd_signal=0.0,
        bb_mid=100.0,
        bb_upper=105.0,
        atr14=2.0,
        vol=1_000_000.0,
        vol_sma20=900_000.0,
        fundamentals={"trailingPE": pe, "priceToBook": pb, "dividendYield": dy, "trailingEps": eps},
        **technicals,
    )


def test_value_stock_scores_higher_than_overvalued_stock_with_same_technicals():
    strong = compute_score(make_snapshot(pe=3.3, pb=0.4, dy=3.0))["score"]
    weak = compute_score(make_snapshot(pe=16.8, pb=2.0, dy=3.0))["score"]
    assert strong - weak > 2.0


def test_loss_making_company_is_penalised_even_without_pe():
    # yfinance renvoie trailingPE=None pour une perte : seul le BPA la révèle (S1)
    unknown = compute_score(make_snapshot(pe=None, pb=0.5, eps=None))["score"]
    losing = compute_score(make_snapshot(pe=None, pb=0.5, eps=-11.0))["score"]
    assert losing < unknown


def test_loss_making_company_gets_high_conviction_sell():
    outcome = compute_score(make_snapshot(pe=None, pb=0.5, eps=-11.0, bullish=False))
    assert outcome["recommendation"] == "VENTE"
    assert outcome["confidence"] >= 0.9
    assert any("Vente de conviction" in reason for reason in outcome["reasons"])


def test_high_price_to_book_is_not_toxic():
    # Profil type luxe : P/B élevé mais bénéficiaire -> pas de vente "de conviction" (S2)
    outcome = compute_score(make_snapshot(pe=18.0, pb=2.9, dy=1.5, eps=13.0, bullish=False))
    assert outcome["recommendation"] == "VENTE"
    assert not any("Vente de conviction" in reason for reason in outcome["reasons"])


def test_pe_contributes_once_per_bracket():
    # Sans terme continu, deux PE de la même tranche donnent le même score (S3)
    assert compute_score(make_snapshot(pe=9.0))["score"] == compute_score(make_snapshot(pe=13.0))["score"]


def test_no_dividend_is_penalised():
    with_dividend = compute_score(make_snapshot(dy=3.0))["score"]
    without = compute_score(make_snapshot(dy=0.0))["score"]
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
