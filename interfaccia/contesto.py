"""Tutto quello che le schede condividono: impostazioni, dati scaricati e calcoli comuni (serie e score)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from typing import Any

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
    """I dati esterni si scaricano solo quando una scheda li chiede, la prima volta (poi restano in cache)."""

    imp: Impostazioni
    prezzi: PrezziBrent
    confronto: Confronto

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

        return cls(imp, prezzi, Confronto(t, data_prima, base.loc[t], base.loc[data_prima]))

    @property
    def base(self) -> pd.DataFrame:
        return self.prezzi.tabella

    @cached_property
    def meteo(self) -> DatoFacoltativo:
        """Temperatura rispetto al normale stagionale (°C)."""
        return DatoFacoltativo.prova(self.imp.usa_meteo, lambda: AnomaliaStagionale().calcola(
            Caricamento.meteo(self.base.index[0], self.confronto.t)))

    @cached_property
    def ovx(self) -> DatoFacoltativo:
        """Chiusure dell'OVX (% annuo)."""
        return DatoFacoltativo.prova(self.imp.usa_ovx, lambda: Caricamento.yahoo(FonteYahoo.OVX)["Close"])

    @cached_property
    def pompa(self) -> DatoFacoltativo:
        """Prezzi settimanali alla pompa in Italia."""
        return DatoFacoltativo.prova(self.imp.usa_pompa, Caricamento.pompa)

    @cached_property
    def gpr(self) -> DatoFacoltativo:
        """Rischio geopolitico giornaliero."""
        return DatoFacoltativo.prova(self.imp.usa_gpr, Caricamento.gpr)

    @property
    def parametri_score(self) -> ScoreRifornimento:
        return ScoreRifornimento(self.imp.alpha, self.imp.theta)

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
            return Caricamento.storico_score(self.prezzi, self.ovx_giornaliero, self.parametri_score), None
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
