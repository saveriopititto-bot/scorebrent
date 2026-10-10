"""Calcola lo score di rifornimento e lo scrive nella tabella `brent_score` di Supabase, per FuelMode.

Usa gli stessi dati e la stessa funzione dell'app (dati.py e brent_math.score_storico), quindi il valore
in Supabase coincide con quello della scheda «Score rifornimento» con gli stessi α e θ.

Variabili d'ambiente (non servono con --prova):
    SUPABASE_URL                 indirizzo del progetto, es. https://abcdefgh.supabase.co
    SUPABASE_SERVICE_ROLE_KEY    chiave service_role del progetto (solo lato server: non va mai nell'app)

Esempi:
    python esporta_score.py --prova              # calcola e stampa le righe senza inviarle
    python esporta_score.py                      # invia gli ultimi 5 giorni (aggiorna quelli già presenti)
    python esporta_score.py --giorni 0           # invia tutto lo storico disponibile
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import requests

import brent_math as bm
import dati

TABELLA = "brent_score"
FINESTRA, ORIZZONTE = 20, 5   # come la scheda «Score rifornimento»


def calcola(alpha: float, theta: float) -> tuple[pd.DataFrame, str]:
    """Scarica i dati e calcola lo score di ogni giorno. Senza OVX usa il modello «+ agitazione»."""
    base = dati.costruisci_base(dati.scarica_yahoo(dati.BRENT), dati.scarica_yahoo(dati.EURUSD))
    try:
        ovx = dati.ovx_giornaliero(dati.scarica_yahoo(dati.OVX)["Close"], base.index)
    except Exception as e:  # l'OVX è facoltativo, come nell'app
        print(f"OVX non disponibile, continuo senza: {e}", file=sys.stderr)
        ovx = None
    return bm.score_storico(base, ovx, alpha, theta, FINESTRA, ORIZZONTE)


def righe(sc: pd.DataFrame, modello: str, alpha: float, theta: float, giorni: int) -> list[dict]:
    """Righe da scrivere: gli ultimi `giorni` giorni di borsa con uno score (0 = tutti)."""
    d = sc.dropna(subset=["S", "classe"])
    if giorni > 0:
        d = d.iloc[-giorni:]
    adesso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return [
        {
            "data": f"{giorno:%Y-%m-%d}",
            "esito": int(r.classe),
            "score": round(float(r.S), 6),
            "brent_eur": round(float(r.prezzo), 4),
            "media_30_eur": round(float(r.media), 4),
            "scarto": round(float(r.scarto), 6),
            "oscillazione_5g": round(float(r.sigma) * ORIZZONTE ** 0.5, 6),
            "stabilita": round(float(r.stabilita), 6),
            "alpha": alpha,
            "theta": theta,
            "modello": modello,
            "aggiornato_il": adesso,
        }
        for giorno, r in d.iterrows()
    ]


def invia(dati_righe: list[dict], url: str, chiave: str, blocco: int = 500) -> None:
    """Inserisce o aggiorna le righe (chiave: data) con l'API REST di Supabase."""
    indirizzo = f"{url.rstrip('/')}/rest/v1/{TABELLA}?on_conflict=data"
    intestazioni = {
        "apikey": chiave,
        "Authorization": f"Bearer {chiave}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    for i in range(0, len(dati_righe), blocco):
        r = requests.post(indirizzo, headers=intestazioni, json=dati_righe[i : i + blocco], timeout=60)
        if r.status_code >= 300:
            raise RuntimeError(f"Supabase ha risposto {r.status_code}: {r.text[:500]}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--giorni", type=int, default=5, help="ultimi giorni da inviare; 0 = tutto lo storico (default 5)")
    p.add_argument("--alpha", type=float, default=1.0, help="sensibilità alla turbolenza α (default 1)")
    p.add_argument("--theta", type=float, default=1.0, help="soglia θ (default 1)")
    p.add_argument("--prova", action="store_true", help="calcola e stampa le righe senza inviarle")
    a = p.parse_args()

    url, chiave = os.environ.get("SUPABASE_URL", ""), os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not a.prova and not (url and chiave):
        print("Mancano SUPABASE_URL e/o SUPABASE_SERVICE_ROLE_KEY (oppure usa --prova).", file=sys.stderr)
        return 2

    sc, modello = calcola(a.alpha, a.theta)
    da_inviare = righe(sc, modello, a.alpha, a.theta, a.giorni)
    if not da_inviare:
        print("Nessuno score da inviare.", file=sys.stderr)
        return 1
    ultima = da_inviare[-1]
    esito = {1: "+1 rifornisci", 0: "0 neutro", -1: "-1 aspetta"}[ultima["esito"]]
    print(f"Score del {ultima['data']}: {esito}, S = {ultima['score']:+.3f} ({modello}); "
          f"{len(da_inviare)} righe.")
    if a.prova:
        print(json.dumps(da_inviare[-3:], indent=2, ensure_ascii=False))
        return 0
    invia(da_inviare, url, chiave)
    print(f"Scritte in Supabase, tabella {TABELLA}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
