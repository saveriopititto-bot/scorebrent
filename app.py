"""App Streamlit: pesi degli archi (posizione -> distributori) con lo score di rifornimento."""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st

import fuel_model as fm

st.set_page_config(page_title="Score di rifornimento", page_icon="⛽", layout="wide")

BASE = Path(__file__).parent
ANAG_FILE = "anagrafica_impianti_attivi.csv"
PREZZI_FILE = "prezzo_alle_8.csv"


# --------------------------------------------------------------------------
# Dati
# --------------------------------------------------------------------------
def default_path(name: str) -> Path | None:
    for d in (BASE / "data", BASE, Path.cwd()):
        if (d / name).exists():
            return d / name
    return None


@st.cache_data(show_spinner="Leggo i CSV…")
def load_data(anag_bytes: bytes, prezzi_bytes: bytes):
    anag, extraction = fm.parse_anagrafica(anag_bytes)
    prezzi = fm.parse_prezzi(prezzi_bytes)
    return anag, prezzi, extraction


def get_bytes(uploaded, name: str) -> bytes | None:
    if uploaded is not None:
        return uploaded.getvalue()
    p = default_path(name)
    return p.read_bytes() if p else None


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
sb = st.sidebar
sb.header("Dati")
up_a = sb.file_uploader("Anagrafica impianti (CSV)", type="csv", help=ANAG_FILE)
up_p = sb.file_uploader("Prezzi alle 8 (CSV)", type="csv", help=PREZZI_FILE)

anag_b, prezzi_b = get_bytes(up_a, ANAG_FILE), get_bytes(up_p, PREZZI_FILE)
if anag_b is None or prezzi_b is None:
    st.title("⛽ Score di rifornimento")
    st.info(
        f"Carica i due CSV dalla barra laterale, oppure mettili nella cartella `data/` accanto ad `app.py` "
        f"(`{ANAG_FILE}` e `{PREZZI_FILE}`)."
    )
    st.stop()

anag, prezzi, extraction = load_data(anag_b, prezzi_b)

sb.header("Posizione (nodo centrale)")
modo_pos = sb.radio("Imposta da", ["Comune", "Coordinate"], horizontal=True)
if modo_pos == "Comune":
    comuni = sorted(anag.comune.unique())
    idx = comuni.index("GUALDO TADINO") if "GUALDO TADINO" in comuni else 0
    comune = sb.selectbox("Comune", comuni, index=idx)
    sel = anag[anag.comune == comune]
    origin = (float(sel.lat.median()), float(sel.lon.median()))
    sb.caption(f"Centro stimato dai distributori del comune: {origin[0]:.5f}, {origin[1]:.5f}")
else:
    c1, c2 = sb.columns(2)
    origin = (c1.number_input("Lat", value=43.2300, format="%.5f"), c2.number_input("Lon", value=12.7800, format="%.5f"))

usa_dest = sb.checkbox("Ho una destinazione (deviazione = detour sul percorso)")
dest = None
if usa_dest:
    c1, c2 = sb.columns(2)
    dest = (c1.number_input("Lat dest.", value=43.1100, format="%.5f"), c2.number_input("Lon dest.", value=12.3900, format="%.5f"))

sb.header("Carburante")
fuel = sb.selectbox("Prodotto", fm.FUELS)
self_service = sb.radio("Modalità", ["Self", "Servito"], horizontal=True) == "Self"
max_age = sb.number_input("Età massima del prezzo (giorni)", min_value=1, max_value=60, value=7)

sb.header("Veicolo")
v_tot = sb.number_input("Capacità serbatoio V_tot (l)", min_value=5.0, max_value=200.0, value=50.0, step=1.0)
livello = sb.slider("Livello attuale L", 0.0, 1.0, 0.25, 0.01, format="%.2f")
livello_min = sb.slider("Soglia di sicurezza L_min", 0.0, 0.5, 0.10, 0.01, format="%.2f")
q_custom = sb.checkbox("Imposta i litri q a mano (altrimenti pieno)")
litri = sb.number_input("Litri q", min_value=1.0, max_value=float(v_tot), value=min(30.0, float(v_tot)), step=1.0) if q_custom else None
consumo = sb.number_input("Consumo (l/100 km)", min_value=1.0, max_value=40.0, value=6.5, step=0.1)
usura = sb.number_input("Usura variabile (€/km)", min_value=0.0, max_value=1.0, value=0.05, step=0.01, format="%.3f")

