import numpy as np
import pandas as pd
import pytest

import cpk_levy_nn as cli
from brent.cammino import CamminoPiano
from brent.capacita import (AreaLevyRiepilogo, FinestreCapacita, LimitiSpecifica, PrevisioneCapacita,
                            ReteNeurale)


def area_originale(x):
    """La formula dello script di partenza, scritta a parte per confronto."""
    d = (x[2:] - x[:-2]) / 2.0
    px, py = x[1:-1], d
    px, py = px - px[0], py - py[0]
    return 0.5 * np.sum(px[:-1] * py[1:] - py[:-1] * px[1:])


def test_cp_e_cpk():
    lim = LimitiSpecifica()
    cp, cpk = lim.indici(0.0, 0.1)
    assert cp == pytest.approx(2 / 0.6) and cpk == pytest.approx(1 / 0.3)  # centrato: Cpk = Cp
    cp, cpk = lim.indici(0.5, 0.1)
    assert cp == pytest.approx(2 / 0.6) and cpk == pytest.approx(0.5 / 0.3)  # più vicino a USL
    assert lim.indici(-0.5, 0.1) == lim.indici(0.5, 0.1)                    # simmetrico
    assert lim.indici(0.0, 0.0) == (10.0, 10.0)                             # pavimento di sigma e tetto
    assert lim.indici(1.0, 0.2)[1] == 0.0                                   # media sul limite
    with pytest.raises(ValueError):
        LimitiSpecifica(usl=-1, lsl=1)


def test_area_coincide_con_la_formula_originale_e_con_cammino_piano():
    rng = np.random.default_rng(0)
    for n in (3, 5, 9):
        x = rng.normal(size=n)
        a = FinestreCapacita.area_levy(x)
        assert a == pytest.approx(area_originale(x))
        assert a == pytest.approx(CamminoPiano(x[1:-1], (x[2:] - x[:-2]) / 2).area_levy())
    x = rng.normal(size=5)
    assert FinestreCapacita.area_levy(x + 3) == pytest.approx(FinestreCapacita.area_levy(x))  # traslazione
    assert FinestreCapacita.area_levy(np.linspace(-1, 1, 5)) == pytest.approx(0)            # retta: area nulla


def test_tabella_delle_finestre():
    s = pd.Series([0.0, 0.2, 2.0, -0.1, 0.1, np.nan, 0.3, -3.0], index=pd.bdate_range("2026-01-05", periods=8))
    W = FinestreCapacita().tabella(s)
    x = np.clip(s.dropna().to_numpy(), -1, 1)                    # NaN tolto, valori portati in [-1, 1]
    assert list(W.columns) == ["mu", "sigma", "cp", "cpk", "area"] and len(W) == len(x) - 4
    assert list(W.index) == list(s.dropna().index[4:])          # etichetta = ultimo giorno della finestra
    w0 = x[:5]
    assert W.mu.iloc[0] == pytest.approx(w0.mean()) and W.sigma.iloc[0] == pytest.approx(w0.std(ddof=1))
    assert W.area.iloc[-1] == pytest.approx(area_originale(x[-5:]))
    assert len(FinestreCapacita(passo=2).tabella(s)) == 2
    piatta = FinestreCapacita().tabella(pd.Series(np.full(6, 0.3)))
    assert (piatta.sigma == 0.01).all() and (piatta.cp == 10).all()
    with pytest.raises(ValueError):
        FinestreCapacita(larghezza=2)


def test_back_propagation_uguale_al_gradiente_numerico():
    rng = np.random.default_rng(1)
    X, Y = rng.normal(size=(12, 4)), rng.normal(size=(12, 2))
    rete = ReteNeurale(4, nascosti=5, seme=2)
    g = rete.gradienti(X, Y, l2=0.1)
    eps = 1e-6
    for nome in ("W1", "b1", "W2", "b2"):
        p = getattr(rete, nome)
        num = np.zeros_like(p)
        for i in np.ndindex(p.shape):
            v = p[i]
            p[i] = v + eps
            su = rete.perdita(X, Y, 0.1)
            p[i] = v - eps
            giu = rete.perdita(X, Y, 0.1)
            p[i] = v
            num[i] = (su - giu) / (2 * eps)
        np.testing.assert_allclose(g[nome], num, rtol=1e-5, atol=1e-8)


def test_la_rete_impara_una_funzione_non_lineare():
    rng = np.random.default_rng(3)
    X = rng.uniform(-2, 2, (300, 2))
    Y = np.c_[np.sin(X[:, 0]), X[:, 0] * X[:, 1] / 2]
    rete = ReteNeurale(2, nascosti=16)
    prima = rete.perdita(X, Y)
    rete.adatta(X, Y, lr=0.05, epoche=4000)
    assert rete.perdita(X, Y) < 0.1 * prima


