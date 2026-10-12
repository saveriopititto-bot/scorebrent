"""Le schede dell'app, nell'ordine della barra delle schede."""
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

SCHEDE: tuple[type[Scheda], ...] = (
    SchedaPrezzo, SchedaScore, SchedaProssimi, SchedaPompa, SchedaAndamento, SchedaMeteo, SchedaGeopolitica,
    SchedaProva, SchedaOscillazione, SchedaFormule,
)

__all__ = ["SCHEDE", "Scheda", *(s.__name__ for s in SCHEDE)]
