"""Mattoni comuni dei modelli: insiemi di predittori, standardizzazione, regressione logistica e ridge, prova a
finestre scorrevoli (§3.6 del paper) e punteggi."""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np
import pandas as pd


class InsiemiPredittori:
    """Gruppi di predittori da confrontare, per nome. Un gruppo None vuol dire «tutti i predittori presenti»."""

    def __init__(self, insiemi: dict[str, list[str] | None], predittori: list[str]):
        self.insiemi = insiemi
        self.predittori = predittori

    def __getitem__(self, nome: str) -> list[str]:
        cols = self.insiemi[nome]
        return list(self.predittori) if cols is None else cols

    def __contains__(self, nome) -> bool:
        return nome in self.insiemi

    def __iter__(self):
        return iter(self.insiemi)

    def presenti(self, colonne) -> list[str]:
        return [c for c in self.predittori if c in colonne]

    def risolvi(self, f: pd.DataFrame) -> dict[str, list[str]]:
        """Insiemi utilizzabili con le colonne di `f`; None diventa «tutti i predittori presenti»."""
        out = {}
        for nome, cols in self.insiemi.items():
            cols = self.presenti(f.columns) if cols is None else cols
            if set(cols) <= set(f.columns):
                out[nome] = cols
        return out


@dataclass(frozen=True)
class Standardizzatore:
    """(X - media) / deviazione standard, con le statistiche del solo addestramento; colonne costanti divise per 1."""

    mu: np.ndarray
    sd: np.ndarray

    @classmethod
    def adatta(cls, X: np.ndarray) -> Standardizzatore:
        mu, sd = X.mean(0), X.std(0)
        sd[sd == 0] = 1.0
        return cls(mu, sd)

    def trasforma(self, X: np.ndarray) -> np.ndarray:
        return (X - self.mu) / self.sd


def _con_intercetta(Z: np.ndarray) -> np.ndarray:
    return np.c_[np.ones(len(Z)), Z]


def _penalita(lam: float, k: int) -> np.ndarray:
    """lam * I, senza penalità sull'intercetta."""
    R = lam * np.eye(k)
    R[0, 0] = 0.0
    return R


class RegressioneLogistica:
    """Regressione logistica con penalita' ridge (intercetta esclusa), stimata con IRLS su predittori
    standardizzati."""

    def __init__(self, lam: float = 1.0, iterazioni: int = 100, tolleranza: float = 1e-8):
        self.lam, self.iterazioni, self.tolleranza = lam, iterazioni, tolleranza
        self.scala: Standardizzatore | None = None
        self.beta: np.ndarray | None = None

    @staticmethod
    def sigmoide(z):
        return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))

    def adatta(self, X: np.ndarray, y: np.ndarray) -> RegressioneLogistica:
        self.scala = Standardizzatore.adatta(X)
        Xb = _con_intercetta(self.scala.trasforma(X))
        beta = np.zeros(Xb.shape[1])
        R = _penalita(self.lam, Xb.shape[1])
        for _ in range(self.iterazioni):
            p = self.sigmoide(Xb @ beta)
            W = p * (1 - p) + 1e-9
            g = Xb.T @ (y - p) - R @ beta
            H = Xb.T @ (Xb * W[:, None]) + R
            step = np.linalg.solve(H, g)
            beta += step
            if np.max(np.abs(step)) < self.tolleranza:
                break
        self.beta = beta
        return self

    def prevedi(self, X: np.ndarray) -> np.ndarray:
        """Probabilità che il bersaglio valga 1."""
        return self.sigmoide(_con_intercetta(self.scala.trasforma(X)) @ self.beta)


class RegressioneRidge:
    """Ridge su predittori standardizzati (intercetta non penalizzata). Conserva la varianza dei residui, che serve
    a tornare dalla scala logaritmica (`prevedi_esponenziale`)."""

    def __init__(self, lam: float = 1.0):
        self.lam = lam
        self.scala: Standardizzatore | None = None
        self.beta: np.ndarray | None = None
        self.var_residui = float("nan")

    def adatta(self, X: np.ndarray, y: np.ndarray) -> RegressioneRidge:
        self.scala = Standardizzatore.adatta(X)
        Z = _con_intercetta(self.scala.trasforma(X))
        self.beta = np.linalg.solve(Z.T @ Z + _penalita(self.lam, Z.shape[1]), Z.T @ y)
        self.var_residui = float(np.var(y - Z @ self.beta))
        return self

    def prevedi(self, X: np.ndarray) -> np.ndarray:
        return _con_intercetta(self.scala.trasforma(X)) @ self.beta

    def prevedi_esponenziale(self, X: np.ndarray) -> np.ndarray:
        """exp della previsione con il fattore exp(var/2), che corregge la sottostima che nasce dal tornare dal
        logaritmo alla scala normale (media della lognormale)."""
        return np.exp(self.prevedi(X) + self.var_residui / 2)


@dataclass(frozen=True)
class FinestreScorrevoli:
    """Prova a finestre scorrevoli (walk-forward): il primo `inizio_frac` dei casi serve solo per imparare; poi, a
    blocchi di `passo` casi, il modello viene riaddestrato su tutto il passato e prevede il blocco successivo. Dal
    training si escludono i casi il cui bersaglio (che guarda `orizzonte` bin avanti) finisce dopo l'inizio del
    blocco, per non usare il futuro. I blocchi con meno di `minimo` casi di training sono saltati."""

    orizzonte: int
    passo: int = 21
    inizio_frac: float = 0.4
    minimo: int = 30

    def blocchi(self, t: np.ndarray, utilizzabili: np.ndarray | None = None) -> Iterator[tuple[int, int, np.ndarray]]:
        """(inizio, fine, maschera del training) per ogni blocco; `t` = istante di ogni caso, in ordine."""
        t = np.asarray(t)
        n = len(t)
        for a in range(int(n * self.inizio_frac), n, self.passo):
            b = min(a + self.passo, n)
            tr = t + self.orizzonte <= t[a]
            if utilizzabili is not None:
                tr = utilizzabili & tr
            if tr.sum() < self.minimo:
                continue
            yield a, b, tr


class Punteggi:
    """Misure di bontà delle previsioni."""

    @staticmethod
    def brier(p, y) -> float:
        return float(np.mean((p - y) ** 2))

    @staticmethod
    def auc(y, s) -> float:
        """Area sotto la curva ROC dalla statistica di Mann-Whitney."""
        y = np.asarray(y)
        n1 = float(y.sum())
        n0 = len(y) - n1
        if n1 == 0 or n0 == 0:
            return float("nan")
        r = pd.Series(s).rank().values
        return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))

    @staticmethod
    def auc_errore_standard(n1: float, n0: float, orizzonte: int) -> float:
        """Errore standard dell'AUC sotto ipotesi nulla sui casi *effettivi* (n / orizzonte), perche' i bersagli
        vicini si sovrappongono."""
        h = max(orizzonte, 1)
        n1e, n0e = max(n1 / h, 1.0), max(n0 / h, 1.0)
        return float(np.sqrt((n1e + n0e + 1) / (12 * n1e * n0e)))

    @staticmethod
    def anni_vinti(errore_modello, errore_rif, anni) -> tuple[int, int]:
        """In quanti anni l'errore quadratico medio del modello è sotto quello del riferimento (vinti, anni)."""
        vinti = [np.mean(errore_modello[anni == k] ** 2) < np.mean(errore_rif[anni == k] ** 2) for k in np.unique(anni)]
        return int(sum(vinti)), len(vinti)
