import numpy as np
import pytest

from brent.cammino import CamminoPiano, Percorso, Riepilogo


def test_altezze_sono_rendimenti_logaritmici_in_scala():
    p = Percorso(np.log([100, 110, 99]), scala=100)
    np.testing.assert_allclose(p.altezze, 100 * np.log([1.1, 0.9]))


def test_riepilogo_netto_telescopico_e_parti():
    livello = np.array([0.0, 0.3, 0.1, 0.5, 0.2])
    r = Percorso(livello).riepilogo()
    assert r.net == pytest.approx(livello[-1] - livello[0])
    assert r.parte_positiva + r.parte_negativa == pytest.approx(r.net)
    assert r.parte_positiva - r.parte_negativa == pytest.approx(r.variazione_totale)
    assert r.salto_max == pytest.approx(0.4) and r.salto_min == pytest.approx(-0.3)
    assert r.rms == pytest.approx(np.sqrt(np.mean(np.diff(livello) ** 2)))


def test_efficienza_fra_zero_e_uno():
    assert Riepilogo.da_altezze([1, 2, 3]).efficienza == pytest.approx(1.0)
    assert Riepilogo.da_altezze([1, -1, 1, -1]).efficienza == pytest.approx(0.0)
    assert 0 < Riepilogo.da_altezze([2, -1]).efficienza < 1


def test_riepilogo_vuoto_e_senza_movimento():
    vuoto = Riepilogo.da_altezze([])
    assert np.isnan(vuoto.net) and np.isnan(vuoto.efficienza)
    assert np.isnan(Riepilogo.da_altezze([0, 0]).efficienza)


def test_area_del_quadrato_antiorario_vale_uno():
    x, y = [0, 1, 1, 0, 0], [0, 0, 1, 1, 0]
    assert CamminoPiano(x, y).area_levy() == pytest.approx(1.0)
    assert CamminoPiano(x[::-1], y[::-1]).area_levy() == pytest.approx(-1.0)


def test_proprieta_dell_area_di_levy():
    rng = np.random.default_rng(0)
    x, y = rng.normal(size=30).cumsum(), rng.normal(size=30).cumsum()
    a = CamminoPiano(x, y).area_levy()
    assert CamminoPiano(x + 5, y - 3).area_levy() == pytest.approx(a)   # invariante per traslazione
    assert CamminoPiano(y, x).area_levy() == pytest.approx(-a)          # antisimmetrica
    assert CamminoPiano(x, 2 + 3 * x).area_levy() == pytest.approx(0)   # nulla se y è affine in x
    assert CamminoPiano([1], [2]).area_levy() == 0.0


def test_segno_positivo_se_il_prezzo_anticipa():
    t = np.linspace(0, 4 * np.pi, 200)
    prezzo, attivita = np.sin(t), np.sin(t - 0.5)  # l'attività segue il prezzo
    assert CamminoPiano(prezzo, attivita).area_levy() > 0
    assert CamminoPiano(attivita, prezzo).area_levy() < 0


def test_area_mobile_normalizzata():
    rng = np.random.default_rng(1)
    x, y = rng.normal(size=60).cumsum(), rng.normal(size=60).cumsum()
    w = 10
    a = CamminoPiano(x, y).area_levy_mobile(w)
    assert np.isnan(a[:w]).all() and np.isfinite(a[w:]).all()
    f = CamminoPiano(x, y).finestra(25, w)
    dx, dy = f.incrementi
    assert a[25] == pytest.approx(f.area_levy() / (w * dx.std(ddof=1) * dy.std(ddof=1)))
    # cambiare scala ai canali non cambia l'indice
    np.testing.assert_allclose(CamminoPiano(3 * x, 0.1 * y).area_levy_mobile(w), a, equal_nan=True)
    # finestre senza movimento restano NaN
    assert np.isnan(CamminoPiano(np.zeros(20), np.arange(20.0)).area_levy_mobile(5)[5:]).all()
