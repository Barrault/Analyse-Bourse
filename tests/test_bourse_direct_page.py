"""Lecture de la page « Mes portefeuilles » de Bourse Direct (DEC-28), sur une copie anonymisée."""
from pathlib import Path

import pytest

from bourse_direct_page import parse_number, parse_positions_page
from rebalance import Holding

PAGE = (Path(__file__).parent / "fixtures" / "bourse_direct_positions.html").read_text(encoding="utf-8")


def test_positions_cash_and_account_are_read_from_the_page():
    page = parse_positions_page(["<html><body>cadre publicitaire</body></html>", PAGE])
    assert (page.account, page.account_type, page.cash) == ("508TI00000000001EUR", "PEA", 1234.56)
    assert page.holdings == [
        Holding("BNP PARIBAS ACT.A", "", 90.0, 4, 100.5, ticker="BNP.PA"),
        Holding("Amundi PEA S&P 500 UCITS ETF A", "", 60.73, 12, 61.235, ticker="PSP5.PA"),
        Holding("APPLE INC", "", 1210.4, 1, 1150.0, ticker=None),  # Nasdaq : décision manuelle
        Holding("ArcelorMittal", "", 25.1, 8, 20.0, ticker="MT.AS"),  # Amsterdam, dans l'univers
        Holding("CANAL+", "", 2.56502, 20, 3.4477, ticker=None),  # sans fiche Bourse Direct (href="#")
    ]


def test_the_displayed_account_must_be_unambiguous():
    # Aucune carte, ou deux cartes, annoncent autant d'actifs que de lignes : refus plutôt que deviner
    with pytest.raises(ValueError, match="compte affiché"):
        parse_positions_page([PAGE.replace("5 actifs", "4 actifs")])
    with pytest.raises(ValueError, match="compte affiché"):
        parse_positions_page([PAGE.replace("7 actifs", "5 actifs")])


def test_another_page_is_rejected():
    with pytest.raises(ValueError, match="page des positions introuvable"):
        parse_positions_page(["<html><body><div id='portfolio-react'></div></body></html>"])


@pytest.mark.parametrize("text, value", [("3 920.79 €", 3920.79), ("-19,83 %", -19.83), ("86.40 ", 86.4)])
def test_numbers_as_displayed(text, value):
    assert parse_number(text) == value
