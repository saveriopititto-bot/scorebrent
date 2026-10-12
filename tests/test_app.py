"""L'app completa, eseguita con il simulatore di Streamlit sui dati sintetici."""
from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

from interfaccia.schede import SCHEDE, SEZIONI

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PROVE = ("Esegui la prova", "Esegui la prova dell'oscillazione")


def avvia(query=None, imposta=None, sezione=None, bottoni=()) -> AppTest:
    st.cache_data.clear()  # ogni test con i suoi dati finti
    at = AppTest.from_file(APP, default_timeout=300)
    if query:
        at.query_params.update(query)
    at.run()
    if imposta:
        imposta(at)
        at.run()
    if sezione:
        at.segmented_control(key="sezione").set_value(sezione)
        at.run()
    for etichetta in bottoni:
        next(b for b in at.button if b.label == etichetta).click()
        at.run()
    return at


def valori(at, tipo) -> list[str]:
    return [e.value for e in getattr(at, tipo)]


def schede(at) -> list[str]:
    return [t.label for t in at.tabs]


def widget(at, tipo, etichetta):
    return next(w for w in getattr(at.sidebar, tipo) if w.label == etichetta)


def nessun_errore(at):
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, valori(at, "error")


def test_ogni_scheda_sta_in_una_sezione():
    assert sorted(s.__name__ for s in SCHEDE) == sorted({s.__name__ for sez in SEZIONI for s in sez.schede})
    assert len(SCHEDE) == 10 and [s.nome for s in SEZIONI] == ["Rifornimento", "Mercato", "Modelli"]


def test_menu_si_apre_su_rifornimento(rete):
    at = avvia()
    nessun_errore(at)
    menu = at.segmented_control(key="sezione")
    assert menu.value == "Rifornimento" and list(menu.options) == [s.nome for s in SEZIONI]
    assert schede(at) == ["Score rifornimento", "Prossimi 5 giorni", "Pompa (Italia)"]
    etichette = [m.label for m in at.metric]
    for attesa in ("Score S", "Oscillazione attesa", "Benzina"):
        assert attesa in etichette


def test_sezione_mercato(rete):
    at = avvia(sezione="Mercato")
    nessun_errore(at)
    assert schede(at) == ["Prezzo", "Andamento", "Meteo", "Geopolitica"]
    etichette = [m.label for m in at.metric]
    for attesa in ("Brent in euro", "Valore più recente", "Media degli ultimi 30 giorni"):
        assert attesa in etichette


def test_sezione_modelli_con_le_prove(rete):
    at = avvia(sezione="Modelli", bottoni=PROVE)
    nessun_errore(at)
    assert schede(at) == ["Prova di previsione", "Oscillazione attesa", "Formule"]
    assert len(at.dataframe) == 1  # la tabella dell'ultima prova eseguita
    assert any("Periodo di verifica" in c for c in valori(at, "caption"))
    assert any("### 8. Score rifornimento" in m for m in valori(at, "markdown"))


def test_settimana_per_settimana(rete):
    at = avvia(imposta=lambda at: widget(at, "radio", "Raggruppa i prezzi").set_value("Settimana per settimana"),
               sezione="Modelli", bottoni=PROVE)
    nessun_errore(at)
    assert any("alla settimana" in c for c in valori(at, "caption"))


def test_pagina_dello_score_per_fuelmode(rete):
    at = avvia(query={"pagina": "score"})
    nessun_errore(at)
    assert not at.tabs and not at.segmented_control
    assert [m.label for m in at.metric] == ["Score S", "Brent rispetto alla media 30 giorni",
                                            "Oscillazione attesa in 5 giorni", "Stabilità"]
    assert len(at.dataframe) == 3  # verifica sul Brent e due tabelle della pompa


def _spegni(at):
    for c in at.sidebar.checkbox:
        c.uncheck()


def test_dati_esterni_disattivati(rete):
    attese = {"Rifornimento": ["Prezzi alla pompa in Italia"] * 2,
              "Mercato": ["Temperatura in Europa", "Rischio geopolitico (GPR)"]}
    for sezione, interruttori in attese.items():
        at = avvia(imposta=_spegni, sezione=sezione)
        nessun_errore(at)
        avvisi = [i for i in valori(at, "info") if i.startswith("Per questa parte")]
        assert avvisi == [f"Per questa parte attiva «{i}» in «Dati», nella barra laterale." for i in interruttori]
    nessun_errore(avvia(imposta=_spegni, sezione="Modelli", bottoni=PROVE))


def test_fonti_esterne_irraggiungibili(rete):
    rete.guasti |= {"open-meteo", "fuel-prices", "iacoviello", "^OVX"}
    avvisi = []
    for sezione in ("Rifornimento", "Mercato", "Modelli"):
        at = avvia(sezione=sezione)
        assert not at.exception
        avvisi += valori(at, "warning")
    testo = " ".join(avvisi)
    for frase in ("temperature da Open-Meteo", "rischio geopolitico (GPR)", "prezzi alla pompa", "l'OVX"):
        assert frase in testo


def test_yahoo_irraggiungibile(rete):
    rete.guasti.add("BZ=F")
    at = avvia()
    assert valori(at, "error") == ["Non sono riuscito a scaricare i prezzi: BZ=F non raggiungibile"]
    assert not at.tabs


def test_altre_impostazioni(rete):
    def imposta(at):
        at.sidebar.number_input[0].set_value(2.0)
        widget(at, "slider", "Soglia (θ)").set_value(0.5)
        widget(at, "slider", "Sensibilità alla turbolenza (α)").set_value(0.3)

    at = avvia(imposta=imposta)
    nessun_errore(at)
    assert any("con α = 0.3 e θ = 0.50" in c for c in valori(at, "caption"))
    at = avvia(imposta=imposta, sezione="Modelli", bottoni=PROVE)
    nessun_errore(at)
    assert any("di oltre **2.0%**" in m for m in valori(at, "markdown"))


def test_un_errore_resta_nella_sua_scheda(rete, monkeypatch):
    from interfaccia.schede.andamento import SchedaAndamento

    def guasta(self):
        raise RuntimeError("guasto di prova")

    monkeypatch.setattr(SchedaAndamento, "mostra", guasta)
    at = avvia(sezione="Mercato")
    assert [str(e.value) for e in at.exception] == ["guasto di prova"]
    assert len(at.tabs) == 4 and "Brent in euro" in [m.label for m in at.metric]
