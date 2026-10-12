import numpy as np
import pandas as pd
import pytest

from brent.mercato import Frequenza, Ovx, PrezziBrent, SerieAnalisi
from brent.meteo import AnomaliaStagionale


def test_prezzo_in_euro_e_cambio_riportato():
    d = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])
    brent = pd.DataFrame({"Close": [80.0, 81, 82], "High": [81.0, 82, 83], "Low": [79.0, 80, 81]}, index=d)
    cambio = pd.DataFrame({"Close": [1.1, 1.2]}, index=d[:2])
    t = PrezziBrent.da_quotazioni(brent, cambio).tabella
    assert t["fx"].tolist() == [1.1, 1.2, 1.2]
    np.testing.assert_allclose(t["eur"], [80 / 1.1, 81 / 1.2, 82 / 1.2])


def test_raggruppamento_settimanale(prezzi):
    sett = prezzi.raggruppa(Frequenza.SETTIMANA)
    assert (sett.index.dayofweek == 4).all()  # settimane che finiscono il venerdì
    g = prezzi.tabella.loc["2024-03-04":"2024-03-08"]
    s = sett.loc["2024-03-08"]
    assert s["high"] == g["high"].max() and s["low"] == g["low"].min() and s["eur"] == g["eur"].iloc[-1]
    assert prezzi.raggruppa(Frequenza.GIORNO) is prezzi.tabella


def test_frequenza():
    assert Frequenza("Giorno per giorno") is Frequenza.GIORNO
    assert (Frequenza.GIORNO.periodi_anno, Frequenza.SETTIMANA.periodi_anno) == (252, 52)
    assert (Frequenza.GIORNO.passo, Frequenza.SETTIMANA.passo) == (21, 4)
    assert Frequenza.SETTIMANA.unita == "settimane"


def test_ovx_diviso_per_la_radice_dei_periodi():
    d = pd.bdate_range("2024-01-01", periods=10)
    ovx = pd.Series(40.0, index=d[:3])
    o = Ovx.giornaliero(ovx, d)
    assert np.exp(o[0]) == pytest.approx(0.40 / np.sqrt(252))
    assert np.isfinite(o[:8]).all() and np.isnan(o[8:]).all()  # vale al massimo 5 giorni


def test_serie_analisi(prezzi):
    s = SerieAnalisi.costruisci(prezzi, Frequenza.GIORNO)
    np.testing.assert_allclose(s.x, np.log(prezzi.tabella["eur"]))
    np.testing.assert_allclose(s.y, np.log1p(100 * (prezzi.tabella["high"] / prezzi.tabella["low"] - 1)))
    assert s.esterni == {"meteo": None, "ovx": None, "gpr": None}
    gpr = pd.Series(50.0, index=pd.date_range("2015-01-01", "2027-01-01"))
    g = SerieAnalisi.costruisci(prezzi, Frequenza.SETTIMANA, gprd=gpr).g
    assert np.allclose(g, np.log(50))


def _temperature(anni=6, rumore=0.0):
    d = pd.date_range("2018-01-01", periods=365 * anni + 2)
    t = 10 + 8 * np.sin(2 * np.pi * (d.dayofyear - 110) / 365)
    return pd.Series(t + np.random.default_rng(0).normal(0, rumore, len(d)), index=d)


def test_anomalia_di_una_stagione_perfetta_e_quasi_nulla():
    a = AnomaliaStagionale().calcola(_temperature())
    assert a.abs().max() < 0.3  # resta solo l'effetto della media mobile sulla sinusoide


def test_anomalia_vede_un_giorno_piu_caldo():
    t = _temperature(rumore=0.5)
    t.loc["2021-07-15"] += 6
    a = AnomaliaStagionale().calcola(t)
    assert a.loc["2021-07-15"] > 5
    assert abs(a.mean()) < 0.1


def test_giorno_dell_anno_e_bisestili():
    d = pd.to_datetime(["2024-02-28", "2024-02-29", "2024-03-01", "2023-03-01", "2024-12-31"])
    assert AnomaliaStagionale.giorno_dell_anno(d).tolist() == [59, 59, 60, 60, 365]
    assert AnomaliaStagionale().calcola(pd.Series(dtype=float)).empty
