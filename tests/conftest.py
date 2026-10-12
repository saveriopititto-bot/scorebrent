"""Dati sintetici deterministici e sostituti della rete (Yahoo Finance, Open-Meteo, GPR, prezzi alla pompa), così i
test girano senza connessione e danno sempre lo stesso risultato."""
from __future__ import annotations

import io

import numpy as np
import pandas as pd
import pytest

INIZIO, FINE = "2016-01-04", "2026-10-09"


def ohlc(seed: int, p0: float, vol0: float, inizio: str = INIZIO, fine: str = FINE) -> pd.DataFrame:
    """Prezzi giornalieri con volatilità a grappoli (GARCH) e code spesse, come quelle di un future sul petrolio."""
    rng = np.random.default_rng(seed)
    d = pd.bdate_range(inizio, fine)
    n = len(d)
    v, r = np.empty(n), np.empty(n)
    v[0] = vol0
    for i in range(n):
        if i:
            v[i] = np.sqrt(0.02 * vol0**2 + 0.9 * v[i - 1] ** 2 + 0.08 * r[i - 1] ** 2)
        r[i] = v[i] * rng.standard_t(5) / np.sqrt(5 / 3)
    c = p0 * np.exp(np.cumsum(r))
    escursione = np.abs(rng.normal(0, 1, n)) * v * 0.8
    return pd.DataFrame({"Open": c, "High": c * np.exp(escursione), "Low": c * np.exp(-escursione), "Close": c,
                         "Volume": 0}, index=d.tz_localize("America/New_York"))


class ReteFinta:
    """Sostituisce yfinance.Ticker, requests.get e pandas.read_excel. `guasti` = fonti che falliscono."""

    def __init__(self):
        self.yahoo = {"BZ=F": ohlc(1, 60, 0.02), "EURUSD=X": ohlc(2, 1.2, 0.005), "^OVX": ohlc(3, 35, 0.04)}
        self.guasti: set[str] = set()

    # --- Yahoo Finance
    def ticker(self, simbolo: str):
        rete = self

        class Ticker:
            def history(self, **_):
                if simbolo in rete.guasti:
                    raise RuntimeError(f"{simbolo} non raggiungibile")
                return rete.yahoo[simbolo].copy()

        return Ticker()

    # --- requests.get
    def get(self, url, timeout=None, params=None, headers=None):
        for nome in ("open-meteo", "fuel-prices", "iacoviello"):
            if nome in url and nome in self.guasti:
                raise RuntimeError(f"{nome} non raggiungibile")
        if "open-meteo" in url:
            return Risposta(js=self.meteo(params))
        if "fuel-prices" in url:
            return Risposta(content=self.pompa_parquet())
        if "iacoviello" in url:
            return Risposta(content=b"xls finto")
        raise AssertionError(f"richiesta inattesa: {url}")

    def meteo(self, params) -> list[dict]:
        if "start_date" in params:
            d = pd.date_range(params["start_date"], params["end_date"])
        else:
            fine = pd.Timestamp(FINE)
            d = pd.date_range(fine - pd.Timedelta(days=params["past_days"]), fine)
        luoghi = []
        for i, _ in enumerate(params["latitude"].split(",")):
            rng = np.random.default_rng(10 + i)
            t = 10 + 9 * np.sin(2 * np.pi * (d.dayofyear - 110) / 365) + rng.normal(0, 3, len(d))
            luoghi.append({"daily": {"time": [f"{x:%Y-%m-%d}" for x in d], "temperature_2m_mean": list(map(float, t))}})
        return luoghi

    def pompa(self) -> pd.DataFrame:
        """Benzina e gasolio che seguono il Brent al litro con 1 e 2 settimane di ritardo."""
        w = pd.date_range(INIZIO, FINE, freq="W-MON")
        brent = self.yahoo["BZ=F"]["Close"].tz_localize(None).reindex(w, method="ffill").bfill().to_numpy() / 1.2 / 159
        rng = np.random.default_rng(5)
        b = pd.Series(brent)
        d = pd.DataFrame({"country_code": "IT", "week": w,
                          "euro95_eur_l": 1.2 + 0.6 * b.shift(1).bfill().to_numpy() + rng.normal(0, .002, len(w)),
                          "diesel_eur_l": 1.1 + 0.7 * b.shift(2).bfill().to_numpy() + rng.normal(0, .002, len(w))})
        return pd.concat([d, d.assign(country_code="FR", euro95_eur_l=9.0)])

    def pompa_parquet(self) -> bytes:
        buf = io.BytesIO()
        self.pompa().to_parquet(buf)
        return buf.getvalue()

    @staticmethod
    def gpr(*_, **__) -> pd.DataFrame:
        d = pd.date_range("2015-01-01", FINE)
        rng = np.random.default_rng(7)
        g = 100 * np.exp(rng.normal(0, .3, len(d)))
        evento = np.where(rng.random(len(d)) < 0.01, "Evento", None)
        return pd.DataFrame({"DAY": d.strftime("%Y%m%d").astype(int), "GPRD": g, "GPRD_ACT": g * .8,
                             "GPRD_THREAT": g * 1.2, "event": evento})


class Risposta:
    def __init__(self, content: bytes = b"", js=None):
        self.content, self._js = content, js
        self.status_code, self.text = 200, ""

    def raise_for_status(self):
        pass

    def json(self):
        return self._js


@pytest.fixture
def rete(monkeypatch) -> ReteFinta:
    """Rete finta per tutto il test: nessuna richiesta esce dal computer."""
    import requests
    import yfinance

    finta = ReteFinta()
    monkeypatch.setattr(yfinance, "Ticker", finta.ticker)
    monkeypatch.setattr(requests, "get", finta.get)
    monkeypatch.setattr(pd, "read_excel", finta.gpr)
    return finta


def prezzi_sintetici():
    """Prezzi del Brent in euro costruiti dai dati sintetici."""
    from brent.mercato import PrezziBrent

    def senza_fuso(d):
        d = d[["High", "Low", "Close"]].copy()
        d.index = d.index.tz_localize(None).normalize()
        return d

    r = ReteFinta()
    return PrezziBrent.da_quotazioni(senza_fuso(r.yahoo["BZ=F"]), senza_fuso(r.yahoo["EURUSD=X"]))


@pytest.fixture(scope="session")
def prezzi():
    return prezzi_sintetici()
