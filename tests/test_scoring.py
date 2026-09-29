import unittest

import pandas as pd

from cac40_analyzer import IndicatorSnapshot, compute_score, format_recommendation_summary


def make_snapshot(pe, pb, dy):
    return IndicatorSnapshot(
        date=pd.Timestamp("2024-01-01"),
        close=100.0,
        sma20=100.0,
        sma50=100.0,
        sma200=95.0,
        rsi14=55.0,
        macd=1.0,
        macd_signal=0.0,
        macd_hist=0.5,
        bb_mid=100.0,
        bb_upper=105.0,
        bb_lower=95.0,
        atr14=2.0,
        vol=1_000_000.0,
        vol_sma20=900_000.0,
        fundamentals={"trailingPE": pe, "priceToBook": pb, "dividendYield": dy},
    )


class ScoringTests(unittest.TestCase):
    def test_value_stock_scores_higher_than_overvalued_stock_with_same_technicals(self):
        strong = make_snapshot(3.3, 0.4, 3.0)
        weak = make_snapshot(16.8, 2.0, 3.0)

        strong_score = compute_score(strong)["score"]
        weak_score = compute_score(weak)["score"]

        self.assertGreater(strong_score, weak_score)
        self.assertGreater(strong_score - weak_score, 2.0)

    def test_recommendation_summary_includes_price_and_action(self):
        summary = format_recommendation_summary(
            company_name="Pernod Ricard",
            recommendation="ACHAT",
            confidence=0.42,
            suggested_amount=16.67,
            price=152.34,
        )

        self.assertIn("Pernod Ricard", summary)
        self.assertIn("ACHAT", summary)
        self.assertIn("152.34", summary)
        self.assertIn("16.67", summary)


if __name__ == "__main__":
    unittest.main()
