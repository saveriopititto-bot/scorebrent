import numpy as np
import pandas as pd
import pytest

from brent.fonti import FonteGpr, FonteMeteo, FontePompa, FonteYahoo
from brent.mercato import PrezziBrent

from .conftest import FINE


def test_yahoo_toglie_fuso_e_righe_impossibili(rete):
    d = rete.yahoo["BZ=F"]
    d.iloc[3, d.columns.get_loc("Low")] = -1                          # prezzo negativo
    d.iloc[5, d.columns.get_loc("High")] = d.iloc[5]["Low"] / 2       # massimo sotto il minimo
    out = FonteYahoo().scarica(FonteYahoo.BRENT)
    assert out.index.tz is None and list(out.columns) == ["High", "Low", "Close"]
    assert len(out) == len(d) - 2 and (out.Low > 0).all() and (out.High >= out.Low).all()


def test_yahoo_vuoto_è_un_errore(rete):
    rete.yahoo["BZ=F"] = rete.yahoo["BZ=F"].iloc[:0]
    with pytest.raises(ValueError, match="BZ=F"):
        FonteYahoo().scarica(FonteYahoo.BRENT)


def test_prezzi_brent_scaricati(rete):
    p = PrezziBrent.scarica()
    assert list(p.tabella.columns) == ["usd", "high", "low", "fx", "eur"]
    assert p.date[-1] == pd.Timestamp(FINE)


def test_meteo_media_delle_città(rete):
    fine = pd.Timestamp(FINE)
    t = FonteMeteo().scarica(fine - pd.Timedelta(days=400), fine)
    assert t.index[-1] == fine and t.index[0] == fine - pd.Timedelta(days=400)
    assert t.between(-20, 40).all() and t.notna().all()


def test_meteo_servono_almeno_tre_città(rete, monkeypatch):
    originale = rete.meteo

    def poche_citta(params):
        luoghi = originale(params)
        for l in luoghi[2:]:
            l["daily"]["temperature_2m_mean"] = [None] * len(l["daily"]["time"])
        return luoghi

    monkeypatch.setattr(rete, "meteo", poche_citta)
    fine = pd.Timestamp(FINE)
    with pytest.raises(ValueError, match="Open-Meteo"):
        FonteMeteo().scarica(fine - pd.Timedelta(days=60), fine)


def test_gpr(rete):
    g = FonteGpr().scarica()
    assert list(g.columns) == ["GPRD", "GPRD_ACT", "GPRD_THREAT", "event"]
    assert g.index.is_monotonic_increasing and isinstance(g.index, pd.DatetimeIndex)


def test_pompa_solo_italia(rete):
    p = FontePompa().scarica()
    assert list(p.columns) == ["Benzina", "Gasolio"]
    assert (p["Benzina"] < 5).all()  # le righe francesi (9 €) sono escluse
    with pytest.raises(ValueError, match="Italia"):
        FontePompa(paese="XX").scarica()
    assert np.issubdtype(p.dtypes.iloc[0], np.floating)
