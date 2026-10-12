import numpy as np
import pandas as pd
import pytest

from brent.mercato import Frequenza, SerieAnalisi
from brent.oscillazione import PrevisioneOscillazione
from brent.rialzo import PrevisioneRialzo


@pytest.fixture(scope="module")
def serie(prezzi):
    return SerieAnalisi.costruisci(prezzi, Frequenza.GIORNO)


# --------------------------------------------------------------------------- rialzo
def test_features_rialzo(serie):
    w, h = 20, 5
    feat = PrevisioneRialzo(w, h).features(serie.x, serie.y)
    assert list(feat.columns) == ["t", "dx", "dy", "cos", "levy", "sigma", "mad", "fwd"]
    assert feat.t.iloc[0] == w and feat.t.iloc[-1] == len(serie.x) - h - 1
    r = feat.iloc[100]
    t = int(r.t)
    assert r.dx == pytest.approx(serie.x[t] - serie.x[t - w])
    assert r.fwd == pytest.approx(serie.x[t + h] - serie.x[t])
    assert r.sigma == pytest.approx(np.log(np.diff(serie.x[t - w : t + 1]).std(ddof=1)))
    assert feat["cos"].between(-1, 1).all()


def test_features_rialzo_con_dati_esterni_scarta_le_righe_incomplete(serie):
    n = len(serie.x)
    meteo = np.full(n, 1.0)
    meteo[:300] = np.nan
    ovx = np.full(n, -3.0)
    ovx[500] = np.nan
    feat = PrevisioneRialzo(20, 5).features(serie.x, serie.y, meteo=meteo, ovx=ovx, gpr=np.zeros(n))
    assert {"meteo", "ovx", "gpr"} <= set(feat.columns)
    assert feat.t.min() >= 290 and 500 not in feat.t.values
    assert (feat.meteo == 1).all()


def test_prova_del_rialzo(serie):
    previsione = PrevisioneRialzo(20, 5, soglia=0.0)
    feat = previsione.features(serie.x, serie.y)
    prova = previsione.valida(feat, anni=serie.date[feat.t.to_numpy()].year)
    tab = prova.tabella.set_index("Insieme di predittori")
    assert list(tab.index) == ["Livello 1 (dx, dy)", "+ coseno", "+ area di Lévy", "+ oscillazione", "Tutto"]
    assert tab["AUC"].between(0, 1).all() and (tab["Brier"] > 0).all()
    np.testing.assert_allclose(tab["Skill"], 1 - tab["Brier"] / prova.meta.brier_base)
    assert (tab["Anni vinti"] <= tab["Anni"]).all()
    m = prova.meta
    assert 0 < m.pos_test < m.n_test and m.n_passi > 10
    assert m.primo_test > feat.t.iloc[int(0.4 * len(feat)) - 1]
    # una passeggiata casuale non si prevede: nessun miglioramento netto sul riferimento
    assert tab["Skill"].max() < 0.02


def test_il_rialzo_prevedibile_viene_trovato():
    """Se il futuro dipende dal passato (momentum), la prova deve accorgersene."""
    rng = np.random.default_rng(0)
    r = np.zeros(3000)
    for i in range(1, 3000):
        r[i] = 0.5 * r[i - 1] + rng.normal(0, 0.01)
    x, y = np.cumsum(r), np.abs(rng.normal(size=3000))
    previsione = PrevisioneRialzo(2, 1)
    tab = previsione.valida(previsione.features(x, y)).tabella.set_index("Insieme di predittori")
    assert tab.loc["Livello 1 (dx, dy)", "Skill"] > 0.05 and tab.loc["Livello 1 (dx, dy)", "AUC"] > 0.6


