"""Tests du plan de rebalance mensuel (DEC-25), sans réseau."""
import zipfile
from datetime import datetime
from types import SimpleNamespace

import pytest

import rebalance
from rebalance import Holding, build_plan, find_latest_exports, market_hours_warning, read_positions

NS = "http://purl.oclc.org/ooxml/spreadsheetml/main"  # Strict OOXML, comme l'export Bourse Direct


def write_export(path, rows):
    def cell(ref, value):
        if isinstance(value, str):
            return f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>'
        return f'<c r="{ref}" t="n"><v>{value}</v></c>'
    body = "".join(
        f'<row r="{i}">' + "".join(cell(f"{chr(65 + j)}{i}", v) for j, v in enumerate(row)) + "</row>"
        for i, row in enumerate(rows, 1))
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{NS}"><sheetData>{body}</sheetData></worksheet>')


HEADER = ["Nom", "ISIN", "Cours", "Devise", "Variation Veille %", "Quantité", "PRU (EUR)",
          "+/- value (EUR)", "+/- value %", "Valorisation (EUR)", "Règlement", "MIC", "Marché"]


def test_read_positions_from_a_strict_ooxml_export(tmp_path):
    path = tmp_path / "X.xlsx"
    write_export(path, [HEADER, ["BNP PARIBAS ACT.A", "FR0000131104", 97.66, "EUR", -0.006, 4, 107.775,
                                 -40.46, -0.09, 390.64, "cash", "XPAR", "EURONEXT PARIS"]])
    (holding,) = read_positions(path)
    assert holding == Holding("BNP PARIBAS ACT.A", "FR0000131104", 97.66, 4, 107.775)


def test_latest_export_is_chosen_by_the_date_in_its_name(tmp_path):
    for name in ["508TI0EUR-29_09_2026 16_32_37.xlsx", "508TI0EUR-01_10_2026 08_15_00.xlsx",
                 "508TI0EUR-30_09_2026 23_59_59.xlsx", "autre.xlsx"]:
        (tmp_path / name).write_bytes(b"")
    assert [p.name for p in find_latest_exports(tmp_path)] == ["508TI0EUR-01_10_2026 08_15_00.xlsx"]
    with pytest.raises(FileNotFoundError):
        find_latest_exports(tmp_path / "vide")


def test_only_accounts_exported_on_the_latest_date_are_kept(tmp_path):
    # PEA exporté le 1er octobre ; CTO le 1er et deux fois le 2 : seul le dernier export du CTO
    for name in ["PEA0EUR-01_10_2026 08_00_00.xlsx", "CTO0EUR-01_10_2026 08_05_00.xlsx",
                 "CTO0EUR-02_10_2026 08_10_00.xlsx", "CTO0EUR-02_10_2026 07_50_00.xlsx"]:
        (tmp_path / name).write_bytes(b"")
    assert [p.name for p in find_latest_exports(tmp_path)] == ["CTO0EUR-02_10_2026 08_10_00.xlsx"]
    # Les deux comptes exportés le même jour : un export par compte
    (tmp_path / "PEA0EUR-02_10_2026 07_00_00.xlsx").write_bytes(b"")
    assert [p.name for p in find_latest_exports(tmp_path)] == ["CTO0EUR-02_10_2026 08_10_00.xlsx",
                                                                "PEA0EUR-02_10_2026 07_00_00.xlsx"]


def signal(recommendation, close, confidence=0.493, technical=5.5):
    return ({"recommendation": recommendation, "confidence": confidence, "technical_score": technical},
            SimpleNamespace(close=close))


