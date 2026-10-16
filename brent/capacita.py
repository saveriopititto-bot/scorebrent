"""Capacità di processo dello score: Cp e Cpk su finestre mobili e previsione della finestra successiva con una rete
neurale.

Pipeline
1. Serie S(t) = score di ogni giorno, portata nell'intervallo [LSL, USL] = [-1, 1].
2. Finestre mobili di `larghezza` giorni (5), con passo `passo` (1).
3. Per ogni finestra: media mu, deviazione standard sigma (ddof=1), Cp, Cpk e area di Lévy del cammino
   (S, dS), con dS(t) = (S(t+1) - S(t-1)) / 2 (differenza centrale).
       Cp  = (USL - LSL) / (6 sigma)
       Cpk = min(USL - mu, mu - LSL) / (3 sigma)
   sigma ha un pavimento (`sigma_min`) e Cp, Cpk un tetto (`tetto`), perché con una finestra quasi piatta
   esploderebbero.
4. Rete neurale con uno strato nascosto (tanh), addestrata con back propagation scritta in numpy:
   ingresso = indici della finestra k e k-1, bersaglio = (Cp, Cpk) della finestra k+1.
5. Prova a finestre scorrevoli (walk-forward, `FinestreScorrevoli`): il modello impara solo dal passato e prevede
   il blocco successivo; il riferimento è «domani come oggi» (Cp e Cpk della finestra k).

Con USL = 1 e LSL = -1, che coincidono con le soglie ±θ dello score quando θ = 1, Cp dice quanto lo score oscilla
rispetto alla fascia «neutro» e Cpk anche quanto è vicino a uscirne da un lato.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .cammino import CamminoPiano
from .modelli import FinestreScorrevoli, Standardizzatore


@dataclass(frozen=True)
class LimitiSpecifica:
    """Limiti di specifica e protezioni numeriche degli indici di capacità."""

    usl: float = 1.0
    lsl: float = -1.0
    sigma_min: float = 0.01  # evita Cp enormi se la finestra è quasi piatta
    tetto: float = 10.0      # tetto per Cp e Cpk

    def __post_init__(self):
        if self.usl <= self.lsl:
            raise ValueError("Serve USL > LSL.")

    def entro(self, s) -> np.ndarray:
        """La serie portata dentro [LSL, USL]."""
        return np.clip(np.asarray(s, float), self.lsl, self.usl)

    def indici(self, mu: float, sigma: float) -> tuple[float, float]:
        """(Cp, Cpk), con sigma non sotto `sigma_min` e risultati in [0, tetto]."""
        sigma = max(sigma, self.sigma_min)
        cp = (self.usl - self.lsl) / (6 * sigma)
        cpk = min(self.usl - mu, mu - self.lsl) / (3 * sigma)
        return float(np.clip(cp, 0.0, self.tetto)), float(np.clip(cpk, 0.0, self.tetto))


@dataclass(frozen=True)
class FinestreCapacita:
    """Statistiche di ogni finestra mobile: colonne mu, sigma, cp, cpk, area."""

    COLONNE = ("mu", "sigma", "cp", "cpk", "area")

    larghezza: int = 5
    passo: int = 1
    limiti: LimitiSpecifica = LimitiSpecifica()

    def __post_init__(self):
        if self.larghezza < 3:
            raise ValueError("Servono almeno 3 giorni per finestra (la differenza centrale ne consuma 2).")
        if self.passo < 1:
            raise ValueError("Il passo deve essere almeno 1.")

    @staticmethod
    def area_levy(x) -> float:
        """Area di Lévy del cammino 2D (S(t), dS(t)) con dS(t) = (S(t+1) - S(t-1)) / 2, rispetto al punto di
        partenza. È la formula di `CamminoPiano.area_levy` (eq. 6) sui punti interni della finestra."""
        x = np.asarray(x, float)
        return CamminoPiano(x[1:-1], (x[2:] - x[:-2]) / 2.0).area_levy()

    def statistiche(self, x) -> tuple[float, float, float, float, float]:
        """mu, sigma (ddof=1, non sotto `sigma_min`), Cp, Cpk e area di una finestra."""
        x = np.asarray(x, float)
        mu, sigma = float(x.mean()), max(float(x.std(ddof=1)), self.limiti.sigma_min)
        cp, cpk = self.limiti.indici(mu, sigma)
        return mu, sigma, cp, cpk, self.area_levy(x)

    def tabella(self, s: pd.Series) -> pd.DataFrame:
        """Una riga per finestra, con indice = etichetta dell'ultimo giorno della finestra. I valori mancanti di `s`
        vengono tolti e gli altri portati dentro [LSL, USL] prima di calcolare le finestre."""
        s = pd.Series(s).astype(float).dropna()
        x = self.limiti.entro(s.to_numpy())
        fine = range(self.larghezza, len(x) + 1, self.passo)
        righe = [self.statistiche(x[i - self.larghezza : i]) for i in fine]
        return pd.DataFrame(righe, index=s.index[[i - 1 for i in fine]], columns=list(self.COLONNE))


class ReteNeurale:
    """Percettrone con uno strato nascosto tanh e uscita lineare, addestrato a lotto intero con discesa del gradiente
    sull'errore quadratico medio più una penalità L2 sui pesi (non sui bias). Il gradiente è calcolato a mano con la
    back propagation."""

    def __init__(self, n_in: int, nascosti: int = 16, n_out: int = 2, seme: int = 0):
        r = np.random.default_rng(seme)
        self.W1 = r.normal(0, 0.5, (n_in, nascosti))
        self.b1 = np.zeros(nascosti)
        self.W2 = r.normal(0, 0.5, (nascosti, n_out))
        self.b2 = np.zeros(n_out)

    def _avanti(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        h = np.tanh(X @ self.W1 + self.b1)
        return h, h @ self.W2 + self.b2

    def prevedi(self, X: np.ndarray) -> np.ndarray:
        return self._avanti(X)[1]

    def perdita(self, X: np.ndarray, Y: np.ndarray, l2: float = 0.0) -> float:
        """MSE (media su casi e uscite sommate per caso) + l2/2 * (|W1|² + |W2|²): la funzione di cui `gradienti`
        dà le derivate."""
        P = self.prevedi(X)
        return float(np.sum((P - Y) ** 2) / len(X) + l2 / 2 * (np.sum(self.W1**2) + np.sum(self.W2**2)))

    def gradienti(self, X: np.ndarray, Y: np.ndarray, l2: float = 0.0) -> dict[str, np.ndarray]:
        h, P = self._avanti(X)
        dP = 2 * (P - Y) / len(X)                       # d(MSE)/dP
        dh = (dP @ self.W2.T) * (1 - h**2)              # back propagation attraverso tanh
        return {"W2": h.T @ dP + l2 * self.W2, "b2": dP.sum(0),
                "W1": X.T @ dh + l2 * self.W1, "b1": dh.sum(0)}

    def adatta(self, X: np.ndarray, Y: np.ndarray, lr: float = 0.01, epoche: int = 3000,
               l2: float = 1e-4) -> ReteNeurale:
        for _ in range(epoche):
            for nome, g in self.gradienti(X, Y, l2).items():
                getattr(self, nome)[...] -= lr * g
        return self


@dataclass(frozen=True)
class MetaProvaCapacita:
    finestre: int
    n_casi: int
    n_test: int
    n_passi: int
    quota_tagliata: float  # quota di giorni dello score fuori da [LSL, USL], portati sul limite


@dataclass(frozen=True)
class ProvaCapacita:
    """Tabella degli errori (rete e riferimento), serie con reale e previsioni per finestra di test, finestre
    mobili, riepilogo dell'area di Lévy e meta."""

    tabella: pd.DataFrame
    serie: pd.DataFrame
    finestre: pd.DataFrame
    area: AreaLevyRiepilogo
    meta: MetaProvaCapacita


