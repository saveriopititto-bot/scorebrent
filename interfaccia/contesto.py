"""Tutto quello che le schede condividono: impostazioni, dati scaricati e calcoli comuni (serie e score)."""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Any, Callable

import numpy as np
import pandas as pd
import streamlit as st

from brent.fonti import FonteYahoo
from brent.mercato import Ovx, PrezziBrent, SerieAnalisi
from brent.meteo import AnomaliaStagionale
from brent.oscillazione import PrevisioneOscillazione
from brent.score import ScoreRifornimento, StoricoScore

from .caricamento import Caricamento
from .impostazioni import Impostazioni


@dataclass(frozen=True)
class DatoFacoltativo:
    """Un dato esterno che si può disattivare o che può mancare: `valore` è None se disattivato o non scaricato,
    e in quel caso `errore` dice perché (None se disattivato)."""

    attivo: bool
    valore: Any = None
    errore: str | None = None

    @classmethod
    def prova(cls, attivo: bool, carica: Callable[[], Any]) -> DatoFacoltativo:
        if not attivo:
            return cls(False)
        try:
            return cls(True, carica())
        except Exception as e:
            return cls(True, None, str(e))

    @property
    def disponibile(self) -> bool:
        return self.valore is not None


@dataclass(frozen=True)
class Confronto:
    """Ultimo prezzo di chiusura confrontato con quello di `n` giorni prima."""

    t: pd.Timestamp
    data_prima: pd.Timestamp
    ora: pd.Series
    prima: pd.Series

    @property
    def d_usd(self) -> float:
        return self.ora["usd"] / self.prima["usd"] - 1

    @property
    def d_eur(self) -> float:
        return self.ora["eur"] / self.prima["eur"] - 1

    @property
    def d_clip(self) -> float:
        """La variazione in euro tagliata a ±10%."""
        return max(-0.10, min(0.10, self.d_eur))


@dataclass
class Contesto:
    imp: Impostazioni
    prezzi: PrezziBrent
    confronto: Confronto
    meteo: DatoFacoltativo   # temperatura rispetto al normale stagionale (°C)
    ovx: DatoFacoltativo     # chiusure dell'OVX (% annuo)
    pompa: DatoFacoltativo   # prezzi settimanali alla pompa in Italia
    gpr: DatoFacoltativo     # rischio geopolitico giornaliero
    parametri_score: ScoreRifornimento

    @classmethod
    def carica(cls, imp: Impostazioni) -> Contesto:
        """Scarica i dati. Senza prezzi, o se non arrivano abbastanza indietro, mostra l'errore e ferma l'app."""
        try:
            b, f = Caricamento.yahoo(FonteYahoo.BRENT), Caricamento.yahoo(FonteYahoo.EURUSD)
        except Exception as e:
            st.error(f"Non sono riuscito a scaricare i prezzi: {e}")
            st.stop()
        prezzi = PrezziBrent.da_quotazioni(b, f)
        base = prezzi.tabella

        t = base.index[-1]
        tn = t - pd.Timedelta(days=imp.n)
        if tn < base.index[0]:
            st.error("I prezzi scaricati non arrivano così indietro nel tempo.")
            st.stop()
        data_prima = base.index[base.index <= tn][-1]
        confronto = Confronto(t, data_prima, base.loc[t], base.loc[data_prima])

        return cls(
            imp, prezzi, confronto,
            meteo=DatoFacoltativo.prova(imp.usa_meteo, lambda: AnomaliaStagionale().calcola(
                Caricamento.meteo(base.index[0], t))),
            ovx=DatoFacoltativo.prova(imp.usa_ovx, lambda: Caricamento.yahoo(FonteYahoo.OVX)["Close"]),
            pompa=DatoFacoltativo.prova(imp.usa_pompa, Caricamento.pompa),
            gpr=DatoFacoltativo.prova(imp.usa_gpr, Caricamento.gpr),
            parametri_score=ScoreRifornimento(imp.alpha, imp.theta),
        )

    @property
    def base(self) -> pd.DataFrame:
        return self.prezzi.tabella

    @cached_property
    def serie(self) -> SerieAnalisi:
        """Serie raggruppate come scelto in «Raggruppa i prezzi»."""
        gpr = self.gpr.valore
        return SerieAnalisi.costruisci(self.prezzi, self.imp.freq, self.meteo.valore, self.ovx.valore,
                                       None if gpr is None else gpr["GPRD"])

    @cached_property
    def ovx_giornaliero(self) -> np.ndarray | None:
        return Ovx.giornaliero(self.ovx.valore, self.base.index) if self.ovx.disponibile else None

    @cached_property
    def _score(self) -> tuple[StoricoScore | None, str | None]:
        """Score e oscillazione attesa giorno per giorno, usati da «Score rifornimento» e «Prossimi 5 giorni»: è lo
        stesso calcolo che esporta_score.py scrive in Supabase."""
        try:
            return self.parametri_score.storico(self.prezzi, self.ovx_giornaliero), None
        except Exception as e:
            return None, str(e)

    @property
    def score(self) -> StoricoScore | None:
        return self._score[0]

    @property
    def errore_score(self) -> str | None:
        return self._score[1]

    @property
    def sigma_oggi(self) -> float:
        """Oscillazione attesa al giorno (frazione) per i prossimi giorni."""
        return float(self.score.tabella["sigma"].iloc[-1])

    @property
    def modello_score(self) -> str:
        if self.score is not None:
            return self.score.modello
        return PrevisioneOscillazione.modello_predefinito(self.ovx_giornaliero is not None)