def test_plan_applies_the_tested_rules():
    holdings = [
        Holding("BNP", "I1", 100.0, 4, 100.0),        # signal VENTE
        Holding("Lacroix", "I2", 16.0, 25, 20.0),     # -20 % : stop-loss
        Holding("Total", "I3", 78.0, 6, 79.0),        # NEUTRE : conserver
        Holding("ETF levier", "I4", 43.0, 21, 47.7),  # hors univers
    ]
    tickers = {"I1": "BNP.PA", "I2": "LACR.PA", "I3": "TTE.PA", "I4": "LVC.PA"}
    analyses = {"BNP.PA": signal("VENTE", 100.0), "LACR.PA": signal("NEUTRE", 16.0),
                "TTE.PA": signal("NEUTRE", 78.0), "AC.PA": signal("ACHAT", 40.0, technical=4.5),
                "SAN.PA": signal("ACHAT", 90.0, technical=6.5), "RMS.PA": signal("ACHAT", 2100.0)}

    plan = build_plan(holdings, tickers, analyses, cash=1500.0)

    assert [(s["name"], s["reason"].split(" ")[0]) for s in plan.sells] == [("BNP", "signal"), ("Lacroix", "stop-loss")]
    assert [k["name"] for k in plan.keeps] == ["Total"]
    assert [m["ticker"] for m in plan.manual] == ["LVC.PA"]
    # Priorité : confiance puis score technique ; 1 000 € par ligne, actions entières
    assert [b["ticker"] for b in plan.buys] == ["SAN.PA", "AC.PA"]
    assert plan.buys[0]["quantity"] == 11 and plan.buys[0]["cost"] <= 1000
    assert "dépasse le budget" in plan.skipped_buys[0]["reason"]  # Hermès à 2 100 €
    assert plan.cash_end >= 200 - 1e-9                            # réserve préservée


def test_buys_stop_when_cash_runs_out():
    analyses = {t: signal("ACHAT", 10.0) for t in ["AC.PA", "SAN.PA", "BNP.PA"]}
    plan = build_plan([], {}, analyses, cash=1400.0)
    assert len(plan.buys) == 2  # 1 000 €, puis 200 € restants au-dessus de la réserve
    assert plan.skipped_buys[0]["reason"] == "trésorerie insuffisante"


@pytest.mark.parametrize("when, warned", [
    (datetime(2026, 9, 29, 15, 38), True),   # mardi en séance
    (datetime(2026, 10, 1, 8, 30), False),   # avant l'ouverture
    (datetime(2026, 10, 3, 15, 0), False),   # samedi
])
def test_market_hours_warning(when, warned):
    assert (market_hours_warning(when) is not None) is warned


def test_main_writes_the_plan_to_the_journal(tmp_path, monkeypatch):
    export = tmp_path / "508TI0EUR-29_09_2026 16_32_37.xlsx"
    write_export(export, [HEADER, ["TotalEnergies SE", "FR0000120271", 78.57, "EUR", 0, 6, 79.18,
                                   -3.66, 0, 471.42, "cash", "XPAR", "EURONEXT PARIS"]])
    monkeypatch.setattr(rebalance, "PROJECT_ROOT", tmp_path)
    journal = rebalance.main(["--cash", "1000", "--downloads", str(tmp_path)],
                             analyze=lambda t, p: signal("NEUTRE", 78.57) if t == "TTE.PA" else None,
                             resolve=lambda isin: "TTE.PA")
    content = journal.read_text(encoding="utf-8")
    assert "TotalEnergies SE : NEUTRE" in content and "aucune vente" in content
    assert journal.name.endswith("_508TI0EUR.md")  # un journal par compte


def test_main_requires_an_explicit_export_when_several_accounts(tmp_path, capsys):
    for name in ["PEA0EUR-02_10_2026 07_00_00.xlsx", "CTO0EUR-02_10_2026 08_10_00.xlsx"]:
        (tmp_path / name).write_bytes(b"")
    with pytest.raises(SystemExit):
        rebalance.main(["--cash", "1000", "--downloads", str(tmp_path)])
    assert rebalance.main(["--list-exports", "--downloads", str(tmp_path)]) is None
    assert capsys.readouterr().out.count("EUR-02_10_2026") == 2