@dataclass(frozen=True)
class AreaLevyRiepilogo:
    """Media dell'area di Lévy delle finestre, confrontata con quella di una passeggiata casuale.

    Il cammino (S, dS) non ha media 0 nemmeno per un moto browniano: dS dipende da S e il cammino gira in media in
    senso orario. Per 5 giorni con incrementi di varianza s² l'area attesa è -s²/2. Il riferimento è quindi la media
    dell'area sulle passeggiate casuali che hanno gli stessi incrementi della serie rimescolati (`repliche` volte),
    che conserva la loro distribuzione e toglie ogni dipendenza nel tempo. Le finestre vicine condividono quasi tutti
    i giorni, quindi l'errore standard è calcolato sulle finestre *effettive*, n * passo / larghezza: con |z| oltre 2
    la serie si muove in modo diverso da una passeggiata casuale."""

    media: float
    riferimento: float
    errore_standard: float
    sigma: float
    n: int

    @classmethod
    def da_serie(cls, x, finestre: FinestreCapacita, repliche: int = 20, seme: int = 0) -> AreaLevyRiepilogo:
        x = np.asarray(x, float)
        w, p = finestre.larghezza, finestre.passo

        def aree(y):
            return np.array([finestre.area_levy(y[i - w : i]) for i in range(w, len(y) + 1, p)])

        a = aree(x)
        if len(a) < 2:
            return cls(*(float("nan"),) * 4, len(a))
        r = np.random.default_rng(seme)
        dx = np.diff(x)
        rif = np.mean([aree(np.r_[0.0, np.cumsum(r.permutation(dx))]).mean() for _ in range(repliche)])
        sd = float(a.std(ddof=1))
        n_eff = max(len(a) * p / w, 1.0)
        return cls(float(a.mean()), float(rif), float(sd / np.sqrt(n_eff)), sd, len(a))

    @property
    def z(self) -> float:
        """Distanza dal riferimento in errori standard."""
        return (self.media - self.riferimento) / self.errore_standard if self.errore_standard > 0 else float("nan")


