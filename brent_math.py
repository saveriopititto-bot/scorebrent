"""Matematica del paper "sisma" (analisi differenziale + firma del cammino)
adattata alla serie del Brent.

Corrispondenze con il paper
---------------------------
| paper (sismologia)                     | Brent                                      |
|----------------------------------------|--------------------------------------------|
| bin temporale (mese / 5 giorni)        | bin giornaliero o settimanale              |
| magnitudo equivalente M_eq = livello   | x_k = ln(prezzo del Brent in euro)         |
| altezza differenziale h_k = dM_eq      | h_k = x_k - x_{k-1}  (rendimento log.)     |
| canale di tasso r = log10(1 + n)       | y_k = ln(1 + range intraday in %)          |
| censura dei bin vuoti                  | non serve (ogni giorno di borsa ha prezzo) |
| bersaglio: bin successivo > mediana    | bersaglio: rialzo oltre soglia nei prossimi|
|                                        | `orizzonte` bin                            |
| (nessuno)                              | m_k = temperatura in Europa rispetto al    |
|                                        | normale stagionale (Open-Meteo), opzionale |

Convenzione di segno dell'area di Lévy (eq. 6 del paper), con cammino
(x, y) = (prezzo, attivita'): A > 0 se il cammino ruota in senso antiorario,
cioe' se il PREZZO ANTICIPA l'attivita'; A < 0 se e' l'attivita' ad anticipare
il prezzo. La convenzione e' verificata nei test su un caso con anticipo noto.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# Analisi differenziale
# --------------------------------------------------------------------------
def altezze(livello) -> np.ndarray:
    """h_k = y_k - y_{k-1} (eq. 3)."""
    return np.diff(np.asarray(livello, float))


def aggregati(h) -> dict:
    """Statistiche sulle altezze: le non lineari sono sensibili al percorso,
    `net` e' telescopica (eq. 4) e vale y_K - y_0."""
    h = np.asarray(h, float)
    if h.size == 0:
        return {k: np.nan for k in
                ("net", "variazione_totale", "parte_positiva", "parte_negativa", "rms", "salto_max", "salto_min")}
    return {
        "net": float(h.sum()),
        "variazione_totale": float(np.abs(h).sum()),
        "parte_positiva": float(h[h > 0].sum()),
        "parte_negativa": float(h[h < 0].sum()),
        "rms": float(np.sqrt(np.mean(h**2))),
        "salto_max": float(h.max()),
        "salto_min": float(h.min()),
    }


def efficienza_percorso(h) -> float:
    """|net| / variazione totale, in [0, 1]. 1 = percorso rettilineo,
    vicino a 0 = molto movimento ma poca strada netta."""
    a = aggregati(h)
    tv = a["variazione_totale"]
    return float(abs(a["net"]) / tv) if tv and tv > 0 else float("nan")


# --------------------------------------------------------------------------
# Area di Lévy
# --------------------------------------------------------------------------
def area_levy(x, y) -> float:
    """A = 1/2 * sum_k [(x_k - x_0) dy_k - (y_k - y_0) dx_k]  (eq. 6).

    Esatta per un cammino poligonale. Invariante per traslazione, cambia segno
    scambiando i canali, nulla se un canale e' funzione affine dell'altro."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if x.size < 2:
        return 0.0
    dx, dy = np.diff(x), np.diff(y)
    return 0.5 * float(np.sum((x[:-1] - x[0]) * dy - (y[:-1] - y[0]) * dx))


def area_levy_mobile(x, y, w: int) -> np.ndarray:
    """Area di Lévy su finestra scorrevole di w bin, normalizzata come il
    coefficiente di Pearson: A / (w * sd(dx) * sd(dy)). NaN dove non definita."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    out = np.full(len(x), np.nan)
    for t in range(w, len(x)):
        xs, ys = x[t - w : t + 1], y[t - w : t + 1]
        sx, sy = np.diff(xs).std(ddof=1), np.diff(ys).std(ddof=1)
        if sx > 0 and sy > 0:
            out[t] = area_levy(xs, ys) / (w * sx * sy)
    return out


