"""Modello di scoring razionale per il rifornimento.

Calcola il peso degli archi dal nodo centrale (posizione della macchina)
verso i distributori vicini, a partire dai CSV open data MIMIT
(anagrafica impianti + prezzi alle 8).

    S_i = q * [ (P_market - P_i) + alpha * P_market * dB ] - D_i * C_km

    q   = litri acquistati (default V_tot * (1 - L))
    dB  = (B_t - B_{t-n}) / B_{t-n}, in euro, limitato a +-10%
    D_i = deviazione chilometrica (andata/ritorno, oppure detour rispetto
          alla rotta origine -> destinazione)
    C_km = consumo/100 * P_market + usura
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

EARTH_RADIUS_KM = 6371.0088

# Solo i prodotti "standard": le varianti premium (Blue Diesel, V-Power, ...)
# hanno prezzi diversi e falserebbero il confronto.
FUELS = ("Benzina", "Gasolio", "GPL", "Metano")

# Intervalli plausibili (€/l, Metano €/kg) per scartare errori di inserimento.
PRICE_BOUNDS = {
    "Benzina": (0.8, 3.5),
    "Gasolio": (0.8, 3.5),
    "GPL": (0.3, 2.0),
    "Metano": (0.8, 3.5),
}

ITALY_BBOX = (35.0, 48.0, 6.0, 19.0)  # lat_min, lat_max, lon_min, lon_max


# --------------------------------------------------------------------------
# Lettura dei CSV
# --------------------------------------------------------------------------
def _to_text(src) -> str:
    if isinstance(src, (str, Path)):
        return Path(src).read_text(encoding="utf-8-sig", errors="replace")
    if isinstance(src, (bytes, bytearray)):
        return bytes(src).decode("utf-8-sig", errors="replace")
    data = src.read()
    return data.decode("utf-8-sig", errors="replace") if isinstance(data, bytes) else data


def _extraction_date(first_line: str) -> pd.Timestamp | None:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", first_line)
    return pd.Timestamp(m.group(1)) if m else None


def parse_anagrafica(src) -> tuple[pd.DataFrame, pd.Timestamp | None]:
    """Legge anagrafica_impianti_attivi.csv (separatore '|', 1ª riga = titolo).

    Alcune righe hanno un '|' in più dentro nome/indirizzo: i campi fissi
    (id, gestore, bandiera, tipo in testa; comune, provincia, lat, lon in coda)
    permettono di ricostruirle senza perderle.
    """
    lines = _to_text(src).splitlines()
    extraction = _extraction_date(lines[0]) if lines else None
    rows = []
    for line in lines[2:]:
        f = line.split("|")
        if len(f) < 10:
            continue
        mid = f[4:-4]
        rows.append(
            (
                f[0].strip(),
                f[1].strip(),
                f[2].strip(),
                f[3].strip(),
                mid[0].strip() if mid else "",
                " ".join(m.strip() for m in mid[1:]),
                f[-4].strip().upper(),
                f[-3].strip().upper(),
                f[-2],
                f[-1],
            )
        )
    df = pd.DataFrame(
        rows,
        columns=["id", "gestore", "bandiera", "tipo", "nome", "indirizzo",
                 "comune", "provincia", "lat", "lon"],
    )
    for c in ("lat", "lon"):
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    la0, la1, lo0, lo1 = ITALY_BBOX
    df = df.dropna(subset=["lat", "lon"])
    df = df[df.lat.between(la0, la1) & df.lon.between(lo0, lo1)]
    return df.drop_duplicates("id").reset_index(drop=True), extraction


def parse_prezzi(src) -> pd.DataFrame:
    """Legge prezzo_alle_8.csv (separatore '|', 1ª riga = titolo)."""
    import io

    text = _to_text(src)
    df = pd.read_csv(io.StringIO(text), sep="|", skiprows=1, dtype=str, on_bad_lines="skip")
    df = df.rename(
        columns={"idImpianto": "id", "descCarburante": "carburante", "isSelf": "is_self", "dtComu": "dt_comu"}
    )
    df["id"] = df["id"].str.strip()
    df["carburante"] = df["carburante"].str.strip()
    df["prezzo"] = pd.to_numeric(df["prezzo"].str.replace(",", ".", regex=False), errors="coerce")
    df["is_self"] = pd.to_numeric(df["is_self"], errors="coerce").fillna(0).astype(int) == 1
    df["dt_comu"] = pd.to_datetime(df["dt_comu"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    return df.dropna(subset=["prezzo"]).reset_index(drop=True)


def build_candidates(
    anag: pd.DataFrame,
    prezzi: pd.DataFrame,
    fuel: str,
    self_service: bool,
    max_age_days: float | None,
    extraction_date: pd.Timestamp | None,
) -> pd.DataFrame:
    """Un record per distributore: anagrafica + prezzo del carburante scelto."""
    p = prezzi[(prezzi.carburante.str.lower() == fuel.lower()) & (prezzi.is_self == self_service)]
    lo, hi = PRICE_BOUNDS.get(fuel, (0.0, 10.0))
    p = p[p.prezzo.between(lo, hi)]
    if max_age_days is not None and extraction_date is not None:
        limite = extraction_date + pd.Timedelta(days=1) - pd.Timedelta(days=max_age_days)
        p = p[p.dt_comu >= limite]
    p = p.sort_values("dt_comu").drop_duplicates("id", keep="last")
    out = anag.merge(p[["id", "prezzo", "dt_comu"]], on="id", how="inner")
    if extraction_date is not None:
        out["eta_giorni"] = (extraction_date + pd.Timedelta(days=1) - out["dt_comu"]).dt.total_seconds() / 86400
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------
# Geometria
# --------------------------------------------------------------------------
def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


# --------------------------------------------------------------------------
# Brent
# --------------------------------------------------------------------------
def brent_delta(b_t, b_tn, eurusd_t=1.0, eurusd_tn=1.0, clip=0.10) -> float:
    """Variazione relativa del Brent in euro, limitata a +-clip.

    b_* in USD/barile; eurusd_* = dollari per 1 euro (quotazione EUR/USD).
    """
    e_t, e_tn = b_t / eurusd_t, b_tn / eurusd_tn
    return float(np.clip((e_t - e_tn) / e_tn, -clip, clip))


def fetch_brent_yf(n_days: int) -> dict:
    """Scarica Brent (BZ=F) ed EUR/USD da Yahoo Finance. Richiede `yfinance`."""
    import yfinance as yf

    # ~120 giorni di calendario bastano per stimare σ su 60 rendimenti giornalieri
    start = pd.Timestamp.today().normalize() - pd.Timedelta(days=max(int(n_days) + 15, 120))

    def serie(ticker: str) -> pd.Series:
        s = yf.Ticker(ticker).history(start=start)["Close"].dropna()
        if s.empty:
            raise ValueError(f"Nessun dato per {ticker}")
        s.index = s.index.tz_localize(None).normalize()
        return s

    def valore_a(s: pd.Series, giorno: pd.Timestamp) -> float:
        s = s[s.index <= giorno]
        if s.empty:
            raise ValueError("Storico insufficiente")
        return float(s.iloc[-1])

    brent, fx = serie("BZ=F"), serie("EURUSD=X")
    t = min(brent.index[-1], fx.index[-1])
    tn = t - pd.Timedelta(days=int(n_days))

    # Volatilità giornaliera σ (frazione): RMS degli ultimi 60 rendimenti log. del Brent in euro,
    # e k = numero di giorni di borsa fra il giorno di confronto e t.
    eur = (brent / fx.reindex(brent.index, method="ffill")).dropna()
    rend = np.diff(np.log(eur.to_numpy()))
    sigma = float(np.sqrt(np.mean(rend[-60:] ** 2))) if len(rend) >= 5 else float("nan")
    giorno_prima = eur.index[eur.index <= tn][-1]
    k = int(((eur.index > giorno_prima) & (eur.index <= t)).sum())
    return {
        "data_t": t, "data_tn": tn,
        "b_t": valore_a(brent, t), "b_tn": valore_a(brent, tn),
        "fx_t": valore_a(fx, t), "fx_tn": valore_a(fx, tn),
        "sigma": sigma, "k": k,
    }


def forza_movimento(delta_rel: float, sigma_giornaliera: float, k: int) -> float:
    """z = ln(1 + ΔB) / (σ·√k): quanto è grande il movimento rispetto al rumore
    normale di k giorni di borsa (σ = volatilità giornaliera come frazione)."""
    if not (sigma_giornaliera and sigma_giornaliera > 0 and k and k > 0):
        return float("nan")
    return float(np.log1p(delta_rel) / (sigma_giornaliera * np.sqrt(k)))


def peso_brent(z: float, z_pieno: float = 2.0) -> float:
    """Peso g in [0, 1] del termine speculativo: cresce linearmente con |z| e
    vale 1 da |z| >= z_pieno. Un movimento dentro il rumore pesa poco.
    Se z non è definita (σ ignota) il termine resta a peso pieno."""
    if z != z:  # NaN
        return 1.0
    return float(min(1.0, abs(z) / z_pieno))


# --------------------------------------------------------------------------
# Modello
# --------------------------------------------------------------------------
@dataclass
class ModelParams:
    v_tot: float = 50.0            # capacità serbatoio (l)
    livello: float = 0.25          # L in [0, 1]
    litri: float | None = None     # q; None -> v_tot * (1 - L)
    alpha: float = 0.2             # pass-through del Brent, [0, 0.4]
    delta_brent: float = 0.0       # dB relativo (già limitato)
    consumo_l100: float = 6.5      # l/100 km
    usura_eur_km: float = 0.05     # costo variabile di usura (€/km)
    road_factor: float = 1.3       # km su strada / km in linea d'aria
    raggio_km: float = 15.0        # raggio d'azione (km su strada stimati)
    ref_mode: str = "mediana"      # "mediana" | "media" per P_market
    theta: float = 0.0             # soglia di decisione (€)
    livello_min: float = 0.10      # L_min: sotto questa soglia si rifornisce comunque
    # Modulazione dal Brent (matematica del paper "sisma", adattata)
    modula_brent: bool = True      # se False: α e θ restano quelli impostati
    sigma_giornaliera: float = 0.018  # σ giornaliera del Brent in euro (frazione)
    k_giorni: int = 5              # giorni di borsa su cui è misurato ΔB
    z_pieno: float = 2.0           # |z| da cui il termine Brent pesa per intero
    kappa: float = 1.0             # prudenza: margine = κ · (esposizione al Brent) · σ·√k

    @property
    def litri_effettivi(self) -> float:
        cap = self.v_tot * (1 - self.livello)
        return cap if self.litri is None else float(min(self.litri, cap))


def compute_edges(
    cands: pd.DataFrame,
    origin: tuple[float, float],
    p: ModelParams,
    dest: tuple[float, float] | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Pesi degli archi origine -> distributore.

    Restituisce (tabella ordinata per score decrescente, riepilogo).
    Colonne chiave: score = S_i (da massimizzare), peso = -S_i (costo per
    cammino minimo), peso_pos = S_max - S_i (costo non negativo).
    """
    olat, olon = origin
    df = cands.copy()
    df["dist_km"] = haversine_km(olat, olon, df.lat.values, df.lon.values) * p.road_factor
    df = df[df.dist_km <= p.raggio_km].copy()
    summary: dict = {"n": len(df), "q": p.litri_effettivi}
    if df.empty:
        return df, summary

    p_market = float(df.prezzo.median() if p.ref_mode == "mediana" else df.prezzo.mean())
    c_km = p.consumo_l100 / 100 * p_market + p.usura_eur_km
    q = p.litri_effettivi

    if dest is None:
        df["dev_km"] = 2 * df.dist_km
    else:
        dlat, dlon = dest
        d_dest = haversine_km(df.lat.values, df.lon.values, dlat, dlon) * p.road_factor
        d_dir = float(haversine_km(olat, olon, dlat, dlon)) * p.road_factor
        df["dev_km"] = np.clip(df.dist_km + d_dest - d_dir, 0, None)

    # Termine Brent: α viene pesato dalla forza del movimento (g) e la soglia θ
    # cresce con l'esposizione effettiva al Brent per la sua incertezza (σ·√k).
    z = forza_movimento(p.delta_brent, p.sigma_giornaliera, p.k_giorni)
    g = peso_brent(z, p.z_pieno) if p.modula_brent else 1.0
    alpha_eff = p.alpha * g
    sigma_n = p.sigma_giornaliera * np.sqrt(max(p.k_giorni, 1))
    margine = p.kappa * q * alpha_eff * p_market * sigma_n if p.modula_brent else 0.0
    theta_eff = p.theta + margine

    df["guadagno"] = q * (p_market - df.prezzo)
    df["brent"] = q * alpha_eff * p_market * p.delta_brent
    df["costo_log"] = df.dev_km * c_km
    df["score"] = df.guadagno + df.brent - df.costo_log
    df["peso"] = -df.score
    df["peso_pos"] = df.score.max() - df.score

    pmin, pmax = df.prezzo.min(), df.prezzo.max()
    df["ep"] = 1.0 if pmax == pmin else 1 - (df.prezzo - pmin) / (pmax - pmin)
    n = len(df)
    df["ep_pct"] = 1.0 if n == 1 else 1 - (df.prezzo.rank(method="average") - 1) / (n - 1)

    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", np.arange(1, n + 1))

    best = df.iloc[0]
    sicurezza = p.livello < p.livello_min
    if sicurezza:
        decisione, motivo = True, f"livello serbatoio sotto la soglia di sicurezza ({p.livello:.0%} < {p.livello_min:.0%})"
    elif best.score > theta_eff:
        decisione, motivo = True, f"S migliore ({best.score:+.2f} €) supera la soglia θ = {theta_eff:.2f} €"
    else:
        decisione, motivo = False, f"S migliore ({best.score:+.2f} €) non supera la soglia θ = {theta_eff:.2f} €"
    summary.update(
        p_market=p_market, c_km=c_km, best=best, decisione=decisione, motivo=motivo,
        p_min=float(pmin), p_max=float(pmax),
        z=z, g=g, alpha_eff=alpha_eff, theta_eff=theta_eff, margine=margine,
    )
    return df, summary
