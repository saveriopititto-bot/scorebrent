"""Previsione del rialzo: il prezzo salirà oltre una soglia nei prossimi `orizzonte` periodi? Regressione logistica
sui predittori della finestra mobile, provata a finestre scorrevoli contro la frequenza storica dei rialzi."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .cammino import CamminoPiano
from .modelli import (
    FinestreScorrevoli,
    InsiemiPredittori,
    Punteggi,
    RegressioneLogistica,
)


@dataclass(frozen=True)
class MetaProvaRialzo:
    n_test: int
    pos_test: int
    n_passi: int
    primo_test: int
    ultimo_test: int
    base_rate: float
    brier_base: float
    auc_se: float


@dataclass(frozen=True)
class ProvaRialzo:
    """Risultato della prova: una riga per insieme di predittori (Brier, Skill, AUC e, se noti, gli anni vinti)."""

    tabella: pd.DataFrame
    meta: MetaProvaRialzo


class PrevisioneRialzo:
    INSIEMI = InsiemiPredittori({
        "Livello 1 (dx, dy)": ["dx", "dy"],
        "+ coseno": ["dx", "dy", "cos"],
        "+ area di Lévy": ["dx", "dy", "levy"],
        "+ oscillazione": ["dx", "dy", "sigma", "mad"],
        "+ meteo": ["dx", "dy", "meteo"],
        "+ OVX": ["dx", "dy", "ovx"],
        "+ GPR": ["dx", "dy", "gpr"],
        "Tutto": None,
    }, ["dx", "dy", "cos", "levy", "sigma", "mad", "meteo", "ovx", "gpr"])

    def __init__(self, finestra: int, orizzonte: int, soglia: float = 0.0, passo: int = 21,
                 inizio_frac: float = 0.4, lam: float = 1.0):
        self.finestra, self.orizzonte, self.soglia, self.lam = finestra, orizzonte, soglia, lam
        self.finestre = FinestreScorrevoli(orizzonte, passo, inizio_frac)

    def features(self, x, y, meteo=None, ovx=None, gpr=None) -> pd.DataFrame:
        """Per ogni istante t (fine finestra): incrementi grezzi dx, dy sulla finestra, coseno (correlazione degli
        incrementi = parte simmetrica), area di Lévy normalizzata (parte antisimmetrica) e oscillazione degli
        incrementi di x: `sigma` = ln(deviazione standard) e `mad` = ln(deviazione assoluta mediana dalla mediana),
        meno sensibile ai salti isolati. In scala logaritmica perche' la volatilita' e' asimmetrica (molti periodi
        calmi, pochi molto agitati). `fwd` = x[t+orizzonte] - x[t].

        Con `meteo` (anomalia di temperatura allineata a x) aggiunge la colonna `meteo`, media dell'anomalia sugli
        ultimi w bin; le righe con meno di meta' dei valori meteo disponibili sono scartate, cosi' tutti gli insiemi
        di predittori vengono confrontati sugli stessi casi.

        Con `ovx` (ln della volatilita' attesa per bin, allineata a x) aggiunge la colonna `ovx` con il valore
        all'istante t; le righe senza OVX sono scartate. `gpr` (ln del rischio geopolitico, allineato a x) funziona
        allo stesso modo."""
        w, h = self.finestra, self.orizzonte
        cammino = CamminoPiano(x, y)
        x = cammino.x
        m = None if meteo is None else np.asarray(meteo, float)
        o = None if ovx is None else np.asarray(ovx, float)
        g = None if gpr is None else np.asarray(gpr, float)
        rows = []
        for t in range(w, len(x) - h):
            f = cammino.finestra(t, w)
            dx, dy = f.incrementi
            sx, sy = dx.std(ddof=1), dy.std(ddof=1)
            if sx == 0 or sy == 0:
                continue
            mad = float(np.median(np.abs(dx - np.median(dx))))
            riga = (t, f.x[-1] - f.x[0], f.y[-1] - f.y[0], float(np.corrcoef(dx, dy)[0, 1]),
                    f.area_levy() / (w * sx * sy), np.log(sx), np.log(max(mad, 1e-4 * sx)),
                    x[t + h] - x[t])
            if m is not None:
                ms = m[t - w + 1 : t + 1]
                if np.isfinite(ms).sum() < w / 2:
                    continue
                riga += (float(np.nanmean(ms)),)
            if o is not None:
                if not np.isfinite(o[t]):
                    continue
                riga += (float(o[t]),)
            if g is not None:
                if not np.isfinite(g[t]):
                    continue
                riga += (float(g[t]),)
            rows.append(riga)
        cols = (["t", "dx", "dy", "cos", "levy", "sigma", "mad", "fwd"] + ([] if m is None else ["meteo"])
                + ([] if o is None else ["ovx"]) + ([] if g is None else ["gpr"]))
        return pd.DataFrame(rows, columns=cols)

    def valida(self, feat: pd.DataFrame, anni=None) -> ProvaRialzo:
        """La baseline e' la frequenza dei rialzi nel training di ogni blocco; skill = 1 - Brier_modello /
        Brier_baseline su tutte le previsioni. Con `anni` (anno di ogni riga di `feat`) la tabella conta anche in
        quanti anni il modello batte la baseline."""
        f = feat.reset_index(drop=True)
        n = len(f)
        if n < 100:
            raise ValueError(f"Troppo pochi dati per la prova ({n} casi utili, ne servono almeno 100).")
        ybin = (f.fwd > self.soglia).astype(float).values
        if ybin.min() == ybin.max():
            raise ValueError("Il prezzo sale sempre (o non sale mai) oltre la soglia: cambia soglia o orizzonte.")
        insiemi = self.INSIEMI.risolvi(f)
        p0 = np.full(n, np.nan)
        prev = {nome: np.full(n, np.nan) for nome in insiemi}
        n_passi = 0
        for a, b, tr in self.finestre.blocchi(f.t.values):
            ytr = ybin[tr]
            n_passi += 1
            p0[a:b] = ytr.mean()
            for nome, cols in insiemi.items():
                if ytr.min() == ytr.max():
                    prev[nome][a:b] = ytr.mean()
                    continue
                modello = RegressioneLogistica(self.lam).adatta(f.loc[tr, cols].values, ytr)
                prev[nome][a:b] = modello.prevedi(f.loc[a : b - 1, cols].values)

        te = np.isfinite(p0)
        yte = ybin[te]
        if len(yte) == 0 or yte.min() == yte.max():
            raise ValueError("Nel periodo di verifica il bersaglio ha una sola classe: cambia soglia o orizzonte.")
        brier_base = Punteggi.brier(p0[te], yte)
        anni_te = None if anni is None else np.asarray(anni)[te]
        rows = []
        for nome, p in prev.items():
            br = Punteggi.brier(p[te], yte)
            riga = {"Insieme di predittori": nome, "Brier": br, "Skill": 1 - br / brier_base,
                    "AUC": Punteggi.auc(yte, p[te])}
            if anni_te is not None:
                riga["Anni vinti"], riga["Anni"] = Punteggi.anni_vinti(p[te] - yte, p0[te] - yte, anni_te)
            rows.append(riga)

        n1, n0 = float(yte.sum()), float(len(yte) - yte.sum())
        meta = MetaProvaRialzo(
            n_test=int(te.sum()), pos_test=int(n1), n_passi=n_passi,
            primo_test=int(f.t[te].iloc[0]), ultimo_test=int(f.t[te].iloc[-1]),
            base_rate=float(yte.mean()), brier_base=brier_base,
            auc_se=Punteggi.auc_errore_standard(n1, n0, self.orizzonte),
        )
        return ProvaRialzo(pd.DataFrame(rows), meta)