# --------------------------------------------------------------------------
# Meteo
# --------------------------------------------------------------------------
def anomalia_stagionale(temp: pd.Series, smussamento: int = 31) -> pd.Series:
    """Temperatura giornaliera meno il suo normale stagionale.

    Il normale e' la media, su tutti gli anni disponibili, dello stesso giorno
    dell'anno, smussata con una media mobile circolare di `smussamento` giorni
    (il 29 febbraio conta come 28). Positivo = piu' caldo del normale."""
    temp = temp.dropna()
    if temp.empty:
        return temp
    doy = np.minimum(temp.index.dayofyear - ((temp.index.is_leap_year) & (temp.index.dayofyear > 59)), 365)
    clima = temp.groupby(doy).mean().reindex(range(1, 366)).interpolate(limit_direction="both")
    k = smussamento // 2
    giro = pd.concat([clima.iloc[-k:], clima, clima.iloc[:k]])
    clima = giro.rolling(smussamento, center=True, min_periods=1).mean().iloc[k : k + 365]
    return temp - clima.to_numpy()[doy - 1]


# --------------------------------------------------------------------------
# Validazione fuori campione (§3.6 del paper)
# --------------------------------------------------------------------------
INSIEMI = {
    "Livello 1 (dx, dy)": ["dx", "dy"],
    "+ coseno": ["dx", "dy", "cos"],
    "+ area di Lévy": ["dx", "dy", "levy"],
    "+ oscillazione": ["dx", "dy", "sigma", "mad"],
    "Tutto": ["dx", "dy", "cos", "levy", "sigma", "mad"],
    "+ meteo": ["dx", "dy", "meteo"],
    "Tutto + meteo": ["dx", "dy", "cos", "levy", "sigma", "mad", "meteo"],
}


def costruisci_features(x, y, w: int, orizzonte: int, meteo=None) -> pd.DataFrame:
    """Per ogni istante t (fine finestra): incrementi grezzi dx, dy sulla
    finestra, coseno (correlazione degli incrementi = parte simmetrica), area
    di Lévy normalizzata (parte antisimmetrica) e oscillazione degli incrementi
    di x: `sigma` = ln(deviazione standard) e `mad` = ln(deviazione assoluta
    mediana dalla mediana), meno sensibile ai salti isolati. In scala
    logaritmica perche' la volatilita' e' asimmetrica (molti periodi calmi,
    pochi molto agitati). `fwd` = x[t+orizzonte] - x[t].

    Con `meteo` (anomalia di temperatura allineata a x) aggiunge la colonna
    `meteo`, media dell'anomalia sugli ultimi w bin; le righe con meno di meta'
    dei valori meteo disponibili sono scartate, cosi' tutti gli insiemi di
    predittori vengono confrontati sugli stessi casi."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = None if meteo is None else np.asarray(meteo, float)
    rows = []
    for t in range(w, len(x) - orizzonte):
        xs, ys = x[t - w : t + 1], y[t - w : t + 1]
        dx, dy = np.diff(xs), np.diff(ys)
        sx, sy = dx.std(ddof=1), dy.std(ddof=1)
        if sx == 0 or sy == 0:
            continue
        mad = float(np.median(np.abs(dx - np.median(dx))))
        riga = (t, xs[-1] - xs[0], ys[-1] - ys[0], float(np.corrcoef(dx, dy)[0, 1]),
                area_levy(xs, ys) / (w * sx * sy), np.log(sx), np.log(max(mad, 1e-4 * sx)),
                x[t + orizzonte] - x[t])
        if m is not None:
            ms = m[t - w + 1 : t + 1]
            if np.isfinite(ms).sum() < w / 2:
                continue
            riga += (float(np.nanmean(ms)),)
        rows.append(riga)
    cols = ["t", "dx", "dy", "cos", "levy", "sigma", "mad", "fwd"] + ([] if m is None else ["meteo"])
    return pd.DataFrame(rows, columns=cols)


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def _fit_logistica(X, y, lam=1.0, iters=100):
    """Regressione logistica con penalita' ridge (intercetta esclusa), IRLS."""
    Xb = np.c_[np.ones(len(X)), X]
    beta = np.zeros(Xb.shape[1])
    R = lam * np.eye(Xb.shape[1])
    R[0, 0] = 0.0
    for _ in range(iters):
        p = _sigmoid(Xb @ beta)
        W = p * (1 - p) + 1e-9
        g = Xb.T @ (y - p) - R @ beta
        H = Xb.T @ (Xb * W[:, None]) + R
        step = np.linalg.solve(H, g)
        beta += step
        if np.max(np.abs(step)) < 1e-8:
            break
    return beta


def _predici(beta, X):
    return _sigmoid(np.c_[np.ones(len(X)), X] @ beta)