class PrevisioneCapacita:
    """Previsione di (Cp, Cpk) della finestra successiva da quelli delle due finestre più recenti."""

    BERSAGLI = ("cp", "cpk")
    RETE, RIFERIMENTO = "Rete neurale", "Domani come oggi"

    def __init__(self, finestre: FinestreCapacita | None = None, nascosti: int = 16, epoche: int = 3000,
                 lr: float = 0.01, l2: float = 1e-4, passo: int = 21, inizio_frac: float = 0.7, seme: int = 0):
        self.finestre = FinestreCapacita() if finestre is None else finestre
        self.nascosti, self.epoche, self.lr, self.l2, self.seme = nascosti, epoche, lr, l2, seme
        self.passo, self.inizio_frac = passo, inizio_frac

    @property
    def predittori(self) -> list[str]:
        c = FinestreCapacita.COLONNE
        return [*c, *(f"{x}_prec" for x in c)]

    def dataset(self, W: pd.DataFrame) -> pd.DataFrame:
        """Una riga per ogni finestra k con una precedente: indici di k e di k-1 (`*_prec`), `k` e bersagli
        `cp_succ`, `cpk_succ` della finestra k+1 (NaN per l'ultima, che serve per la previsione)."""
        c = list(FinestreCapacita.COLONNE)
        d = pd.concat([W[c], W[c].shift(1).add_suffix("_prec")], axis=1)
        for b in self.BERSAGLI:
            d[f"{b}_succ"] = W[b].shift(-1)
        d.insert(0, "k", np.arange(len(W)))
        return d.iloc[1:]

    def _addestra(self, X: np.ndarray, Y: np.ndarray):
        """Rete addestrata su X, Y standardizzati con le sole statistiche dell'addestramento; restituisce la funzione
        che prevede nella scala originale."""
        sx, sy = Standardizzatore.adatta(X), Standardizzatore.adatta(Y)
        rete = ReteNeurale(X.shape[1], self.nascosti, Y.shape[1], self.seme)
        rete.adatta(sx.trasforma(X), sy.trasforma(Y), self.lr, self.epoche, self.l2)
        return lambda Z: rete.prevedi(sx.trasforma(Z)) * sy.sd + sy.mu

    def valida(self, s: pd.Series) -> ProvaCapacita:
        """Prova a finestre scorrevoli sulla serie dello score: ogni `passo` finestre la rete si riaddestra su tutti
        i casi il cui bersaglio era già noto e prevede il blocco successivo. `passo` <= 0 = un solo taglio
        addestramento/prova, come nella versione a riga di comando originale."""
        s = pd.Series(s).astype(float).dropna()
        lim = self.finestre.limiti
        W = self.finestre.tabella(s)
        d = self.dataset(W).dropna().reset_index()
        d = d.rename(columns={d.columns[0]: "fine"})
        n = len(d)
        if n < 50:
            raise ValueError(f"Troppo pochi dati per la prova ({n} casi utili, ne servono almeno 50).")
        X, Y = d[self.predittori].to_numpy(), d[[f"{b}_succ" for b in self.BERSAGLI]].to_numpy()
        passo = self.passo if self.passo > 0 else n
        prove = FinestreScorrevoli(orizzonte=1, passo=passo, inizio_frac=self.inizio_frac)
        P = np.full_like(Y, np.nan)
        n_passi = 0
        for a, b, tr in prove.blocchi(d.k.to_numpy()):
            n_passi += 1
            P[a:b] = self._addestra(X[tr], Y[tr])(X[a:b])
        te = np.isfinite(P[:, 0])
        if not te.any():
            raise ValueError("Troppo pochi dati per la prova.")

        reale, prev = Y[te], {self.RETE: P[te], self.RIFERIMENTO: d.loc[te, list(self.BERSAGLI)].to_numpy()}
        mae_rif = np.abs(prev[self.RIFERIMENTO] - reale).mean(0)
        righe = []
        for nome, p in prev.items():
            e = p - reale
            mae = np.abs(e).mean(0)
            riga = {"Previsione": nome}
            for j, b in enumerate(("Cp", "Cpk")):
                riga[f"MAE {b}"] = float(mae[j])
                riga[f"Bias {b}"] = float(e[:, j].mean())
                riga[f"Miglioramento {b}"] = float(1 - mae[j] / mae_rif[j]) if mae_rif[j] > 0 else np.nan
            righe.append(riga)
        serie = pd.DataFrame({"fine": d.fine[te].to_numpy(), "Cp reale": reale[:, 0], "Cpk reale": reale[:, 1],
                              "Cp rete": prev[self.RETE][:, 0], "Cpk rete": prev[self.RETE][:, 1],
                              "Cp oggi": prev[self.RIFERIMENTO][:, 0], "Cpk oggi": prev[self.RIFERIMENTO][:, 1]})
        x = s.to_numpy()
        meta = MetaProvaCapacita(finestre=len(W), n_casi=n, n_test=int(te.sum()), n_passi=n_passi,
                                 quota_tagliata=float(np.mean((x > lim.usl) | (x < lim.lsl))))
        area = AreaLevyRiepilogo.da_serie(lim.entro(x), self.finestre)
        return ProvaCapacita(pd.DataFrame(righe), serie, W, area, meta)

    def prevedi(self, s: pd.Series) -> tuple[float, float]:
        """(Cp, Cpk) attesi per la finestra successiva all'ultima, imparando da tutti i casi con bersaglio noto."""
        d = self.dataset(self.finestre.tabella(s)).dropna(subset=self.predittori)
        tr = d.dropna()
        if len(tr) < 30:
            raise ValueError("Troppo pochi dati per prevedere Cp e Cpk.")
        Y = tr[[f"{b}_succ" for b in self.BERSAGLI]].to_numpy()
        p = self._addestra(tr[self.predittori].to_numpy(), Y)(d[self.predittori].to_numpy()[-1:])[0]
        lim = self.finestre.limiti
        cp, cpk = np.clip(p, 0.0, lim.tetto)
        return float(cp), float(min(cpk, cp))  # Cpk <= Cp per definizione
