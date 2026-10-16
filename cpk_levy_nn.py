"""Previsione di Cp e Cpk della finestra successiva a partire dallo score di ogni giorno (scorebrent).

Il calcolo è in brent/capacita.py: finestre mobili di 5 giorni con passo 1, per ognuna media, sigma, Cp, Cpk
(USL = 1, LSL = -1) e area di Lévy; una rete neurale con uno strato nascosto prevede (Cp, Cpk) della finestra k+1
da quelli delle finestre k e k-1. La prova è a finestre scorrevoli (si impara solo dal passato) e la rete è
confrontata con il riferimento «domani come oggi».

Esempi:
    python cpk_levy_nn.py --csv dati.csv --col score_gg   # serie da un file CSV
    python cpk_levy_nn.py --brent                         # score S dell'app (scarica da Yahoo Finance)
    python cpk_levy_nn.py                                 # dati sintetici di prova
    python cpk_levy_nn.py --passo 0                       # un solo taglio addestramento/prova (70% / 30%)
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from brent.capacita import FinestreCapacita, LimitiSpecifica, PrevisioneCapacita


def serie_sintetica(n: int = 600, seme: int = 1) -> pd.Series:
    """Passeggiata casuale schiacciata in (-1, 1) con tanh."""
    r = np.random.default_rng(seme)
    return pd.Series(np.tanh(np.cumsum(r.normal(0, 0.15, n)) * 0.5))


def serie_csv(percorso: str, colonna: str) -> pd.Series:
    d = pd.read_csv(percorso)
    if colonna not in d.columns:
        raise SystemExit(f"Colonna «{colonna}» non trovata in {percorso}; colonne: {', '.join(d.columns)}")
    return pd.to_numeric(d[colonna], errors="coerce")


def serie_brent(alpha: float, theta: float) -> pd.Series:
    """Score continuo S di ogni giorno di borsa, come nella scheda «Score rifornimento»."""
    from esporta_score import EsportazioneScore

    return EsportazioneScore(alpha, theta).calcola().tabella["S"]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    fonte = p.add_mutually_exclusive_group()
    fonte.add_argument("--csv", help="file CSV con la serie dello score")
    fonte.add_argument("--brent", action="store_true", help="usa lo score S calcolato dai prezzi del Brent")
    p.add_argument("--col", default="score_gg", help="colonna del CSV (default score_gg)")
    p.add_argument("--alpha", type=float, default=1.0, help="α dello score con --brent (default 1)")
    p.add_argument("--theta", type=float, default=1.0, help="θ dello score con --brent (default 1)")
    p.add_argument("--finestra", type=int, default=5, help="giorni per finestra (default 5)")
    p.add_argument("--train", type=float, default=0.7, help="quota iniziale usata solo per imparare (default 0.7)")
    p.add_argument("--passo", type=int, default=21,
                   help="finestre fra un riaddestramento e l'altro; 0 = un solo taglio (default 21)")
    p.add_argument("--nascosti", type=int, default=16, help="neuroni nello strato nascosto (default 16)")
    p.add_argument("--epoche", type=int, default=3000, help="epoche di addestramento (default 3000)")
    a = p.parse_args(argv)

    if a.csv:
        s = serie_csv(a.csv, a.col)
    elif a.brent:
        s = serie_brent(a.alpha, a.theta)
    else:
        s = serie_sintetica()

    finestre = FinestreCapacita(larghezza=a.finestra, limiti=LimitiSpecifica())
    modello = PrevisioneCapacita(finestre, nascosti=a.nascosti, epoche=a.epoche, passo=a.passo,
                                 inizio_frac=a.train)
    try:
        prova = modello.valida(s)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1

    m = prova.meta
    area = prova.area
    print(f"Giorni fuori da [-1, 1] portati sul limite: {100 * m.quota_tagliata:.1f}%")
    print(f"Area di Lévy: media {area.media:.4g} ± {area.errore_standard:.2g} (errore standard), "
          f"std {area.sigma:.4g}; passeggiata casuale con gli stessi incrementi {area.riferimento:.4g}, "
          f"z = {area.z:+.2f}")
    print(f"Finestre: {m.finestre} | casi {m.n_casi} | test {m.n_test} | riaddestramenti {m.n_passi}")
    for _, r in prova.tabella.iterrows():
        print(f"{r.Previsione:<17} MAE Cp {r['MAE Cp']:.3f}  Cpk {r['MAE Cpk']:.3f}   "
              f"bias Cp {r['Bias Cp']:+.3f}  Cpk {r['Bias Cpk']:+.3f}")
    rete = prova.tabella.iloc[0]
    print(f"Miglioramento della rete sul riferimento: Cp {100 * rete['Miglioramento Cp']:+.1f}%  "
          f"Cpk {100 * rete['Miglioramento Cpk']:+.1f}%")
    cp, cpk = modello.prevedi(s)
    print(f"Prossima finestra: Cp {cp:.3f}  Cpk {cpk:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
