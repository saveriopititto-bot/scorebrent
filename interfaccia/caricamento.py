"""Download dei dati con la cache di Streamlit: le fonti sono in brent/fonti.py."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from brent.fonti import FonteGpr, FonteMeteo, FontePompa, FonteYahoo


class Caricamento:
    """Ogni metodo scarica una fonte e ne tiene il risultato in cache per il tempo indicato."""

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
