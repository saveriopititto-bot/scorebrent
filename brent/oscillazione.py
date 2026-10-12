"""Previsione dell'oscillazione.

Bersaglio: oscillazione realizzata nei prossimi `orizzonte` bin, cioe' la radice della media dei quadrati degli
incrementi di x (rendimenti logaritmici). Si prevede il suo logaritmo con una regressione ridge, in stile HAR:
oscillazione su una finestra breve e una lunga, piu' l'agitazione (escursione fra massimo e minimo), che ne e' una
misura meno rumorosa, e facoltativamente la volatilita' attesa dal mercato (OVX), il meteo e il rischio
geopolitico."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .modelli import FinestreScorrevoli, InsiemiPredittori, Punteggi, RegressioneRidge


@dataclass(frozen=True)
class MetaProvaOscillazione:
    n_test: int
    n_passi: int
    primo_test: int
    ultimo_test: int


@dataclass(frozen=True)
class ProvaOscillazione:
    """Tabella per previsione (Bias, MAD, Sigma, Miglioramento e, se noti, gli anni vinti), serie con reale e
    previsioni per riga di test (in % per bin) e meta."""

    tabella: pd.DataFrame
    serie: pd.DataFrame
    meta: MetaProvaOscillazione


class PrevisioneOscillazione:
    INSIEMI = InsiemiPredittori({
        "Oscillazione recente": ["s_breve", "s_lungo", "mad"],
        "+ agitazione": ["s_breve", "s_lungo", "mad", "agit"],
        "+ agitazione e meteo": ["s_breve", "s_lungo", "mad", "agit", "meteo"],
        "+ agitazione e OVX": ["s_breve", "s_lungo", "mad", "agit", "ovx"],
        "+ agitazione e GPR": ["s_breve", "s_lungo", "mad", "agit", "gpr"],
        "Tutto": None,
    }, ["s_breve", "s_lungo", "mad", "agit", "meteo", "ovx", "gpr"])
    PAVIMENTO = 1e-6  # evita ln(0) nei periodi senza movimento
    # Riferimenti ingenui confrontati con i modelli nella prova.
    COME_PASSATO, OVX_GREZZO, MEDIA_STORICA = "Come appena passato", "OVX così com'è", "Media storica"

    def __init__(self, finestra: int, orizzonte: int, breve: int = 5, passo: int = 21, inizio_frac: float = 0.4,
                 lam: float = 1.0):
        self.finestra, self.orizzonte, self.breve, self.lam = finestra, orizzonte, min(breve, finestra), lam
        self.finestre = FinestreScorrevoli(orizzonte, passo, inizio_frac)

    @staticmethod
    def modello_predefinito(con_ovx: bool) -> str:
        """Il modello usato per le previsioni mostrate e per lo score."""
        return "+ agitazione e OVX" if con_ovx else "+ agitazione"

    def _ln_rms(self, r: np.ndarray) -> float:
        return np.log(max(np.sqrt(np.mean(r**2)), self.PAVIMENTO))

    def features(self, x, y, meteo=None, ovx=None, gpr=None) -> pd.DataFrame:
        """Una riga per ogni t >= w. Predittori (logaritmi): `s_breve` e `s_lungo` = RMS degli incrementi negli
        ultimi `breve` e w bin, `mad` = deviazione assoluta mediana sugli ultimi w; `agit` = media di y sugli ultimi
        `breve` bin; `meteo` (opzionale) = media dell'anomalia sugli ultimi w bin; `ovx` (opzionale) = ln della
        volatilita' attesa per bin all'istante t; `gpr` (opzionale) = ln del rischio geopolitico all'istante t.
        `bersaglio` = ln RMS degli incrementi nei prossimi `orizzonte` bin, NaN dove il futuro non e' ancora noto
        (servono per la previsione di oggi)."""
        w, h, breve = self.finestra, self.orizzonte, self.breve
        x, y = np.asarray(x, float), np.asarray(y, float)
        r = np.r_[np.nan, np.diff(x)]
        m = None if meteo is None else np.asarray(meteo, float)
        o = None if ovx is None else np.asarray(ovx, float)
        g = None if gpr is None else np.asarray(gpr, float)
        rows = []
        for t in range(w, len(x)):
            rl, rb = r[t - w + 1 : t + 1], r[t - breve + 1 : t + 1]
            riga = {
                "t": t,
                "s_breve": self._ln_rms(rb),
                "s_lungo": self._ln_rms(rl),
                "mad": np.log(max(float(np.median(np.abs(rl - np.median(rl)))), self.PAVIMENTO)),
                "agit": float(np.mean(y[t - breve + 1 : t + 1])),
                "bersaglio": self._ln_rms(r[t + 1 : t + h + 1]) if t + h < len(x) else np.nan,
            }
            if m is not None:
                ms = m[t - w + 1 : t + 1]
                riga["meteo"] = float(np.nanmean(ms)) if np.isfinite(ms).sum() >= w / 2 else np.nan
            if o is not None:
                riga["ovx"] = float(o[t])
            if g is not None:
                riga["gpr"] = float(g[t])
            rows.append(riga)
        return pd.DataFrame(rows)

    def _ridge(self, f: pd.DataFrame, tr: np.ndarray, cols: list[str]) -> RegressioneRidge:
        return RegressioneRidge(self.lam).adatta(f.loc[tr, cols].values, f.bersaglio.values[tr])

    def prevedi(self, feat: pd.DataFrame, cols: list[str]) -> float:
        """Oscillazione attesa (frazione per bin) dopo l'ultima riga, imparando da tutte le righe con bersaglio
        noto."""
        f = feat.dropna(subset=cols)
        tr = f[f.bersaglio.notna()]
        if len(tr) < 30:
            raise ValueError("Troppo pochi dati per prevedere l'oscillazione.")
        modello = RegressioneRidge(self.lam).adatta(tr[cols].values, tr.bersaglio.values)
        return float(modello.prevedi_esponenziale(f[cols].values[-1:])[0])

    def scorrevole(self, feat: pd.DataFrame, cols: list[str]) -> pd.Series:
        """Oscillazione attesa (frazione per bin) per ogni riga di `feat`, comprese le ultime senza bersaglio, senza
        mai usare il futuro: a blocchi il modello si riaddestra sui soli casi gia' conclusi prima dell'inizio del
        blocco. Il primo `inizio_frac` resta NaN. Indice = t."""
        f = feat.dropna(subset=cols).reset_index(drop=True)
        out = np.full(len(f), np.nan)
        for a, b, tr in self.finestre.blocchi(f.t.values, f.bersaglio.notna().values):
            out[a:b] = self._ridge(f, tr, cols).prevedi_esponenziale(f.loc[a : b - 1, cols].values)
        return pd.Series(out, index=f.t.values)

    def valida(self, feat: pd.DataFrame, anni=None) -> ProvaOscillazione:
        """Prova a finestre scorrevoli. Riferimenti ingenui: «come appena passato» (prevede l'oscillazione degli
        ultimi w bin, s_lungo), «media storica» (media del bersaglio nel training) e, se c'e' la colonna `ovx`,
        «OVX cosi' com'e'» (la volatilita' attesa dal mercato, senza alcun adattamento). Gli errori sono in punti
        percentuali di oscillazione per bin: bias = errore medio (positivo = sovrastima), MAD = errore assoluto
        medio, sigma = deviazione standard dell'errore. Il miglioramento e gli anni vinti sono misurati contro
        «come appena passato», il riferimento piu' difficile. `anni` = anno di ogni t."""
        f = feat.dropna(subset=["bersaglio", *self.INSIEMI.presenti(feat.columns)]).reset_index(drop=True)
        n = len(f)
        if n < 100:
            raise ValueError(f"Troppo pochi dati per la prova ({n} casi utili, ne servono almeno 100).")
        insiemi = self.INSIEMI.risolvi(f)
        prev = {nome: np.full(n, np.nan) for nome in insiemi}
        prev[self.COME_PASSATO] = np.exp(f.s_lungo.values)
        if "ovx" in f.columns:
            prev[self.OVX_GREZZO] = np.exp(f.ovx.values)
        prev[self.MEDIA_STORICA] = np.full(n, np.nan)
        te = np.zeros(n, bool)
        n_passi = 0
        for a, b, tr in self.finestre.blocchi(f.t.values):
            n_passi += 1
            te[a:b] = True
            ytr = f.bersaglio.values[tr]
            prev[self.MEDIA_STORICA][a:b] = np.exp(ytr.mean() + ytr.var() / 2)
            for nome, cols in insiemi.items():
                prev[nome][a:b] = self._ridge(f, tr, cols).prevedi_esponenziale(f.loc[a : b - 1, cols].values)
        if not te.any():
            raise ValueError("Troppo pochi dati per la prova.")

        reale = 100 * np.exp(f.bersaglio.values[te])
        prev = {nome: 100 * p[te] for nome, p in prev.items()}
        e_rif = prev[self.COME_PASSATO] - reale
        mse_rif = np.mean(e_rif**2)
        anni_te = None if anni is None else np.asarray(anni)[f.t.values[te]]
        rows = []
        for nome, p in prev.items():
            e = p - reale
            riga = {"Previsione": nome, "Bias": float(e.mean()), "MAD": float(np.abs(e).mean()),
                    "Sigma": float(e.std()), "Miglioramento": float(1 - np.mean(e**2) / mse_rif)}
            if anni_te is not None:
                riga["Anni vinti"], riga["Anni"] = Punteggi.anni_vinti(e, e_rif, anni_te)
            rows.append(riga)
        serie = pd.DataFrame({"t": f.t.values[te], "Reale": reale, **prev})
        meta = MetaProvaOscillazione(n_test=int(te.sum()), n_passi=n_passi, primo_test=int(f.t.values[te][0]),
                                     ultimo_test=int(f.t.values[te][-1]))
        return ProvaOscillazione(pd.DataFrame(rows), serie, meta)
