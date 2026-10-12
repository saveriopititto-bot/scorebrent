"""L'app completa, eseguita con il simulatore di Streamlit sui dati sintetici."""
from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

from interfaccia.schede import SCHEDE, SEZIONI

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PROVE = ("Esegui la prova", "Esegui la prova dell'oscillazione")


def avvia(query=None, imposta=None, sezione=None, scheda=None, bottoni=()) -> AppTest:
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
    if scheda:
        menu_schede(at).set_value(scheda)
        at.run()
    for etichetta in bottoni:
        next(b for b in at.button if b.label == etichetta).click()
        at.run()
    return at


def menu_schede(at):
    return at.segmented_control(key=f"scheda-{at.segmented_control(key='sezione').value.lower()}")


def valori(at, tipo) -> list[str]:
    return [e.value for e in getattr(at, tipo)]


def etichette(at) -> list[str]:
    return [m.label for m in at.metric]


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
    assert list(menu_schede(at).options) == ["Score rifornimento", "Prossimi 5 giorni", "Pompa (Italia)"]
    assert menu_schede(at).value == "Score rifornimento"
    assert "Score S" in etichette(at) and not at.tabs
    assert not any("Prezzo del petrolio" in m for m in valori(at, "markdown"))  # niente titolo nel menù


def test_ogni_scheda_si_apre(rete):
    """Tutte le schede, una alla volta, senza errori; ognuna mostra le sue metriche."""
    attese = {"Prossimi 5 giorni": "Oscillazione attesa", "Pompa (Italia)": "Benzina", "Prezzo": "Brent in euro",
              "Andamento": "Valore più recente", "Meteo": "Media degli ultimi 30 giorni",
              "Geopolitica": "Minacce / atti (30 giorni)", "Oscillazione attesa": "Movimento probabile in 5 giorni"}
    for sezione in SEZIONI:
        for scheda in sezione.schede:
            at = avvia(sezione=sezione.nome, scheda=scheda.titolo)
            nessun_errore(at)
            assert menu_schede(at).value == scheda.titolo
            if scheda.titolo in attese:
                assert attese[scheda.titolo] in etichette(at), scheda.titolo


def test_ogni_sezione_ricorda_la_sua_scheda(rete):
    at = avvia(sezione="Mercato", scheda="Meteo")
    at.segmented_control(key="sezione").set_value("Modelli")
    at.run()
    assert menu_schede(at).value == "Prova di previsione"
    at.segmented_control(key="sezione").set_value("Mercato")
    at.run()
    assert menu_schede(at).value == "Meteo"


def test_le_due_prove(rete):
    at = avvia(sezione="Modelli", bottoni=("Esegui la prova",))
    nessun_errore(at)
    assert len(at.dataframe) == 1 and any("Periodo di verifica" in c for c in valori(at, "caption"))
    at = avvia(sezione="Modelli", scheda="Oscillazione attesa", bottoni=("Esegui la prova dell'oscillazione",))
    nessun_errore(at)
    assert len(at.dataframe) == 1 and any("Periodo di verifica" in c for c in valori(at, "caption"))
    at = avvia(sezione="Modelli", scheda="Formule")
    assert any("### 8. Score rifornimento" in m for m in valori(at, "markdown"))


def test_settimana_per_settimana(rete):
    at = avvia(imposta=lambda at: widget(at, "radio", "Raggruppa i prezzi").set_value("Settimana per settimana"),
               sezione="Modelli", scheda="Oscillazione attesa", bottoni=PROVE[1:])
    nessun_errore(at)
    assert any("alla settimana" in c for c in valori(at, "caption"))


def test_pagina_dello_score_per_fuelmode(rete):
    at = avvia(query={"pagina": "score"})
    nessun_errore(at)
    assert not at.segmented_control
    assert [m.label for m in at.metric] == ["Score S", "Brent rispetto alla media 30 giorni",
                                            "Oscillazione attesa in 5 giorni", "Stabilità"]
    assert len(at.dataframe) == 3  # verifica sul Brent e due tabelle della pompa


