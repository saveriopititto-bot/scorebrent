"""Analisi differenziale (variazioni fra periodi e loro riepiloghi) e area di Lévy del cammino (prezzo, agitazione).

Convenzione di segno dell'area di Lévy (eq. 6 del paper), con cammino (x, y) = (prezzo, attivita'): A > 0 se il
cammino ruota in senso antiorario, cioe' se il PREZZO ANTICIPA l'attivita'; A < 0 se e' l'attivita' ad anticipare
il prezzo.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Riepilogo:
    """Statistiche sulle altezze: le non lineari sono sensibili al percorso, `net` e' telescopica (eq. 4) e vale
    y_K - y_0."""

    net: float
    variazione_totale: float
    parte_positiva: float
    parte_negativa: float
    rms: float
    salto_max: float
    salto_min: float

    @classmethod
    def da_altezze(cls, h) -> Riepilogo:
        h = np.asarray(h, float)
        if h.size == 0:
            return cls(*(np.nan,) * 7)
        return cls(
            net=float(h.sum()),
            variazione_totale=float(np.abs(h).sum()),
            parte_positiva=float(h[h > 0].sum()),
            parte_negativa=float(h[h < 0].sum()),
            rms=float(np.sqrt(np.mean(h**2))),
            salto_max=float(h.max()),
            salto_min=float(h.min()),
        )

    @property
    def efficienza(self) -> float:
        """|net| / variazione totale, in [0, 1]. 1 = percorso rettilineo, vicino a 0 = molto movimento ma poca
        strada netta."""
        tv = self.variazione_totale
        return float(abs(self.net) / tv) if tv and tv > 0 else float("nan")


class Percorso:
    """Una serie di livelli (es. ln prezzo) e le sue altezze differenziali, moltiplicate per `scala`
    (100 = in punti percentuali)."""

    def __init__(self, livello, scala: float = 1.0):
        self.livello = np.asarray(livello, float)
        self.scala = scala

    @property
    def altezze(self) -> np.ndarray:
        """h_k = y_k - y_{k-1} (eq. 3)."""
        return self.scala * np.diff(self.livello)

    def riepilogo(self) -> Riepilogo:
        return Riepilogo.da_altezze(self.altezze)


class CamminoPiano:
    """Cammino poligonale nel piano (x, y)."""

    def __init__(self, x, y):
        self.x, self.y = np.asarray(x, float), np.asarray(y, float)

    def __len__(self) -> int:
        return len(self.x)

    def finestra(self, t: int, w: int) -> CamminoPiano:
        """I w+1 punti che finiscono in t (w incrementi)."""
        return CamminoPiano(self.x[t - w : t + 1], self.y[t - w : t + 1])

    @property
    def incrementi(self) -> tuple[np.ndarray, np.ndarray]:
        return np.diff(self.x), np.diff(self.y)

    def area_levy(self) -> float:
        """A = 1/2 * sum_k [(x_{k-1} - x_0) dy_k - (y_{k-1} - y_0) dx_k]  (eq. 6).

        Esatta per un cammino poligonale. Invariante per traslazione, cambia segno scambiando i canali, nulla se un
        canale e' funzione affine dell'altro."""
        x, y = self.x, self.y
        if x.size < 2:
            return 0.0
        dx, dy = np.diff(x), np.diff(y)
        return 0.5 * float(np.sum((x[:-1] - x[0]) * dy - (y[:-1] - y[0]) * dx))

    def area_levy_mobile(self, w: int) -> np.ndarray:
        """Area di Lévy su finestra scorrevole di w bin, normalizzata come il coefficiente di Pearson:
        A / (w * sd(dx) * sd(dy)). NaN dove non definita."""
        out = np.full(len(self), np.nan)
        for t in range(w, len(self)):
            f = self.finestra(t, w)
            dx, dy = f.incrementi
            sx, sy = dx.std(ddof=1), dy.std(ddof=1)
            if sx > 0 and sy > 0:
                out[t] = f.area_levy() / (w * sx * sy)
        return out