def test_prova_rialzo_errori():
    previsione = PrevisioneRialzo(5, 1)
    with pytest.raises(ValueError, match="Troppo pochi dati"):
        previsione.valida(pd.DataFrame({"t": range(50), "fwd": 0.0, "dx": 0.0, "dy": 0.0}))
    with pytest.raises(ValueError, match="sale sempre"):
        previsione.valida(pd.DataFrame({"t": range(200), "fwd": 1.0, "dx": 0.0, "dy": 0.0}))


# --------------------------------------------------------------------------- oscillazione
def test_features_oscillazione(serie):
    w, h = 20, 5
    feat = PrevisioneOscillazione(w, h).features(serie.x, serie.y)
    assert len(feat) == len(serie.x) - w
    assert feat.bersaglio.isna().sum() == h  # gli ultimi giorni non hanno ancora un futuro
    r = feat.iloc[200]
    t = int(r.t)
    rend = np.diff(serie.x)
    assert r.s_lungo == pytest.approx(np.log(np.sqrt(np.mean(rend[t - w : t] ** 2))))
    assert r.s_breve == pytest.approx(np.log(np.sqrt(np.mean(rend[t - 5 : t] ** 2))))
    assert r.bersaglio == pytest.approx(np.log(np.sqrt(np.mean(rend[t : t + h] ** 2))))
    assert r.agit == pytest.approx(serie.y[t - 4 : t + 1].mean())


def test_previsione_oscillazione_ragionevole(serie):
    previsione = PrevisioneOscillazione(20, 5)
    feat = previsione.features(serie.x, serie.y)
    sigma = previsione.prevedi(feat, previsione.INSIEMI["+ agitazione"])
    tipica = np.exp(feat.bersaglio.median())
    assert tipica / 3 < sigma < 3 * tipica
    with pytest.raises(ValueError):
        previsione.prevedi(feat.iloc[:20], previsione.INSIEMI["+ agitazione"])


def test_oscillazione_scorrevole_non_guarda_il_futuro(serie):
    previsione = PrevisioneOscillazione(20, 5)
    cols = previsione.INSIEMI["+ agitazione"]
    prima = previsione.scorrevole(previsione.features(serie.x, serie.y), cols)
    assert np.isnan(prima.iloc[: int(0.4 * len(prima))]).all() and np.isfinite(prima.iloc[-1])
    # stravolgere i prezzi dopo il giorno `taglio` non cambia nessuna previsione fatta fino a quel giorno
    taglio = 2000
    x, y = serie.x.copy(), serie.y.copy()
    x[taglio + 1 :] += np.random.default_rng(9).normal(0, 0.2, len(x) - taglio - 1).cumsum()
    y[taglio + 1 :] *= 5
    dopo = previsione.scorrevole(previsione.features(x, y), cols)
    fino = prima.index <= taglio
    np.testing.assert_array_equal(prima[fino].values, dopo[fino].values)
    assert not np.allclose(prima[~fino].values, dopo[~fino].values)


def test_prova_oscillazione(serie):
    previsione = PrevisioneOscillazione(20, 5)
    ovx = serie.x * 0 + np.log(0.02)
    feat = previsione.features(serie.x, serie.y, ovx=ovx)
    prova = previsione.valida(feat, anni=serie.date.year)
    tab = prova.tabella.set_index("Previsione")
    assert {"Come appena passato", "OVX così com'è", "Media storica", "+ agitazione e OVX"} <= set(tab.index)
    assert tab.loc["Come appena passato", "Miglioramento"] == pytest.approx(0)
    # con volatilità a grappoli il modello batte la media storica
    assert tab.loc["+ agitazione", "Miglioramento"] > tab.loc["Media storica", "Miglioramento"]
    assert (tab["MAD"] > 0).all() and (tab["Sigma"] > 0).all()
    assert len(prova.serie) == prova.meta.n_test and "Reale" in prova.serie


def test_modello_predefinito():
    assert PrevisioneOscillazione.modello_predefinito(True) == "+ agitazione e OVX"
    assert PrevisioneOscillazione.modello_predefinito(False) == "+ agitazione"
