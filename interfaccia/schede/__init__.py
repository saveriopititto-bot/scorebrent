"""Le schede dell'app, raggruppate nelle sezioni del menù."""
from __future__ import annotations

from dataclasses import dataclass

from .andamento import SchedaAndamento
from .base import Scheda
from .formule import SchedaFormule
from .geopolitica import SchedaGeopolitica
from .meteo import SchedaMeteo
from .oscillazione import SchedaOscillazione
from .pompa import SchedaPompa
from .prezzo import SchedaPrezzo
from .prossimi import SchedaProssimi
from .prova import SchedaProva
from .score import SchedaScore


@dataclass(frozen=True)
class Sezione:
    """Un bottone del menù: le sue schede compaiono sotto, nell'ordine dato."""

    nome: str  # anche il valore nell'indirizzo, es. ?sezione=Mercato
    schede: tuple[type[Scheda], ...]


SEZIONI: tuple[Sezione, ...] = (
    Sezione("Rifornimento", (SchedaScore, SchedaProssimi, SchedaPompa)),
    Sezione("Mercato", (SchedaPrezzo, SchedaAndamento, SchedaMeteo, SchedaGeopolitica)),
    Sezione("Modelli", (SchedaProva, SchedaOscillazione, SchedaFormule)),
)
SCHEDE: tuple[type[Scheda], ...] = tuple(s for sezione in SEZIONI for s in sezione.schede)

__all__ = ["SCHEDE", "SEZIONI", "Scheda", "Sezione", *(s.__name__ for s in SCHEDE)]
