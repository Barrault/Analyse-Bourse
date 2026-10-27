"""
Lecture des positions et des espèces depuis la page Bourse Direct (extension, DEC-28).

L'extension envoie le HTML de la page affichée (un texte par cadre) ; tout le décodage est
ici, en Python, pour être testé sur une copie anonymisée de la page.

La page « Mes portefeuilles » est une application React : les noms de classes CSS changent
à chaque déploiement, on ne s'appuie que sur les attributs `data-testid` / `data-prt-column`,
la classe `position-row` et les liens d'instrument `/api/instrument/redirect/<MIC>/<mnémo>/<devise>`
(absents pour un titre sans fiche : la ligne passe alors en décision manuelle).
"""
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import List, Optional

from rebalance import Holding

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
SKIPPED_TAGS = {"script", "style", "svg"}
INSTRUMENT_LINK = re.compile(r"/api/instrument/redirect/([A-Z0-9]+)/([^/]+)/([A-Z]{3})")
ASSET_COUNT = re.compile(r"(\d+)\s*actif")
# Marché (MIC) → suffixe Yahoo ; ArcelorMittal est dans l'univers sous MT.AS (Amsterdam)
YAHOO_SUFFIX = {"XPAR": ".PA", "ALXP": ".PA", "XAMS": ".AS"}


@dataclass
class PositionsPage:
    account: str            # n° de compte affiché (sert à nommer le journal)
    account_type: str       # « PEA », « CTO »… tel qu'affiché
    cash: float             # disponible au comptant (€)
    holdings: List[Holding]


# ----------------------- Arbre HTML minimal ----------------------- #

@dataclass
class Node:
    tag: str
    attrs: dict
    children: list = field(default_factory=list)  # Node ou str

    def classes(self) -> List[str]:
        return (self.attrs.get("class") or "").split()

    def iter(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.iter()

    def find_all(self, predicate) -> List["Node"]:
        return [node for node in self.iter() if predicate(node)]

    def find(self, predicate) -> Optional["Node"]:
        return next((node for node in self.iter() if predicate(node)), None)

    def text(self) -> str:
        """Texte visible, sans les repères de développement (`<span class="dev">[a]</span>`)."""
        if "dev" in self.classes():
            return ""
        return "".join(c if isinstance(c, str) else c.text() for c in self.children)


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#document", {})
        self.stack = [self.root]
        self.skipping = 0

    def handle_starttag(self, tag, attrs):
        if self.skipping or tag in SKIPPED_TAGS:
            self.skipping += tag in SKIPPED_TAGS
            return
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        if not self.skipping and tag not in SKIPPED_TAGS:
            self.stack[-1].children.append(Node(tag, dict(attrs)))

    def handle_endtag(self, tag):
        if tag in SKIPPED_TAGS:
            self.skipping = max(0, self.skipping - 1)
            return
        if self.skipping:
            return
        # Ferme jusqu'à la balise correspondante ; une fermeture orpheline est ignorée
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if not self.skipping:
            self.stack[-1].children.append(data)


def parse_html(html: str) -> Node:
    builder = TreeBuilder()
    builder.feed(html)
    builder.close()
    return builder.root


# ----------------------- Décodage ----------------------- #

def parse_number(text: str) -> float:
    """« 3 920.79 € », « 107.775 € », « 86.40 », « -19,83 % » → nombre."""
    cleaned = re.sub(r"[\s  €%]", "", text)
    if "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".")
    return float(cleaned)


def by_testid(value: str):
    return lambda node: node.attrs.get("data-testid") == value


def by_column(value: str):
    return lambda node: node.attrs.get("data-prt-column") == value


def parse_row(row: Node) -> Holding:
    # Lien absent (href="#") pour un titre sans fiche Bourse Direct, ex. Canal+ coté à Londres
    link = row.find(lambda n: n.tag == "a" and INSTRUMENT_LINK.search(n.attrs.get("href") or ""))
    mic, symbol, currency = INSTRUMENT_LINK.search(link.attrs["href"]).groups() if link else (None, None, None)
    name_node = row.find(lambda n: any(c.startswith("PositionInstrument-module_name_") for c in n.classes()))
    name = (name_node.text() if name_node else symbol or "").strip()
    if not name:
        raise ValueError("ligne de position sans nom ni lien d'instrument")

    def value(predicate, label: str) -> float:
        node = row.find(predicate)
        if node is None:
            raise ValueError(f"{name} : {label} introuvable")
        return parse_number(re.sub(r"[A-Za-z:]", "", node.text()))  # « PRU : », devise

    # Mnémonique + suffixe du marché = ticker Yahoo ; titre non identifié : décision manuelle
    ticker = f"{symbol}{YAHOO_SUFFIX[mic]}" if mic in YAHOO_SUFFIX and currency == "EUR" else None
    return Holding(name=name, isin="", price=value(by_column("last"), "cours"),
                   quantity=int(value(by_testid("consolidated-quantity"), "quantité")),
                   pru=value(by_testid("consolidated-pru"), "PRU"), ticker=ticker)


def displayed_account(root: Node, n_rows: int):
    """Le sélecteur de comptes ne marque pas la carte affichée : on retient la carte dont le
    nombre d'actifs égale le nombre de lignes affichées, et on refuse en cas de doute."""
    cards = root.find_all(lambda n: re.fullmatch(r"card-\d+", n.attrs.get("data-testid") or "") is not None)
    matching = []
    for card in cards:
        count = ASSET_COUNT.search(card.text())
        if count and int(count.group(1)) == n_rows:
            index = card.attrs["data-testid"].split("-")[1]
            kind = card.find(by_testid(f"card-type-{index}"))
            matching.append((card.attrs.get("data-id") or "", kind.text().strip() if kind else ""))
    if len(matching) != 1:
        raise ValueError(f"compte affiché non identifiable ({len(matching)} compte(s) avec {n_rows} actifs) : "
                         "attendre la fin du chargement de la page, ou passer par l'export xlsx")
    return matching[0]


def parse_positions_page(frames: List[str]) -> PositionsPage:
    for html in frames:
        root = parse_html(html)
        cash_node = root.find(by_testid("portfolio-header_available-cash-value"))
        if cash_node is None:
            continue
        rows = root.find_all(lambda n: "position-row" in n.classes())
        account, account_type = displayed_account(root, len(rows))
        return PositionsPage(account=account, account_type=account_type, cash=parse_number(cash_node.text()),
                             holdings=[parse_row(row) for row in rows])
    raise ValueError("page des positions introuvable : ouvrir « Mes portefeuilles » sur Bourse Direct")
