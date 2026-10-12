"""Download dei dati esterni, senza Streamlit. Ogni fonte è una classe con un metodo `scarica`; l'app aggiunge la
cache (interfaccia/caricamento.py), lo script di esportazione le usa così come sono."""
from __future__ import annotations

from io import BytesIO

import pandas as pd
import requests
import yfinance as yf


class FonteYahoo:
    """Storico giornaliero da Yahoo Finance."""

    BRENT = "BZ=F"        # Brent Crude Oil Futures (USD/barile)
    EURUSD = "EURUSD=X"   # dollari per 1 euro
    OVX = "^OVX"          # CBOE Crude Oil Volatility Index: volatilità annua attesa a 30 giorni, in %

    def scarica(self, ticker: str) -> pd.DataFrame:
        """Storico giornaliero completo (High, Low, Close) di `ticker`, con indice di date senza fuso orario."""
        d = yf.Ticker(ticker).history(period="max", interval="1d")
        if d.empty:
            raise ValueError(f"Yahoo Finance non ha restituito dati per {ticker}")
        d = d[["High", "Low", "Close"]].dropna()
        d = d[(d.Low > 0) & (d.High >= d.Low)]  # scarta le righe con prezzi impossibili
        d.index = d.index.tz_localize(None).normalize()
        return d


class FonteMeteo:
    """Temperatura media giornaliera di alcune città europee, da Open-Meteo."""

    # Città europee di cui si fa la media della temperatura (latitudine, longitudine).
    CITTA = {
        "Berlino": (52.52, 13.41),
        "Parigi": (48.86, 2.35),
        "Londra": (51.51, -0.13),
        "Milano": (45.46, 9.19),
        "Madrid": (40.42, -3.70),
    }
    STORICO = "https://archive-api.open-meteo.com/v1/archive"
    RECENTE = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, citta: dict[str, tuple[float, float]] | None = None, minimo_citta: int = 3):
        self.citta = self.CITTA if citta is None else citta
        self.minimo_citta = minimo_citta

    def _temperature(self, url: str, **params) -> pd.DataFrame:
        """Temperatura media giornaliera (°C) delle città: una colonna per città."""
        lat, lon = zip(*self.citta.values())
        r = requests.get(url, timeout=30, params={
            "latitude": ",".join(map(str, lat)), "longitude": ",".join(map(str, lon)),
            "daily": "temperature_2m_mean", "timezone": "Europe/Berlin", **params,
        })
        r.raise_for_status()
        js = r.json()
        luoghi = js if isinstance(js, list) else [js]  # con una sola città Open-Meteo restituisce un oggetto
        return pd.DataFrame({
            nome: pd.Series(l["daily"]["temperature_2m_mean"], index=pd.to_datetime(l["daily"]["time"]), dtype=float)
            for nome, l in zip(self.citta, luoghi)
        })

    def scarica(self, inizio: pd.Timestamp, fine: pd.Timestamp) -> pd.Series:
        """Temperatura media delle città giorno per giorno. Lo storico di Open-Meteo arriva con alcuni giorni di
        ritardo: gli ultimi giorni vengono dalle previsioni, che includono il passato recente."""
        fine_storico = max(inizio, fine - pd.Timedelta(days=7))  # oltre, lo storico non è ancora pubblicato
        storico = self._temperature(self.STORICO, start_date=f"{inizio:%Y-%m-%d}", end_date=f"{fine_storico:%Y-%m-%d}")
        recente = self._temperature(self.RECENTE, past_days=31, forecast_days=1)
        t = storico.combine_first(recente).loc[:fine]
        media = t.mean(axis=1).where(t.notna().sum(axis=1) >= self.minimo_citta)
        if media.dropna().empty:
            raise ValueError("Open-Meteo non ha restituito temperature")
        return media.dropna()


class FonteGpr:
    """Geopolitical Risk Index giornaliero (Caldara e Iacoviello): 100 = media 1985-2019."""

    URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls"

    def scarica(self) -> pd.DataFrame:
        """GPR giornaliero (calendario, weekend compresi): GPRD totale, GPRD_ACT (atti), GPRD_THREAT (minacce) ed
        `event`, l'etichetta in inglese degli eventi principali."""
        r = requests.get(self.URL, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        d = pd.read_excel(BytesIO(r.content), sheet_name=0)
        d = d.dropna(subset=["DAY", "GPRD"])
        d.index = pd.to_datetime(d["DAY"].astype(int).astype(str), format="%Y%m%d")
        if d.empty:
            raise ValueError("il file del GPR è vuoto")
        return d[["GPRD", "GPRD_ACT", "GPRD_THREAT", "event"]].sort_index()


class FontePompa:
    """Prezzi medi nazionali alla pompa, settimanali, tasse incluse (Weekly Oil Bulletin della Commissione Europea,
    ripubblicato da fuel-prices.eu, CC BY 4.0)."""

    URL = "https://www.fuel-prices.eu/research/data/d1-eu-weekly-bulletin/fp-d1-eu-weekly-panel.parquet"

    def __init__(self, paese: str = "IT"):
        self.paese = paese

    def scarica(self) -> pd.DataFrame:
        """Prezzi medi settimanali di benzina e gasolio, euro al litro con tasse; indice = lunedì del listino."""
        r = requests.get(self.URL, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        d = pd.read_parquet(BytesIO(r.content))
        d = d[d["country_code"] == self.paese]
        if d.empty:
            raise ValueError("nel file non ci sono prezzi per l'Italia")
        d.index = pd.to_datetime(d["week"])
        return d[["euro95_eur_l", "diesel_eur_l"]].rename(
            columns={"euro95_eur_l": "Benzina", "diesel_eur_l": "Gasolio"}).sort_index().astype(float)
