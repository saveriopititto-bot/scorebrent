import json
import subprocess
import sys
from pathlib import Path

import pytest

import esporta_score as es

RADICE = Path(__file__).resolve().parent.parent


@pytest.fixture
def storico(rete):
    e = es.EsportazioneScore(1.0, 1.0)
    return e, e.calcola()


def test_righe_della_tabella(storico):
    e, s = storico
    righe = e.righe(s, 5)
    assert len(righe) == 5
    r = righe[-1]
    assert set(r) == {"data", "esito", "score", "brent_eur", "media_30_eur", "scarto", "oscillazione_5g", "stabilita",
                      "alpha", "theta", "modello", "aggiornato_il"}
    assert r["esito"] in (-1, 0, 1) and r["modello"] == "+ agitazione e OVX"
    oggi = s.oggi
    assert r["score"] == round(float(oggi.S), 6)
    assert r["oscillazione_5g"] == round(float(oggi.sigma) * 5 ** 0.5, 6)
    assert [x["data"] for x in righe] == sorted(x["data"] for x in righe)
    tutte = e.righe(s, 0)
    assert len(tutte) == s.tabella.S.notna().sum()
    json.dumps(tutte)  # serializzabili per l'API


def test_senza_ovx_usa_agitazione(rete, capsys):
    rete.guasti.add("^OVX")
    s = es.EsportazioneScore().calcola()
    assert s.modello == "+ agitazione"
    assert "OVX non disponibile" in capsys.readouterr().err


def test_cliente_supabase_invia_a_blocchi(monkeypatch):
    chiamate = []

    class Risposta:
        status_code, text = 201, ""

    monkeypatch.setattr(es.requests, "post", lambda url, headers, json, timeout: chiamate.append((url, headers, json))
                        or Risposta())
    es.ClienteSupabase("https://x.supabase.co/", "chiave").invia([{"data": str(i)} for i in range(1200)])
    assert [len(c[2]) for c in chiamate] == [500, 500, 200]
    url, intestazioni, _ = chiamate[0]
    assert url == "https://x.supabase.co/rest/v1/brent_score?on_conflict=data"
    assert intestazioni["Authorization"] == "Bearer chiave" and "merge-duplicates" in intestazioni["Prefer"]


def test_cliente_supabase_errore(monkeypatch):
    class Risposta:
        status_code, text = 401, "chiave sbagliata"

    monkeypatch.setattr(es.requests, "post", lambda *a, **k: Risposta())
    with pytest.raises(RuntimeError, match="401"):
        es.ClienteSupabase("https://x.supabase.co", "k").invia([{"data": "2024-01-01"}])


def test_riga_di_comando(rete, monkeypatch, capsys):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setattr(sys, "argv", ["esporta_score.py"])
    assert es.main() == 2
    monkeypatch.setattr(sys, "argv", ["esporta_score.py", "--prova", "--giorni", "3", "--alpha", "0.5"])
    assert es.main() == 0
    out = capsys.readouterr().out
    assert out.startswith("Score del 2026-10-09: ") and "3 righe" in out
    righe = json.loads(out[out.index("["):])
    assert len(righe) == 3 and righe[0]["alpha"] == 0.5


def test_il_modello_non_dipende_da_streamlit():
    """L'esportazione gira su GitHub Actions senza Streamlit (requirements-export.txt)."""
    codice = (
        "import sys\n"
        "class Blocca:\n"
        "    def find_spec(self, nome, *a):\n"
        "        if nome.split('.')[0] in ('streamlit', 'altair'): raise ImportError(nome)\n"
        "sys.meta_path.insert(0, Blocca())\n"
        "import brent.fonti, brent.mercato, brent.cammino, brent.meteo, brent.modelli, brent.rialzo\n"
        "import brent.oscillazione, brent.score, brent.pompa, esporta_score\n"
    )
    subprocess.run([sys.executable, "-c", codice], cwd=RADICE, check=True)
