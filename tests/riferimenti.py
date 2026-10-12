"""Risultati di riferimento sui dati sintetici: lo score di ogni giorno (quello che va in Supabase) e le tabelle delle
due prove. test_regressione.py controlla che il codice li riproduca.

Se un cambiamento del modello è voluto, si rigenerano con:  python -m tests.riferimenti
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from brent.mercato import Frequenza, Ovx, SerieAnalisi
from brent.oscillazione import PrevisioneOscillazione
from brent.rialzo import PrevisioneRialzo
from brent.score import ScoreRifornimento

from .conftest import ReteFinta

CARTELLA = Path(__file__).resolve().parent / "riferimenti"


def calcola(prezzi) -> dict[str, pd.DataFrame]:
    ovx_close = ReteFinta().yahoo["^OVX"]["Close"].tz_localize(None).rename_axis(None)
    ovx = Ovx.giornaliero(ovx_close, prezzi.date)
    score = ScoreRifornimento().storico(prezzi, ovx).tabella.dropna(subset=["S"])

    serie = SerieAnalisi.costruisci(prezzi, Frequenza.GIORNO, ovx_close=ovx_close)
    rialzo = PrevisioneRialzo(20, 5, soglia=0.01)
    feat = rialzo.features(serie.x, serie.y, **serie.esterni)
    tab_rialzo = rialzo.valida(feat, anni=serie.date[feat.t.to_numpy()].year).tabella

    osc = PrevisioneOscillazione(20, 5)
    tab_osc = osc.valida(osc.features(serie.x, serie.y, **serie.esterni), anni=serie.date.year).tabella
    return {"score": score.rename_axis("data").reset_index(), "rialzo": tab_rialzo, "oscillazione": tab_osc}


def main() -> None:
    from .conftest import prezzi_sintetici

    CARTELLA.mkdir(exist_ok=True)
    for nome, tab in calcola(prezzi_sintetici()).items():
        tab.to_csv(CARTELLA / f"{nome}.csv", index=False, float_format="%.12g")
        print(f"{nome}.csv: {len(tab)} righe")


if __name__ == "__main__":
    main()