def auc(y, s) -> float:
    y = np.asarray(y)
    n1 = float(y.sum())
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = pd.Series(s).rank().values
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def validazione(feat: pd.DataFrame, orizzonte: int, soglia: float = 0.0, passo: int = 21,
                inizio_frac: float = 0.4, lam: float = 1.0, anni=None):
    """Prova a finestre scorrevoli (walk-forward): il primo `inizio_frac` dei
    casi serve solo per imparare; poi, a blocchi di `passo` casi, il modello
    viene riaddestrato su tutto il passato e prevede il blocco successivo.
    Dal training si escludono i casi il cui bersaglio (che guarda `orizzonte`
    bin avanti) finisce dopo l'inizio del blocco, per non usare il futuro.

    La baseline e' la frequenza dei rialzi nel training di ogni blocco;
    skill = 1 - Brier_modello / Brier_baseline su tutte le previsioni.

    Restituisce (tabella per insieme di predittori, meta). Con `anni` (anno di
    ogni riga di `feat`) la tabella conta anche in quanti anni il modello batte
    la baseline. `auc_se` e' l'errore standard dell'AUC sotto ipotesi nulla sui
    casi *effettivi* (n / orizzonte), perche' i bersagli vicini si sovrappongono."""
    f = feat.reset_index(drop=True)
    n = len(f)
    if n < 100:
        raise ValueError(f"Troppo pochi dati per la prova ({n} casi utili, ne servono almeno 100).")
    ybin = (f.fwd > soglia).astype(float).values
    if ybin.min() == ybin.max():
        raise ValueError("Il prezzo sale sempre (o non sale mai) oltre la soglia: cambia soglia o orizzonte.")
    insiemi = {nome: cols for nome, cols in INSIEMI.items() if set(cols) <= set(f.columns)}
    p0 = np.full(n, np.nan)
    prev = {nome: np.full(n, np.nan) for nome in insiemi}
    n_passi = 0
    for a in range(int(n * inizio_frac), n, passo):
        b = min(a + passo, n)
        tr = (f.t + orizzonte <= f.t.iloc[a]).values
        ytr = ybin[tr]
        if len(ytr) < 30:
            continue
        n_passi += 1
        p0[a:b] = ytr.mean()
        for nome, cols in insiemi.items():
            if ytr.min() == ytr.max():
                prev[nome][a:b] = ytr.mean()
                continue
            Xtr, Xte = f.loc[tr, cols].values, f.loc[a : b - 1, cols].values
            mu, sd = Xtr.mean(0), Xtr.std(0)
            sd[sd == 0] = 1.0
            prev[nome][a:b] = _predici(_fit_logistica((Xtr - mu) / sd, ytr, lam), (Xte - mu) / sd)

    te = np.isfinite(p0)
    yte = ybin[te]
    if len(yte) == 0 or yte.min() == yte.max():
        raise ValueError("Nel periodo di verifica il bersaglio ha una sola classe: cambia soglia o orizzonte.")
    brier_base = float(np.mean((p0[te] - yte) ** 2))
    anni_te = None if anni is None else np.asarray(anni)[te]
    rows = []
    for nome, p in prev.items():
        br = float(np.mean((p[te] - yte) ** 2))
        riga = {"Insieme di predittori": nome, "Brier": br, "Skill": 1 - br / brier_base, "AUC": auc(yte, p[te])}
        if anni_te is not None:
            vinti = [np.mean((p[te][anni_te == k] - yte[anni_te == k]) ** 2)
                     < np.mean((p0[te][anni_te == k] - yte[anni_te == k]) ** 2) for k in np.unique(anni_te)]
            riga["Anni vinti"], riga["Anni"] = int(sum(vinti)), len(vinti)
        rows.append(riga)

    n1, n0 = float(yte.sum()), float(len(yte) - yte.sum())
    h = max(orizzonte, 1)
    n1e, n0e = max(n1 / h, 1.0), max(n0 / h, 1.0)
    meta = {
        "n_test": int(te.sum()), "pos_test": int(n1), "n_passi": n_passi,
        "primo_test": int(f.t[te].iloc[0]), "ultimo_test": int(f.t[te].iloc[-1]),
        "base_rate": float(yte.mean()), "brier_base": brier_base,
        "auc_se": float(np.sqrt((n1e + n0e + 1) / (12 * n1e * n0e))),
    }
    return pd.DataFrame(rows), meta
