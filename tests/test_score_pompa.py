import numpy as np
import pandas as pd
import pytest

from brent.mercato import Ovx
from brent.pompa import AnalisiPompa
from brent.score import Esito, ScoreRifornimento

from .conftest import ReteFinta


def _serie(valori, inizio="2024-01-01"):
    return pd.Series(valori, index=pd.bdate_range(inizio, periods=len(valori)), dtype=float)


def test_formula_dello_score():
    prezzo = _serie(np.r_[np.full(40, 100.0), 104.0])
    sigma, norma = _serie(np.full(41, 0.01)), _serie(np.full(41, 0.01))
    sc = ScoreRifornimento(alpha=1, soglia=1).calcola(prezzo, sigma, norma)
    oggi = sc.iloc[-1]
    media = prezzo[prezzo.index > prezzo.index[-1] - pd.Timedelta(days=30)].mean()
    assert oggi.media == pytest.approx(media)
    assert oggi.scarto == pytest.approx(np.log(104 / media))
    assert oggi.stabilita == 1.0
    assert oggi.S == pytest.approx(np.log(104 / media) / (0.01 * np.sqrt(5)))
    assert oggi.classe == 1


def test_stabilità_smorza_lo_score_nei_mercati_agitati():
    prezzo = _serie(np.r_[np.full(40, 100.0), 104.0])
    calma = ScoreRifornimento(alpha=1).calcola(prezzo, _serie(np.full(41, 0.01)), _serie(np.full(41, 0.01)))
    agitata = ScoreRifornimento(alpha=1).calcola(prezzo, _serie(np.full(41, 0.02)), _serie(np.full(41, 0.01)))
    assert agitata.stabilita.iloc[-1] == pytest.approx(np.exp(-1))
    assert agitata.S.iloc[-1] == pytest.approx(calma.S.iloc[-1] / 2 * np.exp(-1))
    senza = ScoreRifornimento(alpha=0).calcola(prezzo, _serie(np.full(41, 0.02)), _serie(np.full(41, 0.01)))
    assert senza.stabilita.iloc[-1] == 1.0


@pytest.mark.parametrize("ultimo,esito", [(100.0, 0), (95.0, -1), (106.0, 1)])
def test_soglie(ultimo, esito):
    prezzo = _serie(np.r_[np.full(40, 100.0), ultimo])
    sc = ScoreRifornimento(soglia=1).calcola(prezzo, _serie(np.full(41, 0.01)), _serie(np.full(41, 0.01)))
    assert sc.classe.iloc[-1] == esito
    assert sc.classe.iloc[:10].isna().all()  # media dei 30 giorni non ancora disponibile


def test_soglia_inclusa():
    """Uno score esattamente uguale a ±θ dà già +1 o −1."""
    sigma = _serie(np.full(41, 0.01))
    for ultimo, esito in ((104.0, 1), (96.0, -1)):
        prezzo = _serie(np.r_[np.full(40, 100.0), ultimo])
        s = ScoreRifornimento().calcola(prezzo, sigma, sigma).S.iloc[-1]
        assert ScoreRifornimento(soglia=abs(s)).calcola(prezzo, sigma, sigma).classe.iloc[-1] == esito
        assert ScoreRifornimento(soglia=abs(s) * 1.0001).calcola(prezzo, sigma, sigma).classe.iloc[-1] == 0


def test_esito():
    assert [e.codice for e in Esito] == ["+1", "0", "-1"]
    assert Esito(-1).etichetta == "−1 aspetta" and Esito.RIFORNISCI == 1


def test_storico_dello_score(prezzi):
    ovx = Ovx.giornaliero(ReteFinta().yahoo["^OVX"]["Close"].tz_localize(None).rename_axis(None), prezzi.date)
    storico = ScoreRifornimento().storico(prezzi, ovx)
    sc = storico.tabella
    assert storico.modello == "+ agitazione e OVX"
    assert list(sc.columns) == ["prezzo", "media", "scarto", "sigma", "stabilita", "S", "classe"]
    assert sc.index.equals(prezzi.date)
    assert np.isfinite(storico.oggi[["S", "sigma", "classe"]].astype(float)).all()
    assert set(sc.classe.dropna().unique()) <= {-1, 0, 1}
    assert sc.stabilita.dropna().between(0, 1).all()
    assert sc.S.notna().mean() > 0.5
    assert ScoreRifornimento().storico(prezzi).modello == "+ agitazione"


def test_verifica_dello_score(prezzi):
    sc = ScoreRifornimento().storico(prezzi).tabella
    ver = ScoreRifornimento().verifica(sc).set_index("Classe")
    assert list(ver.index) == ["+1", "0", "-1", "Tutti"]
    assert ver.loc[["+1", "0", "-1"], "Giorni"].sum() == ver.loc["Tutti", "Giorni"]
    assert ver.loc["Tutti", "Quota"] == 1.0


# --------------------------------------------------------------------------- pompa
@pytest.fixture(scope="module")
def pompa():
    d = ReteFinta().pompa()
    d = d[d.country_code == "IT"].set_index("week")[["euro95_eur_l", "diesel_eur_l"]]
    return d.rename(columns={"euro95_eur_l": "Benzina", "diesel_eur_l": "Gasolio"}).rename_axis(None)


def test_ritardo_della_pompa(prezzi, pompa):
    analisi = AnalisiPompa(pompa)
    brent_l = analisi.brent_al_litro(prezzi.tabella["eur"])
    assert brent_l.index.equals(pompa.index)
    for carburante, ritardo, quota in (("Benzina", 1, 0.6), ("Gasolio", 2, 0.7)):
        rit = analisi.ritardo(brent_l, carburante).set_index("Ritardo (settimane)")
        assert list(rit.index) == [0, 1, 2, 3, 4]
        assert rit["Correlazione"].idxmax() == ritardo
        assert rit.loc[ritardo, "Quota trasferita"] == pytest.approx(quota * 158.987 / 159, rel=0.1)


def test_verifica_dello_score_sulla_pompa(pompa):
    giorni = pd.bdate_range(pompa.index[0], pompa.index[-1])
    # uno score che «sa» se la benzina salirà: deve far risparmiare sempre
    sale = (pompa["Benzina"].shift(-1) > pompa["Benzina"]).astype(int) * 2 - 1
    classe = sale.reindex(giorni, method="ffill")
    ver = AnalisiPompa(pompa).verifica_score(classe)
    tab = ver.tabella.set_index("Classe")
    assert list(tab.index) == ["+1", "0", "-1", "Tutte"] and tab.loc["0", "Settimane"] == 0
    assert tab.loc["+1", "Benzina dopo 1"] > 0 > tab.loc["-1", "Benzina dopo 1"]
    r = ver.risparmio.set_index(["Carburante", "Settimane"])
    assert r.loc[("Benzina", 1), "Volte in cui ha fatto risparmiare"] == 1.0
    assert r.loc[("Benzina", 1), "Risparmio medio (€ per pieno)"] > 0
    # il segnale opposto fa perdere esattamente lo stesso
    contrario = AnalisiPompa(pompa).verifica_score(-classe).risparmio.set_index(["Carburante", "Settimane"])
    assert contrario.loc[("Benzina", 1), "Risparmio medio (€ per pieno)"] == pytest.approx(
        -r.loc[("Benzina", 1), "Risparmio medio (€ per pieno)"])
