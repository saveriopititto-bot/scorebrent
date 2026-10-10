"""Download e preparazione dei dati di mercato da Yahoo Finance, senza Streamlit.

Li usano sia l'app (app.py, che aggiunge la cache) sia lo script che esporta lo
score in Supabase (esporta_score.py), così i due calcolano lo stesso valore.
"""
import numpy as np
import pandas as pd
import yfinance as yf

BRENT = "BZ=F"        # Brent Crude Oil Futures (USD/barile)
EURUSD = "EURUSD=X"   # dollari per 1 euro
OVX = "^OVX"          # CBOE Crude Oil Volatility Index: volatilità annua attesa a 30 giorni, in %


def scarica_yahoo(ticker: str) -> pd.DataFrame:
    """Storico giornaliero completo (High, Low, Close) di `ticker`, con indice di date senza fuso orario."""
    d = yf.Ticker(ticker).history(period="max", interval="1d")
    if d.empty:
        raise ValueError(f"Yahoo Finance non ha restituito dati per {ticker}")
    d = d[["High", "Low", "Close"]].dropna()
    d = d[(d.Low > 0) & (d.High >= d.Low)]  # scarta le righe con prezzi impossibili
    d.index = d.index.tz_localize(None).normalize()
    return d


def costruisci_base(brent: pd.DataFrame, cambio: pd.DataFrame) -> pd.DataFrame:
    """Prezzi del Brent in dollari (usd, high, low), cambio EUR/USD (fx) e prezzo in euro (eur).
    Solo i giorni in cui il Brent quota; il cambio è riportato sull'ultimo valore disponibile."""
    base = pd.DataFrame(
        {"usd": brent["Close"], "high": brent["High"], "low": brent["Low"],
         "fx": cambio["Close"].reindex(brent.index, method="ffill")}
    ).dropna()
    base["eur"] = base["usd"] / base["fx"]
    return base


def ovx_giornaliero(ovx_close: pd.Series, indice: pd.DatetimeIndex) -> np.ndarray:
    """ln della volatilità attesa al giorno dall'OVX (annua in %), allineata a `indice`; l'ultimo valore
    disponibile vale per al massimo 5 giorni di borsa."""
    return np.log(ovx_close.reindex(indice, method="ffill", limit=5).to_numpy() / 100 / np.sqrt(252))
