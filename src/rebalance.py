"""
Plan d'ordres mensuel à partir de l'export de positions Bourse Direct (cf. DEC-25).

    python src/rebalance.py --list-exports              # exports retenus dans ~/Downloads
    python src/rebalance.py --cash 1500                 # export le plus récent de ~/Downloads
    python src/rebalance.py --cash 1500 --export CHEMIN.xlsx

Applique les règles de la stratégie testée : vente sur signal VENTE ou stop-loss, achats
ACHAT par probabilité puis score technique, montant fixe, actions entières, frais Bourse
Direct, réserve de trésorerie. Écrit le plan dans journal/AAAA-MM-JJ.md (suivi réel).
"""
import argparse
import math
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from backtest import calculate_fees
from cac40_analyzer import NOMS_ENTREPRISES, analyze_ticker, order_amount
from config_loader import config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Nom d'export Bourse Direct : <n° de compte>EUR-JJ_MM_AAAA HH_MM_SS.xlsx
EXPORT_NAME = re.compile(r"^(\w+EUR)-(\d{2}_\d{2}_\d{4} \d{2}_\d{2}_\d{2})\.xlsx$")
PARIS = ZoneInfo("Europe/Paris")


@dataclass
class Holding:
    name: str
    isin: str
    price: float      # dernier cours de l'export
    quantity: int
    pru: float        # prix de revient unitaire (frais inclus, selon le courtier)


@dataclass
class Plan:
    sells: List[dict] = field(default_factory=list)
    keeps: List[dict] = field(default_factory=list)
    manual: List[dict] = field(default_factory=list)
    buys: List[dict] = field(default_factory=list)
    skipped_buys: List[dict] = field(default_factory=list)
    cash_start: float = 0.0
    cash_after_sells: float = 0.0
    cash_end: float = 0.0


# ----------------------- Export de positions ----------------------- #

def find_latest_exports(directory: Path) -> List[Path]:
    """Exports à traiter dans `directory` : la date (jour) la plus récente parmi tous les
    exports, puis, pour chaque compte ayant un export ce jour-là, son export le plus récent.
    Un compte sans export à cette date est ignoré : on ne mélange jamais deux dates."""
    candidates = []
    for path in directory.glob("*EUR-*.xlsx"):
        match = EXPORT_NAME.match(path.name)
        if match:
            candidates.append((match.group(1), datetime.strptime(match.group(2), "%d_%m_%Y %H_%M_%S"), path))
    if not candidates:
        raise FileNotFoundError(f"Aucun export de positions (…EUR-JJ_MM_AAAA HH_MM_SS.xlsx) dans {directory}")
    day = max(when.date() for _, when, _ in candidates)
    latest: Dict[str, Tuple[datetime, Path]] = {}
    for account, when, path in candidates:
        if when.date() == day and (account not in latest or when > latest[account][0]):
            latest[account] = (when, path)
    return [latest[account][1] for account in sorted(latest)]


def account_of(export: Path) -> str:
    """N° de compte en tête du nom d'export (nom du fichier à défaut)."""
    match = EXPORT_NAME.match(export.name)
    return match.group(1) if match else export.stem


def read_positions(path: Path) -> List[Holding]:
    """Lit l'export Bourse Direct. Le fichier est au format « Strict OOXML », que openpyxl
    ne lit pas : on lit directement le XML de la feuille (bibliothèque standard)."""
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    ns = root.tag.split("}")[0].strip("{")

    def cell_value(cell) -> str:
        inline = cell.find(f"{{{ns}}}is")
        if inline is not None:
            return "".join(inline.itertext()).strip()
        value = cell.find(f"{{{ns}}}v")
        return value.text.strip() if value is not None and value.text else ""

    rows = [[cell_value(c) for c in row] for row in root.iter(f"{{{ns}}}row")]
    header = [h.lower() for h in rows[0]]

    def column(prefix: str) -> int:
        return next(i for i, h in enumerate(header) if h.startswith(prefix))

    idx = {key: column(prefix) for key, prefix in
           (("name", "nom"), ("isin", "isin"), ("price", "cours"), ("quantity", "quantit"), ("pru", "pru"))}
    holdings = []
    for row in rows[1:]:
        if len(row) <= max(idx.values()) or not row[idx["isin"]]:
            continue
        holdings.append(Holding(name=row[idx["name"]], isin=row[idx["isin"]], price=float(row[idx["price"]]),
                                quantity=int(float(row[idx["quantity"]])), pru=float(row[idx["pru"]])))
    return holdings