sb.header("Modello")
raggio = sb.slider("Raggio d'azione (km su strada)", 2, 60, 15)
road_factor = sb.slider("Fattore strada / linea d'aria", 1.0, 2.0, 1.3, 0.05)
ref_mode = sb.radio("P_market = … dei prezzi nel raggio", ["mediana", "media"], horizontal=True)
alpha = sb.slider("α (pass-through Brent)", 0.0, 0.4, 0.20, 0.01)
theta = sb.number_input("Soglia θ (€)", value=0.0, step=0.5)

sb.subheader("Brent")
brent_mode = sb.radio("ΔB", ["Manuale", "Yahoo Finance"], horizontal=True)
if brent_mode == "Manuale":
    dB = sb.number_input("Variazione Brent in € (%)", value=0.0, step=0.5) / 100
    dB = fm.brent_delta(1 + dB, 1.0)  # applica il limite ±10%
    n_man = sb.number_input("misurata su n giorni", min_value=1, max_value=60, value=7)
    sigma_d = sb.number_input("Volatilità giornaliera σ (%)", min_value=0.1, max_value=10.0, value=1.8, step=0.1) / 100
    k_gg = max(1, round(n_man * 5 / 7))  # giorni di borsa
else:
    n_days = sb.number_input("n (giorni)", min_value=1, max_value=60, value=7)
    if sb.button("Scarica Brent e EUR/USD"):
        try:
            st.session_state["brent"] = fm.fetch_brent_yf(int(n_days))
        except Exception as e:  # rete assente, yfinance mancante, ecc.
            st.session_state.pop("brent", None)
            sb.error(f"Download non riuscito: {e}")
    data = st.session_state.get("brent")
    if data:
        dB = fm.brent_delta(data["b_t"], data["b_tn"], data["fx_t"], data["fx_tn"])
        sigma_d, k_gg = data["sigma"], data["k"]
        sb.caption(
            f"Brent {data['b_tn']:.2f} → {data['b_t']:.2f} $/bbl, EUR/USD {data['fx_tn']:.4f} → {data['fx_t']:.4f} "
            f"({data['data_tn']:%d/%m} → {data['data_t']:%d/%m})"
        )
    else:
        dB = 0.0
        sigma_d, k_gg = 0.018, 5
        sb.caption("Nessun dato scaricato: ΔB = 0.")
sb.metric("ΔB usato (limitato a ±10%)", f"{dB:+.2%}")

modula = sb.checkbox(
    "Modula α e θ con la forza del movimento", value=True,
    help="Un rialzo dentro il rumore normale del Brent pesa poco; uno oltre 'movimento pieno' pesa per intero. "
         "La soglia θ cresce con l'esposizione al Brent per la sua incertezza (σ·√k).",
)
z_pieno = sb.slider("Movimento «pieno» da (σ)", 0.5, 4.0, 2.0, 0.1, disabled=not modula)
kappa = sb.slider("Prudenza κ (× σ del termine Brent)", 0.0, 3.0, 1.0, 0.1, disabled=not modula)

# --------------------------------------------------------------------------
# Calcolo
# --------------------------------------------------------------------------
params = fm.ModelParams(
    v_tot=v_tot, livello=livello, litri=litri, alpha=alpha, delta_brent=dB,
    consumo_l100=consumo, usura_eur_km=usura, road_factor=road_factor, raggio_km=float(raggio),
    ref_mode=ref_mode, theta=theta, livello_min=livello_min,
    modula_brent=modula, sigma_giornaliera=float(sigma_d) if sigma_d == sigma_d else 0.018,
    k_giorni=int(k_gg), z_pieno=z_pieno, kappa=kappa,
)
cands = fm.build_candidates(anag, prezzi, fuel, self_service, float(max_age), extraction)
edges, info = fm.compute_edges(cands, origin, params, dest)

