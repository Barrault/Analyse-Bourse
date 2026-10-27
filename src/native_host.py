"""
Hôte « Native Messaging » de l'extension Opera (DEC-28).

Lancé par le navigateur à chaque demande de l'extension (jamais à la main) : lit un message
JSON sur l'entrée standard, répond sur la sortie standard, puis s'arrête. Aucun port réseau.
Installation : python src/install_native_host.py --extension-id <identifiant>.

Messages reçus :
    {"type": "ping"}                     → {"ok": true}
    {"type": "plan", "frames": [html…]}  → {"ok": true, "account", "account_type", "warning", "plan", "journal"}
En cas d'erreur : {"ok": false, "error": "..."} (détail dans logs_results/native_host.log).
"""
import json
import logging
import struct
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Callable, Optional

from bourse_direct_page import parse_positions_page
from cac40_analyzer import analyze_ticker
from rebalance import (DEFAULT_PERIOD, PARIS, PROJECT_ROOT, build_plan, load_analyses, market_hours_warning,
                       render, write_journal)

log = logging.getLogger("native_host")


# ----------------------- Protocole ----------------------- #
# Chaque message : longueur sur 4 octets (ordre natif), puis le JSON en UTF-8.

def read_message(stream: BinaryIO) -> Optional[dict]:
    header = stream.read(4)
    if len(header) < 4:
        return None  # le navigateur a fermé l'entrée : fin
    (length,) = struct.unpack("=I", header)
    return json.loads(stream.read(length).decode("utf-8"))


def write_message(stream: BinaryIO, message: dict) -> None:
    data = json.dumps(message, ensure_ascii=False).encode("utf-8")
    stream.write(struct.pack("=I", len(data)))
    stream.write(data)
    stream.flush()


# ----------------------- Traitement ----------------------- #

def handle(message: dict, now: datetime, analyze: Callable = analyze_ticker, root: Path = PROJECT_ROOT) -> dict:
    """Même chaîne que `rebalance.py --cash … --export …`, positions lues sur la page."""
    kind = message.get("type")
    if kind == "ping":
        return {"ok": True}
    if kind != "plan":
        raise ValueError(f"type de message inconnu : {kind!r}")
    page = parse_positions_page(message["frames"])
    analyses = load_analyses(DEFAULT_PERIOD, now, analyze, root / "results")
    # Tickers lus sur la page (mnémonique Euronext Paris) : pas de recherche par ISIN
    plan = build_plan(page.holdings, {}, analyses, page.cash)
    source = f"page Bourse Direct, {page.account_type} {page.account}"
    journal = write_journal(render(plan, source, now), page.account, now, root)
    log.info("plan calculé : %d ventes, %d achats", len(plan.sells), len(plan.buys))  # jamais les positions
    return {"ok": True, "account": page.account, "account_type": page.account_type, "warning": market_hours_warning(now),
            "plan": asdict(plan), "journal": str(journal)}


def main() -> None:
    out = sys.stdout.buffer
    # Tout affichage parasite (yfinance…) corromprait le protocole : sorties vers le log
    log_path = PROJECT_ROOT / "logs_results" / "native_host.log"
    log_path.parent.mkdir(exist_ok=True)
    sys.stdout = sys.stderr = open(log_path, "a", encoding="utf-8")
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    while (message := read_message(sys.stdin.buffer)) is not None:
        try:
            response = handle(message, datetime.now(PARIS))
        except Exception as error:
            log.exception("échec du message %r", message.get("type"))
            response = {"ok": False, "error": f"{type(error).__name__} : {error}"}
        write_message(out, response)


if __name__ == "__main__":
    main()