def test_dataset_usa_k_e_k_meno_1_per_prevedere_k_piu_1():
    W = FinestreCapacita().tabella(cli.serie_sintetica(40))
    d = PrevisioneCapacita().dataset(W)
    assert len(d) == len(W) - 1 and d.cp_succ.isna().sum() == 1
    r = d.iloc[3]
    k = int(r.k)
    assert r.cp == W.cp.iloc[k] and r.area_prec == W.area.iloc[k - 1]
    assert r.cp_succ == W.cp.iloc[k + 1] and r.cpk_succ == W.cpk.iloc[k + 1]


@pytest.fixture(scope="module")
def modello():
    return PrevisioneCapacita(epoche=300, passo=30, inizio_frac=0.5)


def test_prova_e_riferimento(modello):
    s = cli.serie_sintetica(400)
    prova = modello.valida(s)
    t = prova.tabella.set_index("Previsione")
    assert list(t.index) == [PrevisioneCapacita.RETE, PrevisioneCapacita.RIFERIMENTO]
    assert t.loc[PrevisioneCapacita.RIFERIMENTO, "Miglioramento Cp"] == 0
    m = prova.meta
    assert m.finestre == 396 and m.n_casi == 394 and m.n_test == len(prova.serie) and m.n_passi >= 2
    # il riferimento è Cp e Cpk della finestra di oggi
    W, fine = prova.finestre, prova.serie.fine
    np.testing.assert_allclose(prova.serie["Cp oggi"], W.cp.reindex(fine).to_numpy())
    np.testing.assert_allclose(prova.serie["Cp reale"], W.cp.shift(-1).reindex(fine).to_numpy())
    e = (prova.serie["Cpk oggi"] - prova.serie["Cpk reale"]).abs().mean()
    assert t.loc[PrevisioneCapacita.RIFERIMENTO, "MAE Cpk"] == pytest.approx(e)


def test_la_prova_non_usa_il_futuro(modello):
    """Cambiare la serie dopo un giorno non deve cambiare le previsioni delle finestre che finiscono prima."""
    s = cli.serie_sintetica(400)
    taglio = 330
    altra = s.copy()
    altra.iloc[taglio:] = np.random.default_rng(9).uniform(-1, 1, len(s) - taglio)
    a, b = modello.valida(s).serie, modello.valida(altra).serie
    # la previsione per la finestra k+1 usa le finestre fino a k, che finisce nel giorno `fine`
    prima = a.fine < taglio - 1
    assert prima.sum() > 20
    pd.testing.assert_frame_equal(a[prima], b[b.fine < taglio - 1])


def test_un_solo_taglio_e_previsione(modello):
    s = cli.serie_sintetica(300)
    uno = PrevisioneCapacita(epoche=200, passo=0, inizio_frac=0.7).valida(s)
    assert uno.meta.n_passi == 1 and uno.meta.n_test == uno.meta.n_casi - int(uno.meta.n_casi * 0.7)
    cp, cpk = modello.prevedi(s)
    assert 0 <= cpk <= cp <= 10
    with pytest.raises(ValueError):
        modello.valida(s.iloc[:40])


def test_area_di_levy_di_una_passeggiata_casuale():
    """Per un moto browniano l'area media del cammino (S, dS) su 5 giorni è -s²/2, non 0; il riferimento con gli
    incrementi rimescolati la ritrova e z resta piccolo."""
    x = np.cumsum(np.random.default_rng(4).normal(0, 1, 6000))
    r = AreaLevyRiepilogo.da_serie(x, FinestreCapacita())
    assert r.media == pytest.approx(-0.5, abs=0.05) and r.riferimento == pytest.approx(-0.5, abs=0.03)
    assert abs(r.z) < 3
    # una serie che oscilla in modo regolare non è una passeggiata casuale
    t = np.arange(600)
    onda = AreaLevyRiepilogo.da_serie(np.sin(2 * np.pi * t / 7), FinestreCapacita())
    assert abs(onda.z) > 3


def test_riga_di_comando(tmp_path, capsys):
    f = tmp_path / "dati.csv"
    pd.DataFrame({"score_gg": cli.serie_sintetica(250)}).to_csv(f, index=False)
    assert cli.main(["--csv", str(f), "--epoche", "100", "--passo", "40"]) == 0
    out = capsys.readouterr().out
    assert "MAE Cp" in out and "Domani come oggi" in out and "Prossima finestra" in out
    with pytest.raises(SystemExit):
        cli.main(["--csv", str(f), "--col", "manca"])
    corto = tmp_path / "corto.csv"
    pd.DataFrame({"score_gg": np.zeros(20)}).to_csv(corto, index=False)
    assert cli.main(["--csv", str(corto)]) == 1


def test_riga_di_comando_con_lo_score_del_brent(rete, capsys):
    assert cli.main(["--brent", "--epoche", "50", "--passo", "200"]) == 0
    assert "Giorni fuori da [-1, 1]" in capsys.readouterr().out
