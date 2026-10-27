"""
Lecture des positions et des espèces depuis la page Bourse Direct (extension, DEC-28).

L'extension envoie le HTML de la page affichée (un texte par cadre) ; tout le décodage est
ici, en Python, pour être testé sur une copie anonymisée de la page.
"""
from dataclasses import dataclass
from typing import List

from rebalance import Holding


@dataclass
class PositionsPage:
    account: str            # n° de compte affiché (sert à nommer le journal)
    cash: float             # espèces disponibles (€)
    holdings: List[Holding]


def parse_positions_page(frames: List[str]) -> PositionsPage:
    # La structure de la page n'est pas encore connue : à écrire à partir d'une copie
    # enregistrée de la page des positions.
    raise NotImplementedError("lecture de la page Bourse Direct pas encore écrite "
                              "(en attente d'une copie HTML de la page des positions)")