def _spegni(at):
    for c in at.sidebar.checkbox:
        c.uncheck()


def test_dati_esterni_disattivati(rete):
    attese = {("Rifornimento", "Score rifornimento"): "Prezzi alla pompa in Italia",
              ("Rifornimento", "Pompa (Italia)"): "Prezzi alla pompa in Italia",
              ("Mercato", "Meteo"): "Temperatura in Europa",
              ("Mercato", "Geopolitica"): "Rischio geopolitico (GPR)"}
    for (sezione, scheda), interruttore in attese.items():
        at = avvia(imposta=_spegni, sezione=sezione, scheda=scheda)
        nessun_errore(at)
        avvisi = [i for i in valori(at, "info") if i.startswith("Per questa parte")]
        assert avvisi == [f"Per questa parte attiva «{interruttore}» in «Dati», nella barra laterale."]
    nessun_errore(avvia(imposta=_spegni, sezione="Modelli", bottoni=PROVE[:1]))
    nessun_errore(avvia(imposta=_spegni, sezione="Modelli", scheda="Oscillazione attesa", bottoni=PROVE[1:]))


def test_fonti_esterne_irraggiungibili(rete):
    rete.guasti |= {"open-meteo", "fuel-prices", "iacoviello", "^OVX"}
    attese = {("Rifornimento", "Pompa (Italia)"): "prezzi alla pompa", ("Mercato", "Meteo"): "temperature da Open-Meteo",
              ("Mercato", "Geopolitica"): "rischio geopolitico (GPR)", ("Modelli", "Oscillazione attesa"): "l'OVX"}
    for (sezione, scheda), frase in attese.items():
        at = avvia(sezione=sezione, scheda=scheda)
        assert not at.exception
        assert any(frase in w for w in valori(at, "warning")), scheda


def test_scarica_solo_i_dati_della_scheda_aperta(rete, monkeypatch):
    import requests

    richieste = []
    monkeypatch.setattr(requests, "get", lambda url, **k: richieste.append(url) or rete.get(url, **k))
    avvia()  # Score rifornimento: servono solo prezzi, OVX e pompa
    assert richieste and all("fuel-prices" in u for u in richieste)
    richieste.clear()
    avvia(sezione="Mercato", scheda="Meteo")  # passa prima dallo score, poi apre Meteo
    assert any("open-meteo" in u for u in richieste) and not any("iacoviello" in u for u in richieste)


def test_yahoo_irraggiungibile(rete):
    rete.guasti.add("BZ=F")
    at = avvia()
    assert valori(at, "error") == ["Non sono riuscito a scaricare i prezzi: BZ=F non raggiungibile"]
    assert not at.segmented_control


def test_altre_impostazioni(rete):
    def imposta(at):
        at.sidebar.number_input[0].set_value(2.0)
        widget(at, "slider", "Soglia (θ)").set_value(0.5)
        widget(at, "slider", "Sensibilità alla turbolenza (α)").set_value(0.3)

    at = avvia(imposta=imposta)
    nessun_errore(at)
    assert any("con α = 0.3 e θ = 0.50" in c for c in valori(at, "caption"))
    at = avvia(imposta=imposta, sezione="Modelli", bottoni=PROVE[:1])
    nessun_errore(at)
    assert any("di oltre **2.0%**" in m for m in valori(at, "markdown"))


def test_un_errore_resta_nella_sua_scheda(rete, monkeypatch):
    from interfaccia.schede.andamento import SchedaAndamento

    def guasta(self):
        raise RuntimeError("guasto di prova")

    monkeypatch.setattr(SchedaAndamento, "mostra", guasta)
    at = avvia(sezione="Mercato", scheda="Andamento")
    assert [str(e.value) for e in at.exception] == ["guasto di prova"]
    assert menu_schede(at).value == "Andamento"  # il menù resta, si può cambiare scheda
    menu_schede(at).set_value("Prezzo")
    at.run()
    nessun_errore(at)
    assert "Brent in euro" in etichette(at)
