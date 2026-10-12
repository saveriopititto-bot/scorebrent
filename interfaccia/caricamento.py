"""Download dei dati e calcoli lunghi con la cache di Streamlit: le fonti sono in brent/fonti.py."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from brent.fonti import FonteGpr, FonteMeteo, FontePompa, FonteYahoo
from brent.mercato import PrezziBrent
from brent.score import ScoreRifornimento, StoricoScore


class Caricamento:
    """Ogni metodo scarica una fonte, o fa un calcolo lungo, e ne tiene il risultato in cache."""

    @staticmethod
    @st.cache_data(ttl=900, show_spinner="Scarico i prezzi da Yahoo Finance…")
    def yahoo(ticker: str) -> pd.DataFrame:
        return FonteYahoo().scarica(ticker)

    @staticmethod
    @st.cache_data(ttl=6 * 3600, show_spinner="Scarico le temperature da Open-Meteo…")
    def meteo(inizio: pd.Timestamp, fine: pd.Timestamp) -> pd.Series:
        return FonteMeteo().scarica(inizio, fine)

    @staticmethod
    @st.cache_data(ttl=12 * 3600, show_spinner="Scarico il rischio geopolitico (GPR)…")
    def gpr() -> pd.DataFrame:
        return FonteGpr().scarica()

    @staticmethod
    @st.cache_data(ttl=12 * 3600, show_spinner="Scarico i prezzi alla pompa in Italia…")
    def pompa() -> pd.DataFrame:
        return FontePompa().scarica()

    @staticmethod
    @st.cache_data(ttl=900, show_spinner="Calcolo lo score…", max_entries=20,
                   hash_funcs={PrezziBrent: lambda p: pd.util.hash_pandas_object(p.tabella).sum()})
    def storico_score(prezzi: PrezziBrent, ovx: np.ndarray | None, parametri: ScoreRifornimento) -> StoricoScore:
        """Lo score di ogni giorno: si ricalcola solo se cambiano prezzi, OVX, α o θ, non a ogni clic."""
        return parametri.storico(prezzi, ovx)