def resolve_ticker(isin: str) -> Optional[str]:
    """Ticker Yahoo d'un ISIN, en privilégiant la cotation de Paris (.PA)."""
    import yfinance as yf
    try:
        symbols = [q.get("symbol", "") for q in yf.Search(isin, max_results=5).quotes]
    except Exception:
        return None
    return next((s for s in symbols if s.endswith(".PA")), symbols[0] if symbols else None)


# ----------------------- Plan d'ordres ----------------------- #

def build_plan(holdings: List[Holding], tickers: Dict[str, Optional[str]],
               analyses: Dict[str, Tuple[dict, object]], cash: float) -> Plan:
    """Applique les règles de la stratégie backtestée aux positions réelles."""
    stop_loss_pct = config.get('trading.exit_rules.stop_loss_pct')
    margin_buffer = config.get('trading.margin_buffer')
    min_order = config.get('trading.min_order_amount')
    plan = Plan(cash_start=cash)
    held_tickers = set()
    available = cash

    for h in holdings:
        ticker = tickers.get(h.isin)
        line = {"name": h.name, "ticker": ticker, "quantity": h.quantity, "price": h.price, "pru": h.pru,
                "pnl_pct": (h.price / h.pru - 1) * 100 if h.pru else 0.0}
        if ticker:
            held_tickers.add(ticker)
        if ticker not in NOMS_ENTREPRISES or ticker not in analyses:
            line["reason"] = ("hors univers de la stratégie" if ticker not in NOMS_ENTREPRISES
                              else "pas de signal (données insuffisantes)")
            plan.manual.append(line)
            continue
        outcome, _ = analyses[ticker]
        line.update(recommendation=outcome["recommendation"], technical_score=outcome["technical_score"])
        stop_hit = stop_loss_pct is not None and h.price <= h.pru * (1 - stop_loss_pct / 100)
        if outcome["recommendation"] == "VENTE" or stop_hit:
            gross = h.quantity * h.price
            line.update(reason="signal VENTE" if outcome["recommendation"] == "VENTE" else f"stop-loss (≤ −{stop_loss_pct} %)",
                        proceeds=gross - calculate_fees(gross))
            available += line["proceeds"]
            plan.sells.append(line)
        else:
            plan.keeps.append(line)
    plan.cash_after_sells = available

    candidates = sorted(
        ((t, o, s) for t, (o, s) in analyses.items() if o["recommendation"] == "ACHAT" and t not in held_tickers),
        key=lambda x: (x[1]["confidence"], x[1]["technical_score"]), reverse=True)
    for ticker, outcome, snap in candidates:
        line = {"name": NOMS_ENTREPRISES.get(ticker, ticker), "ticker": ticker, "price": snap.close,
                "confidence": outcome["confidence"], "technical_score": outcome["technical_score"]}
        budget = min(order_amount(), available - margin_buffer)
        if budget < min_order:
            plan.skipped_buys.append({**line, "reason": "trésorerie insuffisante"})
            continue
        quantity = math.floor((budget - calculate_fees(budget)) / snap.close)
        if quantity < 1:
            plan.skipped_buys.append({**line, "reason": f"1 action ({snap.close:.2f} €) dépasse le budget"})
            continue
        gross = quantity * snap.close
        line.update(quantity=quantity, cost=gross + calculate_fees(gross))
        available -= line["cost"]
        plan.buys.append(line)
    plan.cash_end = available
    return plan


# ----------------------- Rendu ----------------------- #

def market_hours_warning(now: datetime) -> Optional[str]:
    """La stratégie décide sur la clôture de la veille : en séance, la bougie du jour est incomplète."""
    if now.weekday() < 5 and (9, 0) <= (now.hour, now.minute) < (17, 40):
        return ("⚠️ Marché ouvert : les cours incluent la séance en cours, incomplète. "
                "Relancer avant 9 h ou après 17 h 40 pour appliquer la stratégie testée.")
    return None


