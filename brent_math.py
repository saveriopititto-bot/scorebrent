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
| (nessuno)                              | o_k = volatilita' attesa dal mercato delle |
|                                        | opzioni sul petrolio (OVX), opzionale      |

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
# None = tutti i predittori presenti nella tabella (vedi _risolvi).
INSIEMI = {
    "Livello 1 (dx, dy)": ["dx", "dy"],
    "+ coseno": ["dx", "dy", "cos"],
    "+ area di Lévy": ["dx", "dy", "levy"],
    "+ oscillazione": ["dx", "dy", "sigma", "mad"],
    "+ meteo": ["dx", "dy", "meteo"],
    "+ OVX": ["dx", "dy", "ovx"],
    "Tutto": None,
}
PREDITTORI = ["dx", "dy", "cos", "levy", "sigma", "mad", "meteo", "ovx"]


def _risolvi(insiemi: dict, predittori: list[str], f: pd.DataFrame) -> dict:
    """Insiemi utilizzabili con le colonne di `f`; None diventa «tutti i
    predittori presenti»."""
    out = {}
    for nome, cols in insiemi.items():
        cols = [c for c in predittori if c in f.columns] if cols is None else cols
        if set(cols) <= set(f.columns):
            out[nome] = cols
    return out


def costruisci_features(x, y, w: int, orizzonte: int, meteo=None, ovx=None) -> pd.DataFrame:
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
    predittori vengono confrontati sugli stessi casi.

    Con `ovx` (ln della volatilita' attesa per bin, allineata a x) aggiunge la
    colonna `ovx` con il valore all'istante t; le righe senza OVX sono scartate."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = None if meteo is None else np.asarray(meteo, float)
    o = None if ovx is None else np.asarray(ovx, float)
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
        if o is not None:
            if not np.isfinite(o[t]):
                continue
            riga += (float(o[t]),)
        rows.append(riga)
    cols = (["t", "dx", "dy", "cos", "levy", "sigma", "mad", "fwd"] + ([] if m is None else ["meteo"])
            + ([] if o is None else ["ovx"]))
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
    insiemi = _risolvi(INSIEMI, PREDITTORI, f)
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


# --------------------------------------------------------------------------
# Previsione dell'oscillazione
# --------------------------------------------------------------------------
# Bersaglio: oscillazione realizzata nei prossimi `orizzonte` bin, cioe' la
# radice della media dei quadrati degli incrementi di x (rendimenti
# logaritmici). Si prevede il suo logaritmo con una regressione ridge, in stile
# HAR: oscillazione su una finestra breve e una lunga, piu' l'agitazione
# (escursione fra massimo e minimo), che ne e' una misura meno rumorosa, e
# facoltativamente la volatilita' attesa dal mercato (OVX) e il meteo.
INSIEMI_OSC = {
    "Oscillazione recente": ["s_breve", "s_lungo", "mad"],
    "+ agitazione": ["s_breve", "s_lungo", "mad", "agit"],
    "+ agitazione e meteo": ["s_breve", "s_lungo", "mad", "agit", "meteo"],
    "+ agitazione e OVX": ["s_breve", "s_lungo", "mad", "agit", "ovx"],
    "Tutto": None,
}
PREDITTORI_OSC = ["s_breve", "s_lungo", "mad", "agit", "meteo", "ovx"]
_PAVIMENTO = 1e-6  # evita ln(0) nei periodi senza movimento


def costruisci_features_oscillazione(x, y, w: int, orizzonte: int, meteo=None, ovx=None,
                                    breve: int = 5) -> pd.DataFrame:
    """Una riga per ogni t >= w. Predittori (logaritmi): `s_breve` e `s_lungo`
    = RMS degli incrementi negli ultimi `breve` e w bin, `mad` = deviazione
    assoluta mediana sugli ultimi w; `agit` = media di y sugli ultimi `breve`
    bin; `meteo` (opzionale) = media dell'anomalia sugli ultimi w bin;
    `ovx` (opzionale) = ln della volatilita' attesa per bin all'istante t.
    `bersaglio` = ln RMS degli incrementi nei prossimi `orizzonte` bin, NaN
    dove il futuro non e' ancora noto (servono per la previsione di oggi)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    r = np.r_[np.nan, np.diff(x)]
    m = None if meteo is None else np.asarray(meteo, float)
    o = None if ovx is None else np.asarray(ovx, float)
    breve = min(breve, w)
    rows = []
    for t in range(w, len(x)):
        rl, rb = r[t - w + 1 : t + 1], r[t - breve + 1 : t + 1]
        riga = {
            "t": t,
            "s_breve": np.log(max(np.sqrt(np.mean(rb**2)), _PAVIMENTO)),
            "s_lungo": np.log(max(np.sqrt(np.mean(rl**2)), _PAVIMENTO)),
            "mad": np.log(max(float(np.median(np.abs(rl - np.median(rl)))), _PAVIMENTO)),
            "agit": float(np.mean(y[t - breve + 1 : t + 1])),
            "bersaglio": (np.log(max(np.sqrt(np.mean(r[t + 1 : t + orizzonte + 1] ** 2)), _PAVIMENTO))
                          if t + orizzonte < len(x) else np.nan),
        }
        if m is not None:
            ms = m[t - w + 1 : t + 1]
            riga["meteo"] = float(np.nanmean(ms)) if np.isfinite(ms).sum() >= w / 2 else np.nan
        if o is not None:
            riga["ovx"] = float(o[t])
        rows.append(riga)
    return pd.DataFrame(rows)


def _fit_ridge(X, y, lam: float = 1.0):
    """Ridge su predittori standardizzati (intercetta non penalizzata).
    Restituisce (funzione di previsione, varianza dei residui)."""
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1.0
    Z = np.c_[np.ones(len(X)), (X - mu) / sd]
    R = lam * np.eye(Z.shape[1])
    R[0, 0] = 0.0
    beta = np.linalg.solve(Z.T @ Z + R, Z.T @ y)
    var_res = float(np.var(y - Z @ beta))
    return (lambda Xn: np.c_[np.ones(len(Xn)), (Xn - mu) / sd] @ beta), var_res


def prevedi_oscillazione(feat: pd.DataFrame, cols: list[str], lam: float = 1.0) -> float:
    """Oscillazione attesa (frazione per bin) dopo l'ultima riga, imparando
    da tutte le righe con bersaglio noto. Il fattore exp(var/2) corregge la
    sottostima che nasce dal tornare dal logaritmo alla scala normale."""
    f = feat.dropna(subset=cols)
    tr = f[f.bersaglio.notna()]
    if len(tr) < 30:
        raise ValueError("Troppo pochi dati per prevedere l'oscillazione.")
    pred, var = _fit_ridge(tr[cols].values, tr.bersaglio.values, lam)
    return float(np.exp(pred(f[cols].values[-1:])[0] + var / 2))


def valida_oscillazione(feat: pd.DataFrame, orizzonte: int, passo: int = 21, inizio_frac: float = 0.4,
                        lam: float = 1.0, anni=None):
    """Prova a finestre scorrevoli come `validazione`, ma per l'oscillazione.

    Riferimenti ingenui: «come appena passato» (prevede l'oscillazione degli
    ultimi w bin, s_lungo), «media storica» (media del bersaglio nel training)
    e, se c'e' la colonna `ovx`, «OVX cosi' com'e'» (la volatilita' attesa dal
    mercato, senza alcun adattamento). Gli errori sono in punti percentuali di oscillazione per bin:
    bias = errore medio (positivo = sovrastima), MAD = errore assoluto medio,
    sigma = deviazione standard dell'errore. Il miglioramento e gli anni vinti
    sono misurati contro «come appena passato», il riferimento piu' difficile.

    Restituisce (tabella, serie con reale e previsioni per riga di test, meta)."""
    cols_tutte = [c for c in PREDITTORI_OSC if c in feat.columns]
    f = feat.dropna(subset=["bersaglio"] + cols_tutte).reset_index(drop=True)
    n = len(f)
    if n < 100:
        raise ValueError(f"Troppo pochi dati per la prova ({n} casi utili, ne servono almeno 100).")
    insiemi = _risolvi(INSIEMI_OSC, PREDITTORI_OSC, f)
    prev = {nome: np.full(n, np.nan) for nome in insiemi}
    prev["Come appena passato"] = np.exp(f.s_lungo.values)
    if "ovx" in f.columns:
        prev["OVX così com'è"] = np.exp(f.ovx.values)
    prev["Media storica"] = np.full(n, np.nan)
    te = np.zeros(n, bool)
    n_passi = 0
    for a in range(int(n * inizio_frac), n, passo):
        b = min(a + passo, n)
        tr = (f.t + orizzonte <= f.t.iloc[a]).values
        if tr.sum() < 30:
            continue
        n_passi += 1
        te[a:b] = True
        ytr = f.bersaglio.values[tr]
        prev["Media storica"][a:b] = np.exp(ytr.mean() + ytr.var() / 2)
        for nome, cols in insiemi.items():
            pred, var = _fit_ridge(f.loc[tr, cols].values, ytr, lam)
            prev[nome][a:b] = np.exp(pred(f.loc[a : b - 1, cols].values) + var / 2)
    if not te.any():
        raise ValueError("Troppo pochi dati per la prova.")

    reale = 100 * np.exp(f.bersaglio.values[te])
    prev = {nome: 100 * p[te] for nome, p in prev.items()}
    mse_rif = np.mean((prev["Come appena passato"] - reale) ** 2)
    anni_te = None if anni is None else np.asarray(anni)[f.t.values[te]]
    rows = []
    for nome, p in prev.items():
        e = p - reale
        riga = {"Previsione": nome, "Bias": float(e.mean()), "MAD": float(np.abs(e).mean()),
                "Sigma": float(e.std()), "Miglioramento": float(1 - np.mean(e**2) / mse_rif)}
        if anni_te is not None:
            vinti = [np.mean(e[anni_te == k] ** 2) < np.mean((prev["Come appena passato"] - reale)[anni_te == k] ** 2)
                     for k in np.unique(anni_te)]
            riga["Anni vinti"], riga["Anni"] = int(sum(vinti)), len(vinti)
        rows.append(riga)
    serie = pd.DataFrame({"t": f.t.values[te], "Reale": reale, **prev})
    meta = {"n_test": int(te.sum()), "n_passi": n_passi,
            "primo_test": int(f.t.values[te][0]), "ultimo_test": int(f.t.values[te][-1])}
    return pd.DataFrame(rows), serie, meta
