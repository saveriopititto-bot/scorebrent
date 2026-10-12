"""Prezzi del Brent in euro, raggruppamento per giorno o settimana e serie allineate usate dall'analisi."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

from .fonti import FonteYahoo


class Frequenza(Enum):
    """Come si raggruppano i prezzi. Il valore è il testo mostrato nell'app."""

    GIORNO = "Giorno per giorno"
    SETTIMANA = "Settimana per settimana"

    @property
    def unita(self) -> str:
        return "giorni" if self is Frequenza.GIORNO else "settimane"

    @property
    def al_periodo(self) -> str:
        return "al giorno" if self is Frequenza.GIORNO else "alla settimana"

    @property
    def periodi_anno(self) -> int:
        return 252 if self is Frequenza.GIORNO else 52

    @property
    def passo(self) -> int:
        """Ogni quanti periodi si riaddestrano i modelli nelle prove (circa un mese)."""
        return 21 if self is Frequenza.GIORNO else 4


class Ovx:
    """L'OVX è una volatilità annua in %: per confrontarlo con l'oscillazione di un periodo si divide per la
    radice dei periodi in un anno. Le funzioni restituiscono il logaritmo, come gli altri predittori."""

    @staticmethod
    def giornaliero(ovx_close: pd.Series, indice: pd.DatetimeIndex) -> np.ndarray:
        """ln della volatilità attesa al giorno, allineata a `indice`; l'ultimo valore disponibile vale per al
        massimo 5 giorni di borsa."""
        return np.log(ovx_close.reindex(indice, method="ffill", limit=5).to_numpy() / 100 / np.sqrt(252))

    @staticmethod
    def settimanale(ovx_close: pd.Series, giorni: pd.DatetimeIndex, indice: pd.DatetimeIndex) -> np.ndarray:
        """ln della volatilità attesa alla settimana (ultimo valore della settimana), allineata a `indice`."""
        o_bin = ovx_close.reindex(giorni, method="ffill", limit=5).resample("W-FRI").last()
        return np.log(o_bin.reindex(indice).to_numpy() / 100 / np.sqrt(52))


@dataclass(frozen=True)
class PrezziBrent:
    """Prezzi giornalieri del Brent: in dollari (usd, high, low), cambio EUR/USD (fx) e prezzo in euro (eur).
    Solo i giorni in cui il Brent quota; il cambio è riportato sull'ultimo valore disponibile."""

    tabella: pd.DataFrame

    @classmethod
    def da_quotazioni(cls, brent: pd.DataFrame, cambio: pd.DataFrame) -> PrezziBrent:
        base = pd.DataFrame(
            {"usd": brent["Close"], "high": brent["High"], "low": brent["Low"],
             "fx": cambio["Close"].reindex(brent.index, method="ffill")}
        ).dropna()
        base["eur"] = base["usd"] / base["fx"]
        return cls(base)

    @classmethod
    def scarica(cls, fonte: FonteYahoo | None = None) -> PrezziBrent:
        fonte = FonteYahoo() if fonte is None else fonte
        return cls.da_quotazioni(fonte.scarica(FonteYahoo.BRENT), fonte.scarica(FonteYahoo.EURUSD))

    @property
    def date(self) -> pd.DatetimeIndex:
        return self.tabella.index

    def raggruppa(self, freq: Frequenza) -> pd.DataFrame:
        """Prezzi per periodo: giorno per giorno così come sono, oppure settimane che finiscono il venerdì
        (chiusura = ultima, massimo = il più alto, minimo = il più basso)."""
        if freq is Frequenza.GIORNO:
            return self.tabella
        return self.tabella.resample("W-FRI").agg(
            {"usd": "last", "high": "max", "low": "min", "fx": "last", "eur": "last"}
        ).dropna()

    @staticmethod
    def livello(bins: pd.DataFrame) -> np.ndarray:
        """x = ln del prezzo in euro."""
        return np.log(bins["eur"].to_numpy())

    @staticmethod
    def agitazione(bins: pd.DataFrame) -> np.ndarray:
        """y = ln(1 + escursione % fra massimo e minimo)."""
        return np.log1p(100 * (bins["high"] / bins["low"] - 1)).to_numpy()


@dataclass(frozen=True)
class SerieAnalisi:
    """Prezzi raggruppati per periodo e serie allineate: x = ln prezzo in euro, y = agitazione, m = temperatura
    rispetto al normale, o = ln volatilità attesa per periodo dall'OVX, g = ln rischio geopolitico (media degli
    ultimi 7 giorni di calendario, o della settimana). m, o e g sono None se non disponibili."""

    freq: Frequenza
    bins: pd.DataFrame
    x: np.ndarray
    y: np.ndarray
    m: np.ndarray | None = None
    o: np.ndarray | None = None
    g: np.ndarray | None = None

    @classmethod
    def costruisci(cls, prezzi: PrezziBrent, freq: Frequenza, anomalia: pd.Series | None = None,
                   ovx_close: pd.Series | None = None, gprd: pd.Series | None = None) -> SerieAnalisi:
        bins = prezzi.raggruppa(freq)
        m = None
        if anomalia is not None:
            m_bin = anomalia if freq is Frequenza.GIORNO else anomalia.resample("W-FRI").mean()
            m = m_bin.reindex(bins.index).to_numpy()
        o = None
        if ovx_close is not None and freq is Frequenza.GIORNO:
            o = Ovx.giornaliero(ovx_close, bins.index)
        elif ovx_close is not None:
            o = Ovx.settimanale(ovx_close, prezzi.date, bins.index)
        g = None
        if gprd is not None:
            g_bin = (gprd.rolling("7D").mean().reindex(bins.index, method="ffill", limit=10) if freq is Frequenza.GIORNO
                     else gprd.resample("W-FRI").mean().reindex(bins.index))
            g = np.log(g_bin.clip(lower=1).to_numpy())
        return cls(freq, bins, PrezziBrent.livello(bins), PrezziBrent.agitazione(bins), m, o, g)

    @property
    def date(self) -> pd.DatetimeIndex:
        return self.bins.index

    @property
    def esterni(self) -> dict:
        """Predittori esterni facoltativi, come argomenti per i costruttori delle feature."""
        return {"meteo": self.m, "ovx": self.o, "gpr": self.g}
