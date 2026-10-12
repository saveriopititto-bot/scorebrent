import numpy as np
import pandas as pd
import pytest

from brent.modelli import (
    FinestreScorrevoli,
    InsiemiPredittori,
    Punteggi,
    RegressioneLogistica,
    RegressioneRidge,
    Standardizzatore,
)


def test_standardizzatore():
    X = np.array([[1.0, 5], [3, 5], [5, 5]])
    s = Standardizzatore.adatta(X)
    Z = s.trasforma(X)
    assert Z[:, 0].mean() == pytest.approx(0) and Z[:, 0].std() == pytest.approx(1)
    np.testing.assert_allclose(Z[:, 1], 0)  # colonna costante: divisa per 1, nessun NaN


def test_logistica_ritrova_il_segno_e_dà_probabilità():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(2000, 2))
    y = (rng.random(2000) < 1 / (1 + np.exp(-(2 * X[:, 0] - X[:, 1])))).astype(float)
    m = RegressioneLogistica().adatta(X, y)
    assert m.beta[1] > 1 and m.beta[2] < -0.5
    p = m.prevedi(X)
    assert ((p > 0) & (p < 1)).all()
    assert Punteggi.auc(y, p) > 0.8


def test_logistica_penalità_più_forte_coefficienti_più_piccoli():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(200, 1))
    y = (X[:, 0] + rng.normal(0, 0.5, 200) > 0).astype(float)
    assert abs(RegressioneLogistica(100).adatta(X, y).beta[1]) < abs(RegressioneLogistica(0.01).adatta(X, y).beta[1])


def test_ridge_senza_penalità_è_minimi_quadrati():
    rng = np.random.default_rng(2)
    X = rng.normal(size=(300, 3))
    y = 1 + X @ np.array([0.5, -2, 0]) + rng.normal(0, 0.1, 300)
    m = RegressioneRidge(lam=1e-10).adatta(X, y)
    ols = np.linalg.lstsq(np.c_[np.ones(300), X], y, rcond=None)[0]
    np.testing.assert_allclose(m.prevedi(X), np.c_[np.ones(300), X] @ ols, atol=1e-8)
    assert m.var_residui == pytest.approx(0.01, rel=0.2)


def test_ridge_correzione_lognormale():
    rng = np.random.default_rng(3)
    X = rng.normal(size=(5000, 1))
    log_sigma = -4 + 0.3 * X[:, 0] + rng.normal(0, 0.5, 5000)
    m = RegressioneRidge().adatta(X, log_sigma)
    # la media di exp(log_sigma) è ben stimata solo con il fattore exp(var/2)
    assert m.prevedi_esponenziale(X).mean() == pytest.approx(np.exp(log_sigma).mean(), rel=0.03)
    assert np.exp(m.prevedi(X)).mean() < 0.92 * np.exp(log_sigma).mean()


def test_finestre_scorrevoli_non_usano_il_futuro():
    t = np.arange(200)
    f = FinestreScorrevoli(orizzonte=5, passo=21, inizio_frac=0.4)
    blocchi = list(f.blocchi(t))
    assert blocchi[0][0] == 80 and blocchi[-1][1] == 200
    for a, _, tr in blocchi:
        assert (t[tr] + 5 <= t[a]).all()          # ogni esito noto all'inizio del blocco
        assert tr.sum() == a - 5 + 1
    utili = np.ones(200, bool)
    utili[::2] = False
    for _, _, tr in f.blocchi(t, utili):
        assert not tr[::2].any()


def test_finestre_saltano_i_blocchi_con_poco_addestramento():
    assert list(FinestreScorrevoli(orizzonte=40, passo=10, inizio_frac=0.4, minimo=30).blocchi(np.arange(100)))[0][0] == 70


def test_auc():
    assert Punteggi.auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert Punteggi.auc([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1]) == 0.0
    assert Punteggi.auc([0, 1, 0, 1], [0.5, 0.5, 0.5, 0.5]) == 0.5
    assert np.isnan(Punteggi.auc([1, 1], [0.2, 0.3]))
    # come la probabilità che un caso positivo abbia il punteggio più alto
    rng = np.random.default_rng(4)
    y, s = rng.integers(0, 2, 300), rng.normal(size=300)
    coppie = np.mean([a > b for a in s[y == 1] for b in s[y == 0]])
    assert Punteggi.auc(y, s) == pytest.approx(coppie)


def test_errore_standard_auc_usa_i_casi_effettivi():
    base = Punteggi.auc_errore_standard(100, 100, 1)
    assert base == pytest.approx(np.sqrt(201 / (12 * 100 * 100)))
    assert Punteggi.auc_errore_standard(100, 100, 5) > base


def test_brier_e_anni_vinti():
    assert Punteggi.brier(np.array([1.0, 0.5]), np.array([1.0, 0.0])) == pytest.approx(0.125)
    anni = np.array([2020, 2020, 2021, 2021])
    assert Punteggi.anni_vinti(np.array([0.1, 0.1, 1, 1]), np.array([0.5, 0.5, 0.5, 0.5]), anni) == (1, 2)


def test_insiemi_predittori():
    ins = InsiemiPredittori({"a": ["x"], "b": ["x", "z"], "Tutto": None}, ["x", "y", "z"])
    f = pd.DataFrame(columns=["x", "y"])
    assert ins.risolvi(f) == {"a": ["x"], "Tutto": ["x", "y"]}
    assert ins["Tutto"] == ["x", "y", "z"] and "b" in ins and list(ins) == ["a", "b", "Tutto"]
