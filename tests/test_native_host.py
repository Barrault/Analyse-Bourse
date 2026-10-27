"""Tests de l'hôte Native Messaging de l'extension et de son installateur (DEC-28), sans réseau."""
import io
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import native_host
from bourse_direct_page import PositionsPage
from install_native_host import HOST_NAME, host_files
from rebalance import Holding, load_analyses
from test_rebalance import signal

ROOT = Path(__file__).resolve().parent.parent
AFTER_CLOSE = datetime(2026, 10, 1, 18, 0)  # jeudi après la clôture
IN_SESSION = datetime(2026, 10, 1, 15, 0)


def test_messages_roundtrip_with_length_prefix():
    stream = io.BytesIO()
    native_host.write_message(stream, {"type": "plan", "frames": ["<p>é</p>"]})
    stream.seek(0)
    assert native_host.read_message(stream) == {"type": "plan", "frames": ["<p>é</p>"]}
    assert native_host.read_message(stream) is None  # entrée fermée : fin de l'hôte


def test_ping_and_unknown_message():
    assert native_host.handle({"type": "ping"}, AFTER_CLOSE) == {"ok": True}
    with pytest.raises(ValueError):
        native_host.handle({"type": "ordre"}, AFTER_CLOSE)


def test_plan_from_the_page_follows_the_tested_rules(tmp_path, monkeypatch):
    page = PositionsPage("508TI0EUR", "PEA", 1500.0, [Holding("BNP", "", 100.0, 4, 100.0, ticker="BNP.PA")])
    monkeypatch.setattr(native_host, "parse_positions_page", lambda frames: page)
    analyses = {"BNP.PA": signal("VENTE", 100.0), "SAN.PA": signal("ACHAT", 90.0)}
    response = native_host.handle({"type": "plan", "frames": ["<html>"]}, AFTER_CLOSE,
                                  analyze=lambda t, p: analyses.get(t), root=tmp_path)
    assert response["ok"] and response["warning"] is None and response["account_type"] == "PEA"
    assert [s["name"] for s in response["plan"]["sells"]] == ["BNP"]
    assert [b["ticker"] for b in response["plan"]["buys"]] == ["SAN.PA"]
    assert Path(response["journal"]).name == "2026-10-01_508TI0EUR.md"
    json.dumps(response)  # sérialisable tel quel vers l'extension


def test_signals_are_cached_for_the_period_and_briefly_in_session(tmp_path):
    calls = []

    def analyze(ticker, period):
        calls.append(ticker)
        return signal("ACHAT", 10.0) if ticker == "AC.PA" else None

    first = load_analyses("2y", AFTER_CLOSE, analyze, tmp_path)
    n = len(calls)
    later = AFTER_CLOSE + timedelta(hours=4)  # même période (après la clôture) : pas de recalcul
    assert load_analyses("2y", later, analyze, tmp_path) == first and len(calls) == n

    # En séance : un fichier à part (bougie incomplète), réutilisé 15 min seulement (DEC-31)
    load_analyses("2y", IN_SESSION, analyze, tmp_path)
    assert len(calls) == 2 * n
    load_analyses("2y", IN_SESSION + timedelta(minutes=14), analyze, tmp_path)
    assert len(calls) == 2 * n
    load_analyses("2y", IN_SESSION + timedelta(minutes=16), analyze, tmp_path)
    assert len(calls) == 3 * n


def test_installer_allows_only_the_given_extension(tmp_path):
    files = host_files(Path("C:/venv/python.exe"), "a" * 32, root=tmp_path)
    manifest = json.loads(next(c for p, c in files.items() if p.suffix == ".json"))
    assert manifest["name"] == HOST_NAME and manifest["allowed_origins"] == [f"chrome-extension://{'a' * 32}/"]
    launcher = next(c for p, c in files.items() if p.suffix == ".bat")
    assert '"C:' in launcher and "native_host.py" in launcher
    with pytest.raises(ValueError):
        host_files(Path("python.exe"), "pas-un-identifiant", root=tmp_path)


def test_extension_matches_the_project():
    manifest = json.loads((ROOT / "extension" / "manifest.json").read_text(encoding="utf-8"))
    version = re.search(r'^version = "(.+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)
    assert manifest["version"] == version  # extension et projet versionnés ensemble
    assert HOST_NAME in (ROOT / "extension" / "background.js").read_text(encoding="utf-8")
    assert re.fullmatch(r"https://\*\.boursedirect\.fr/\*", manifest["host_permissions"][0])