st.title("⛽ Score di rifornimento")
st.caption(
    f"Estrazione MIMIT del {extraction:%d/%m/%Y} · {len(cands):,} distributori con prezzo "
    f"{fuel} {'self' if self_service else 'servito'} valido in tutta Italia".replace(",", ".")
)

if edges.empty:
    st.warning("Nessun distributore nel raggio scelto con un prezzo valido. Aumenta il raggio o l'età massima del prezzo.")
    st.stop()

best = info["best"]
m = st.columns(5)
m[0].metric("P_market", f"{info['p_market']:.3f} €/l", help=f"{ref_mode} dei {info['n']} distributori nel raggio")
m[1].metric("Distributori nel raggio", info["n"])
m[2].metric("Litri q", f"{info['q']:.1f} l")
m[3].metric("C_km", f"{info['c_km']:.3f} €/km")
m[4].metric("S migliore", f"{best.score:+.2f} €")
if modula and dB != 0:
    st.caption(
        f"Brent: ΔB = {dB:+.2%} = {info['z']:+.2f} σ → peso g = {info['g']:.2f}, α effettivo = {info['alpha_eff']:.3f} "
        f"(impostato {alpha:.2f}) · soglia θ effettiva = {info['theta_eff']:.2f} € "
        f"(di cui margine di prudenza {info['margine']:.2f} €)"
    )

msg = f"**{best.bandiera} · {best.nome}** — {best.indirizzo}, {best.comune}  \n" \
      f"{best.prezzo:.3f} €/l a {best.dist_km:.1f} km · {info['motivo']}"
(st.success if info["decisione"] else st.warning)(("✅ Rifornisci: " if info["decisione"] else "⏸️ Non conviene: ") + msg)
if info["decisione"] is False:
    st.caption("Il termine Brent è uguale per tutti i distributori: sposta lo score ma non cambia la classifica.")

# --------------------------------------------------------------------------
# Mappa
# --------------------------------------------------------------------------
smin, smax = edges.score.min(), edges.score.max()


def colore(s: float) -> list[int]:
    t = 1.0 if smax == smin else (s - smin) / (smax - smin)
    return [int(220 * (1 - t)), int(70 + 130 * t), 80, 210]


edges["colore"] = edges.score.map(colore)
edges["etichetta"] = (
    edges.bandiera + " · " + edges.nome + "\n" + edges.prezzo.map("{:.3f} €/l".format)
    + " · S = " + edges.score.map("{:+.2f} €".format) + " · " + edges.dist_km.map("{:.1f} km".format)
)
edges["src"] = [[origin[1], origin[0]]] * len(edges)
edges["tgt"] = edges[["lon", "lat"]].values.tolist()

layers = [
    pdk.Layer("LineLayer", data=edges, get_source_position="src", get_target_position="tgt",
              get_color="colore", get_width=2, width_min_pixels=1),
    pdk.Layer("ScatterplotLayer", data=edges, get_position=["lon", "lat"], get_fill_color="colore",
              get_radius=120, radius_min_pixels=5, radius_max_pixels=14, pickable=True),
    pdk.Layer("ScatterplotLayer", data=pd.DataFrame([{"lat": origin[0], "lon": origin[1]}]),
              get_position=["lon", "lat"], get_fill_color=[30, 100, 240, 255], get_radius=150,
              radius_min_pixels=8, radius_max_pixels=16),
]
zoom = max(5.0, 12.2 - math.log2(max(raggio, 2) / 5))
st.pydeck_chart(
    pdk.Deck(layers=layers, initial_view_state=pdk.ViewState(latitude=origin[0], longitude=origin[1], zoom=zoom),
             tooltip={"text": "{etichetta}"}),
    height=480,
)
st.caption("Punto blu = posizione. Verde = S alto (conviene), rosso = S basso. Distanze: linea d'aria × fattore strada.")

