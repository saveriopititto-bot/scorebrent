"""L'app completa, eseguita con il simulatore di Streamlit sui dati sintetici."""
from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

from interfaccia.schede import SCHEDE

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PROVE = ("Esegui la prova", "Esegui la prova dell'oscillazione")


def avvia(query=None, imposta=None, bottoni=()) -> AppTest:
    st.cache_data.clear()  # ogni test con i suoi dati finti
    at = AppTest.from_file(APP, default_timeout=300)
    if query:
        at.query_params.update(query)
    at.run()
    if imposta:
        imposta(at)
        at.run()
    for etichetta in bottoni:
        next(b for b in at.button if b.label == etichetta).click()
        at.run()
    return at


def valori(at, tipo) -> list[str]:
    return [e.value for e in getattr(at, tipo)]


def nessun_errore(at):
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, valori(at, "error")


def test_tutte_le_schede(rete):
    at = avvia(bottoni=PROVE)
    nessun_errore(at)
    assert [t.label for t in at.tabs] == [s.titolo for s in SCHEDE]
    assert len(at.tabs) == 10
    etichette = [m.label for m in at.metric]
    for attesa in ("Brent in euro", "Score S", "Oscillazione attesa", "Benzina", "Valore più recente",
                   "Media degli ultimi 30 giorni"):
        assert attesa in etichette
    assert len(at.dataframe) >= 8  # comprese le tabelle delle due prove
    assert any("Periodo di verifica" in c for c in valori(at, "caption"))
    assert any("### 8. Score rifornimento" in m for m in valori(at, "markdown"))


def test_settimana_per_settimana(rete):
    at = avvia(imposta=lambda at: at.sidebar.radio[0].set_value("Settimana per settimana"), bottoni=PROVE)
    nessun_errore(at)
    assert any("alla settimana" in c for c in valori(at, "caption"))


def test_pagina_dello_score_per_fuelmode(rete):
    at = avvia(query={"pagina": "score"})
    nessun_errore(at)
    assert not at.tabs
    assert [m.label for m in at.metric] == ["Score S", "Brent rispetto alla media 30 giorni",
                                            "Oscillazione attesa in 5 giorni", "Stabilità"]
    assert len(at.dataframe) == 3  # verifica sul Brent e due tabelle della pompa


def test_dati_esterni_disattivati(rete):
    def spegni(at):
        for c in at.sidebar.checkbox:
            c.uncheck()

    at = avvia(imposta=spegni, bottoni=PROVE)
    nessun_errore(at)
    info = " ".join(valori(at, "info"))
    for frase in ("temperatura è disattivata", "rischio geopolitico è disattivato", "prezzi alla pompa sono disattivati",
                  "Attiva «Usa i prezzi alla pompa"):
        assert frase in info


def test_fonti_esterne_irraggiungibili(rete):
    rete.guasti |= {"open-meteo", "fuel-prices", "iacoviello", "^OVX"}
    at = avvia()
    assert not at.exception
    avvisi = " ".join(valori(at, "warning"))
    for frase in ("temperature da Open-Meteo", "rischio geopolitico (GPR)", "prezzi alla pompa", "l'OVX"):
        assert frase in avvisi
    assert any("Prezzi alla pompa non disponibili" in i for i in valori(at, "info"))


def test_yahoo_irraggiungibile(rete):
    rete.guasti.add("BZ=F")
    at = avvia()
    assert valori(at, "error") == ["Non sono riuscito a scaricare i prezzi: BZ=F non raggiungibile"]
    assert not at.tabs


def test_altre_impostazioni(rete):
    def imposta(at):
        at.sidebar.number_input[0].set_value(2.0)
        at.sidebar.slider[-1].set_value(0.5)    # θ
        at.sidebar.slider[-2].set_value(0.3)    # α

    at = avvia(imposta=imposta, bottoni=PROVE)
    nessun_errore(at)
    assert any("Con α = 0.3 e θ = 0.50." in c for c in valori(at, "caption"))
    assert any("di oltre **2.0%**" in m for m in valori(at, "markdown"))


def test_un_errore_resta_nella_sua_scheda(rete, monkeypatch):
    from interfaccia.schede.andamento import SchedaAndamento

    def guasta(self):
        raise RuntimeError("guasto di prova")

    monkeypatch.setattr(SchedaAndamento, "mostra", guasta)
    at = avvia()
    assert [str(e.value) for e in at.exception] == ["guasto di prova"]
    assert len(at.tabs) == 10 and any("### 1. Dati e notazione" in m for m in valori(at, "markdown"))
