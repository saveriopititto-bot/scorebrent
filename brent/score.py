"""Score di rifornimento (adattamento dello SCORE 4.0)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import numpy as np
import pandas as pd

from .mercato import PrezziBrent
from .oscillazione import PrevisioneOscillazione


class Esito(IntEnum):
    """I tre valori dello score."""

    RIFORNISCI = 1
    NEUTRO = 0
    ASPETTA = -1

    @property
    def codice(self) -> str:
        return {1: "+1", 0: "0", -1: "-1"}[self.value]

    @property
    def etichetta(self) -> str:
        return {1: "+1 rifornisci", 0: "0 neutro", -1: "−1 aspetta"}[self.value]


@dataclass(frozen=True)
class StoricoScore:
    """Score di ogni giorno (colonne prezzo, media, scarto, sigma, stabilita, S, classe) e nome del modello usato
    per l'oscillazione attesa."""

    tabella: pd.DataFrame
    modello: str

    @property
    def oggi(self) -> pd.Series:
        return self.tabella.iloc[-1]


@dataclass(frozen=True)
class ScoreRifornimento:
    """Score a tre valori, logica «la pompa segue il Brent con ritardo».

        S = ln(P_t / media_30) / (sigma * sqrt(orizzonte)) * exp(-alpha * max(0, sigma/sigma_norm - 1))

    Il primo fattore e' lo scarto del prezzo dalla media degli ultimi `giorni_media` giorni di calendario, in unita'
    dell'oscillazione attesa nei prossimi `orizzonte` giorni (come la normalizzazione dello SCORE 4.0). Il secondo e'
    la stabilita', in (0, 1]: vale 1 con mercato calmo e smorza il segnale quando l'oscillazione attesa supera quella
    normale.

    Classe: +1 (rifornisci: Brent sopra la media, la pompa salira') se S >= soglia, -1 (aspetta: Brent sotto la
    media, la pompa scendera') se S <= -soglia, 0 altrimenti."""

    alpha: float = 1.0
    soglia: float = 1.0
    orizzonte: int = 5
    finestra: int = 20
    giorni_media: int = 30

    def calcola(self, prezzo: pd.Series, sigma: pd.Series, sigma_norm: pd.Series) -> pd.DataFrame:
        """Tutte le serie hanno indice di date."""
        media = prezzo.rolling(f"{self.giorni_media}D", min_periods=max(5, self.giorni_media // 2)).mean()
        scarto = np.log(prezzo / media)
        stab = np.exp(-self.alpha * np.maximum(0.0, sigma / sigma_norm - 1))
        s = scarto / (sigma * np.sqrt(self.orizzonte)) * stab
        classe = pd.Series(np.select([s >= self.soglia, s <= -self.soglia], [1, -1], 0), index=prezzo.index
                           ).where(s.notna())
        return pd.DataFrame({"prezzo": prezzo, "media": media, "scarto": scarto, "sigma": sigma,
                             "stabilita": stab, "S": s, "classe": classe})

    def storico(self, prezzi: PrezziBrent, ovx=None) -> StoricoScore:
        """Score per ogni giorno di borsa.

        L'oscillazione attesa viene dal modello «+ agitazione e OVX» (o «+ agitazione» senza `ovx`, che e' il ln
        della volatilita' attesa al giorno allineato ai prezzi), calcolato giorno per giorno sugli ultimi `finestra`
        giorni. Per i giorni passati e' quella della previsione scorrevole (senza usare il futuro); per l'ultimo
        giorno quella del modello addestrato su tutto lo storico. L'oscillazione normale e' la mediana di quella
        osservata fino a ciascun giorno."""
        base = prezzi.tabella
        date = base.index
        previsione = PrevisioneOscillazione(self.finestra, self.orizzonte)
        feat = previsione.features(PrezziBrent.livello(base), PrezziBrent.agitazione(base), ovx=ovx)
        modello = previsione.modello_predefinito(ovx is not None)
        cols = previsione.INSIEMI[modello]
        sig_t = previsione.scorrevole(feat, cols)
        sigma = pd.Series(sig_t.values, index=date[sig_t.index]).reindex(date)
        sigma.iloc[-1] = previsione.prevedi(feat, cols)
        norma = pd.Series(np.exp(feat["s_lungo"].values), index=date[feat["t"].values]).reindex(date).expanding().median()
        return StoricoScore(self.calcola(base["eur"], sigma, norma), modello)

    def verifica(self, score: pd.DataFrame) -> pd.DataFrame:
        """Cosa ha fatto il Brent nei `orizzonte` giorni di borsa dopo ogni classe: numero e quota di giorni,
        variazione media e quota di giorni in cui e' salito. Con la logica B ci si aspetta piu' salite dopo +1 e piu'
        discese dopo -1."""
        fwd = np.log(score.prezzo.shift(-self.orizzonte) / score.prezzo)
        d = score.assign(fwd=fwd).dropna(subset=["S", "fwd"])
        righe = []
        gruppi = [(e.codice, d.classe == e.value) for e in Esito] + [("Tutti", d.classe.notna())]
        for nome, sel in gruppi:
            x = d.fwd[sel]
            righe.append({"Classe": nome, "Giorni": int(sel.sum()), "Quota": float(sel.mean()),
                          "Variazione media": float(100 * x.mean()) if len(x) else np.nan,
                          "Giorni in salita": float((x > 0).mean()) if len(x) else np.nan})
        return pd.DataFrame(righe)