def render(plan: Plan, export: Path, now: datetime) -> str:
    out = [f"# Plan de rebalance — {now:%d/%m/%Y %H:%M}", "",
           f"Export : `{export.name}` · Cash déclaré : {plan.cash_start:,.2f} €", ""]
    warning = market_hours_warning(now)
    if warning:
        out += [warning, ""]

    out += ["## 1. Ventes (à passer en premier)", ""]
    out += ["| Titre | Qté | Cours | PRU | +/- | Motif | Produit estimé |", "|---|---:|---:|---:|---:|---|---:|"]
    out += [f"| {s['name']} | {s['quantity']} | {s['price']:.2f} € | {s['pru']:.2f} € | {s['pnl_pct']:+.1f} % | "
            f"{s['reason']} | {s['proceeds']:,.2f} € |" for s in plan.sells] or ["| — | | | | | aucune vente | |"]

    out += ["", "## 2. Achats (par ordre de priorité)", ""]
    out += ["| # | Titre | Qté | Cours | Montant frais inclus | Confiance | Score tech. |", "|---:|---|---:|---:|---:|---:|---:|"]
    out += [f"| {i} | {b['name']} ({b['ticker']}) | {b['quantity']} | {b['price']:.2f} € | {b['cost']:,.2f} € | "
            f"{b['confidence']:.1%} | {b['technical_score']:+.1f} |" for i, b in enumerate(plan.buys, 1)] \
        or ["| | aucun achat | | | | | |"]
    if plan.skipped_buys:
        out += ["", "ACHAT non servis : " + ", ".join(f"{b['name']} ({b['reason']})" for b in plan.skipped_buys)]

    out += ["", "## 3. Positions conservées", ""]
    out += [f"- {k['name']} : {k['recommendation']}, {k['pnl_pct']:+.1f} % vs PRU" for k in plan.keeps] or ["- aucune"]
    if plan.manual:
        out += ["", "## 4. Hors stratégie (décision manuelle)", ""]
        out += [f"- {m['name']} ({m['ticker'] or 'ticker introuvable'}) : {m['reason']}, "
                f"{m['pnl_pct']:+.1f} % vs PRU" for m in plan.manual]

    out += ["", "## Trésorerie", "",
            f"- Départ : {plan.cash_start:,.2f} € → après ventes : {plan.cash_after_sells:,.2f} € "
            f"→ après achats : {plan.cash_end:,.2f} € (réserve {config.get('trading.margin_buffer')} €)",
            "- Montants estimés sur le dernier cours : l'exécution se fera au cours d'ouverture."]
    return "\n".join(out) + "\n"


def main(argv: Optional[List[str]] = None, analyze: Callable = analyze_ticker,
         resolve: Callable = resolve_ticker) -> Optional[Path]:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cash", type=float, help="Espèces disponibles sur le compte (€)")
    parser.add_argument("--export", type=Path, help="Export de positions (défaut : le plus récent de ~/Downloads, "
                                                    "s'il est le seul à sa date)")
    parser.add_argument("--list-exports", action="store_true", help="Affiche les exports retenus et s'arrête")
    parser.add_argument("--downloads", type=Path, default=Path.home() / "Downloads")
    parser.add_argument("--period", default="2y")
    args = parser.parse_args(argv)

    if args.list_exports:
        for path in find_latest_exports(args.downloads):
            print(path)
        return None
    if args.cash is None:
        parser.error("--cash est obligatoire")
    export = args.export
    if export is None:
        exports = find_latest_exports(args.downloads)
        if len(exports) > 1:
            parser.error("plusieurs comptes ont un export à la même date ; en choisir un avec --export :\n"
                         + "\n".join(str(p) for p in exports))
        export = exports[0]
    holdings = read_positions(export)
    tickers = {h.isin: resolve(h.isin) for h in holdings}
    analyses = {}
    for ticker in NOMS_ENTREPRISES:
        result = analyze(ticker, args.period)
        if result is not None:
            analyses[ticker] = result

    now = datetime.now(PARIS)
    report = render(build_plan(holdings, tickers, analyses, args.cash), export, now)
    journal = PROJECT_ROOT / "journal" / f"{now:%Y-%m-%d}_{account_of(export)}.md"
    journal.parent.mkdir(exist_ok=True)
    journal.write_text(report, encoding="utf-8")
    print(report)
    print(f"Plan enregistré dans {journal}")
    return journal


if __name__ == "__main__":
    main()