# --------------------------------------------------------------------------
# Tabella dei pesi
# --------------------------------------------------------------------------
tab = edges.rename(
    columns={
        "rank": "#", "bandiera": "Bandiera", "nome": "Impianto", "indirizzo": "Indirizzo", "comune": "Comune",
        "prezzo": "P_i (€/l)", "dist_km": "Distanza (km)", "dev_km": "D_i (km)",
        "guadagno": "Guadagno (€)", "brent": "Brent (€)", "costo_log": "Costo logistico (€)",
        "score": "S_i (€)", "peso": "Peso w = −S", "peso_pos": "Peso w ≥ 0", "ep": "E_p", "ep_pct": "E_p (percentile)",
        "eta_giorni": "Età prezzo (gg)",
    }
)
cols = ["#", "Bandiera", "Impianto", "Indirizzo", "Comune", "P_i (€/l)", "Distanza (km)", "D_i (km)",
        "Guadagno (€)", "Brent (€)", "Costo logistico (€)", "S_i (€)", "Peso w = −S", "Peso w ≥ 0",
        "E_p", "E_p (percentile)", "Età prezzo (gg)", "id", "lat", "lon"]
cols = [c for c in cols if c in tab.columns]
st.subheader("Archi origine → distributore")
st.dataframe(
    tab[cols], hide_index=True, height=420,
    column_config={
        "P_i (€/l)": st.column_config.NumberColumn(format="%.3f"),
        "Distanza (km)": st.column_config.NumberColumn(format="%.1f"),
        "D_i (km)": st.column_config.NumberColumn(format="%.1f"),
        "Guadagno (€)": st.column_config.NumberColumn(format="%+.2f"),
        "Brent (€)": st.column_config.NumberColumn(format="%+.2f"),
        "Costo logistico (€)": st.column_config.NumberColumn(format="%.2f"),
        "S_i (€)": st.column_config.NumberColumn(format="%+.2f"),
        "Peso w = −S": st.column_config.NumberColumn(format="%+.2f"),
        "Peso w ≥ 0": st.column_config.NumberColumn(format="%.2f"),
        "E_p": st.column_config.NumberColumn(format="%.2f"),
        "E_p (percentile)": st.column_config.NumberColumn(format="%.2f"),
        "Età prezzo (gg)": st.column_config.NumberColumn(format="%.1f"),
    },
)

export = tab[cols].copy()
export.insert(0, "origine_lat", origin[0])
export.insert(1, "origine_lon", origin[1])
st.download_button("Scarica gli archi (CSV)", export.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                   file_name="archi_pesati.csv", mime="text/csv")

with st.expander("Formula e significato dei termini"):
    st.markdown(
        r"""
$$S_i = q\,\big[(P_{market}-P_i)+\alpha\,P_{market}\,\Delta B\big]-D_i\,C_{km}$$

- **q**: litri acquistati (`V_tot·(1−L)` se pieno).
- **P_market**: mediana/media dei prezzi dei distributori nel raggio.
- **ΔB**: variazione relativa del Brent in euro su *n* giorni, limitata a ±10%; **α** è la quota di pass-through.
- **Modulazione dal Brent**: z = ln(1+ΔB) / (σ·√k) misura il movimento in unità di rumore normale. α diventa
  α·g con g = min(1, |z|/z_pieno), e la soglia diventa θ + κ·q·α·g·P_market·σ·√k: più si scommette sul Brent,
  più margine si pretende. Il termine Brent conta così solo per la parte del movimento che supera il rumore.
- **D_i**: deviazione. Senza destinazione è andata e ritorno (2·d); con destinazione è `d(o,i)+d(i,dest)−d(o,dest)`.
- **C_km** = consumo/100 · P_market + usura.
- **Peso dell'arco**: `w = −S_i` (cammino minimo), oppure `w = S_max − S_i` se servono pesi non negativi.
- **E_p**: efficienza posizionale, `1 − (P_i−P_min)/(P_max−P_min)`; la versione percentile resiste agli outlier.
- Si rifornisce se `S_max > θ_eff` (θ_eff = θ più il margine di prudenza), oppure se `L < L_min`.
"""
    )
