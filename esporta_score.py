"""Calcola lo score di rifornimento e lo scrive nella tabella `brent_score` di Supabase, per FuelMode.

Usa gli stessi dati e lo stesso calcolo dell'app (brent.fonti e brent.score.ScoreRifornimento), quindi il valore
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

import requests

from brent.fonti import FonteYahoo
from brent.mercato import Ovx, PrezziBrent
from brent.score import Esito, ScoreRifornimento, StoricoScore


class EsportazioneScore:
    """Score di ogni giorno di borsa, con finestra di 20 giorni e orizzonte di 5 come la scheda «Score
    rifornimento», trasformato nelle righe della tabella."""

    def __init__(self, alpha: float = 1.0, theta: float = 1.0, fonte: FonteYahoo | None = None):
        self.score = ScoreRifornimento(alpha, theta)
        self.fonte = FonteYahoo() if fonte is None else fonte

    def calcola(self) -> StoricoScore:
        """Scarica i dati e calcola lo score di ogni giorno. Senza OVX usa il modello «+ agitazione»."""
        prezzi = PrezziBrent.scarica(self.fonte)
        try:
            ovx = Ovx.giornaliero(self.fonte.scarica(FonteYahoo.OVX)["Close"], prezzi.date)
        except Exception as e:  # l'OVX è facoltativo, come nell'app
            print(f"OVX non disponibile, continuo senza: {e}", file=sys.stderr)
            ovx = None
        return self.score.storico(prezzi, ovx)

    def righe(self, storico: StoricoScore, giorni: int) -> list[dict]:
        """Righe da scrivere: gli ultimi `giorni` giorni di borsa con uno score (0 = tutti)."""
        d = storico.tabella.dropna(subset=["S", "classe"])
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
                "oscillazione_5g": round(float(r.sigma) * self.score.orizzonte ** 0.5, 6),
                "stabilita": round(float(r.stabilita), 6),
                "alpha": self.score.alpha,
                "theta": self.score.soglia,
                "modello": storico.modello,
                "aggiornato_il": adesso,
            }
            for giorno, r in d.iterrows()
        ]


class ClienteSupabase:
    """Scrittura nella tabella dello score con l'API REST di Supabase."""

    TABELLA = "brent_score"

    def __init__(self, url: str, chiave: str):
        self.url, self.chiave = url, chiave

    def invia(self, righe: list[dict], blocco: int = 500) -> None:
        """Inserisce o aggiorna le righe (chiave: data)."""
        indirizzo = f"{self.url.rstrip('/')}/rest/v1/{self.TABELLA}?on_conflict=data"
        intestazioni = {
            "apikey": self.chiave,
            "Authorization": f"Bearer {self.chiave}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }
        for i in range(0, len(righe), blocco):
            r = requests.post(indirizzo, headers=intestazioni, json=righe[i : i + blocco], timeout=60)
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

    esportazione = EsportazioneScore(a.alpha, a.theta)
    storico = esportazione.calcola()
    da_inviare = esportazione.righe(storico, a.giorni)
    if not da_inviare:
        print("Nessuno score da inviare.", file=sys.stderr)
        return 1
    ultima = da_inviare[-1]
    esito = Esito(ultima["esito"]).etichetta.replace("−", "-")
    print(f"Score del {ultima['data']}: {esito}, S = {ultima['score']:+.3f} ({storico.modello}); "
          f"{len(da_inviare)} righe.")
    if a.prova:
        print(json.dumps(da_inviare[-3:], indent=2, ensure_ascii=False))
        return 0
    ClienteSupabase(url, chiave).invia(da_inviare)
    print(f"Scritte in Supabase, tabella {ClienteSupabase.TABELLA}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
