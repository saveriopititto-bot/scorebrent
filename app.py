"""App «Prezzo del petrolio»: Brent da Yahoo Finance e analisi del suo andamento
(matematica del paper "sisma", in brent_math.py), con la temperatura in Europa da
Open-Meteo come possibile dato di previsione. Avvio: `streamlit run app.py`."""
from io import BytesIO

import altair as alt
import numpy as np
import pandas as pd
import requests
import streamlit as st

import brent_math as bm
import dati
import style

# Con ?pagina=score l'app mostra solo la scheda «Score rifornimento», senza titolo né barra laterale: è la
# versione incorporata in FuelMode (scheda «Petrolio»). Le impostazioni restano quelle predefinite.
SOLO_SCORE = st.query_params.get("pagina") == "score"

st.set_page_config(page_title="Prezzo del petrolio", page_icon="🛢️", layout="wide",
                   initial_sidebar_state="collapsed" if SOLO_SCORE else "auto")
style.apply_style()  # stile di FuelMode; il titolo dell'app è nella barra delle schede
if SOLO_SCORE:  # niente barra laterale, intestazione e margini: la scheda riempie il riquadro di FuelMode
    st.markdown("<style>[data-testid='stSidebar'], [data-testid='stSidebarCollapsedControl'], "
                "[data-testid='stExpandSidebarButton'], header[data-testid='stHeader'] {display: none;} "
                "[data-testid='stMainBlockContainer'] {padding: 0 !important;} "
                "[data-testid='stMain'] [data-testid='stElementContainer']:has(style) {display: none;}</style>", unsafe_allow_html=True)


# Nomi comprensibili per le previsioni dell'oscillazione (chiavi di bm.INSIEMI_OSC più i riferimenti).
NOMI_OSC = {
    "Oscillazione recente": "Modello: oscillazione recente (sigma e MAD)",
    "+ agitazione": "Modello: + agitazione (massimo − minimo)",
    "+ agitazione e meteo": "Modello: + agitazione e temperatura",
    "+ agitazione e OVX": "Modello: + agitazione e OVX",
    "+ agitazione e GPR": "Modello: + agitazione e rischio geopolitico",
    "Tutto": "Modello: tutti i dati disponibili",
    "Come appena passato": "Riferimento: come nel periodo appena passato",
    "OVX così com'è": "Riferimento: OVX così com'è",
    "Media storica": "Riferimento: media storica",
}

# Nomi comprensibili per i gruppi di dati usati nella prova di previsione (chiavi di bm.INSIEMI).
NOMI_INSIEMI = {
    "Livello 1 (dx, dy)": "Solo le variazioni recenti",
    "+ coseno": "+ quanto prezzo e agitazione si muovono insieme",
    "+ area di Lévy": "+ chi anticipa chi",
    "+ oscillazione": "+ quanto oscilla il prezzo (sigma e MAD)",
    "+ meteo": "+ temperatura in Europa",
    "+ OVX": "+ volatilità attesa dal mercato (OVX)",
    "+ GPR": "+ rischio geopolitico (GPR)",
    "Tutto": "Tutti i dati disponibili",
}

# Città europee di cui si fa la media della temperatura (latitudine, longitudine).
CITTA = {
    "Berlino": (52.52, 13.41),
    "Parigi": (48.86, 2.35),
    "Londra": (51.51, -0.13),
    "Milano": (45.46, 9.19),
    "Madrid": (40.42, -3.70),
}
METEO_STORICO = "https://archive-api.open-meteo.com/v1/archive"
METEO_RECENTE = "https://api.open-meteo.com/v1/forecast"
# Geopolitical Risk Index giornaliero (Caldara e Iacoviello): 100 = media 1985-2019.
GPR_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls"
# Prezzi medi nazionali alla pompa, settimanali, tasse incluse (Weekly Oil Bulletin della Commissione Europea,
# ripubblicato da fuel-prices.eu, CC BY 4.0).
POMPA_URL = "https://www.fuel-prices.eu/research/data/d1-eu-weekly-bulletin/fp-d1-eu-weekly-panel.parquet"
LITRI_BARILE = 158.987


@st.cache_data(ttl=900, show_spinner="Scarico i prezzi da Yahoo Finance…")
def scarica(ticker: str) -> pd.DataFrame:
    return dati.scarica_yahoo(ticker)


def _temperature(url: str, **params) -> pd.DataFrame:
    """Temperatura media giornaliera (°C) delle CITTA: una colonna per città."""
    lat, lon = zip(*CITTA.values())
    r = requests.get(url, timeout=30, params={
        "latitude": ",".join(map(str, lat)), "longitude": ",".join(map(str, lon)),
        "daily": "temperature_2m_mean", "timezone": "Europe/Berlin", **params,
    })
    r.raise_for_status()
    js = r.json()
    luoghi = js if isinstance(js, list) else [js]  # con una sola città Open-Meteo restituisce un oggetto
    return pd.DataFrame({
        nome: pd.Series(l["daily"]["temperature_2m_mean"], index=pd.to_datetime(l["daily"]["time"]), dtype=float)
        for nome, l in zip(CITTA, luoghi)
    })


@st.cache_data(ttl=6 * 3600, show_spinner="Scarico le temperature da Open-Meteo…")
def scarica_meteo(inizio: pd.Timestamp, fine: pd.Timestamp) -> pd.Series:
    """Temperatura media delle CITTA giorno per giorno. Lo storico di Open-Meteo arriva con alcuni
    giorni di ritardo: gli ultimi giorni vengono dalle previsioni, che includono il passato recente."""
    fine_storico = max(inizio, fine - pd.Timedelta(days=7))  # oltre, lo storico non è ancora pubblicato
    storico = _temperature(METEO_STORICO, start_date=f"{inizio:%Y-%m-%d}", end_date=f"{fine_storico:%Y-%m-%d}")
    recente = _temperature(METEO_RECENTE, past_days=31, forecast_days=1)
    t = storico.combine_first(recente).loc[:fine]
    media = t.mean(axis=1).where(t.notna().sum(axis=1) >= 3)  # almeno 3 città su 5
    if media.dropna().empty:
        raise ValueError("Open-Meteo non ha restituito temperature")
    return media.dropna()


@st.cache_data(ttl=12 * 3600, show_spinner="Scarico il rischio geopolitico (GPR)…")
def scarica_gpr() -> pd.DataFrame:
    """GPR giornaliero (calendario, weekend compresi): GPRD totale, GPRD_ACT (atti), GPRD_THREAT
    (minacce) ed `event`, l'etichetta in inglese degli eventi principali."""
    r = requests.get(GPR_URL, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    d = pd.read_excel(BytesIO(r.content), sheet_name=0)
    d = d.dropna(subset=["DAY", "GPRD"])
    d.index = pd.to_datetime(d["DAY"].astype(int).astype(str), format="%Y%m%d")
    if d.empty:
        raise ValueError("il file del GPR è vuoto")
    return d[["GPRD", "GPRD_ACT", "GPRD_THREAT", "event"]].sort_index()


@st.cache_data(ttl=12 * 3600, show_spinner="Scarico i prezzi alla pompa in Italia…")
def scarica_pompa() -> pd.DataFrame:
    """Prezzi medi settimanali in Italia, euro al litro con tasse; indice = lunedì del listino."""
    r = requests.get(POMPA_URL, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    d = pd.read_parquet(BytesIO(r.content))
    d = d[d["country_code"] == "IT"]
    if d.empty:
        raise ValueError("nel file non ci sono prezzi per l'Italia")
    d.index = pd.to_datetime(d["week"])
    return d[["euro95_eur_l", "diesel_eur_l"]].rename(
        columns={"euro95_eur_l": "Benzina", "diesel_eur_l": "Gasolio"}).sort_index().astype(float)


def aggrega(base: pd.DataFrame, freq: str) -> pd.DataFrame:
    if freq == "Giorno per giorno":
        return base
    return base.resample("W-FRI").agg(
        {"usd": "last", "high": "max", "low": "min", "fx": "last", "eur": "last"}
    ).dropna()


def grafico(df: pd.DataFrame, titolo_y: str, barre: bool = False, colori: list[str] | None = None):
    """Grafico nel tempo con date in formato italiano (gg/mm/aa); una serie per colonna di `df`."""
    d = df.rename_axis("Data").reset_index().melt("Data", var_name="Serie", value_name="Valore").dropna()
    if barre:
        d = d[d["Valore"] != 0]
    colore = alt.Color("Serie:N", title=None, sort=list(df.columns), legend=alt.Legend(orient="bottom"),
                       scale=alt.Scale(domain=list(df.columns), range=colori) if colori else alt.Undefined)
    c = (alt.Chart(d).mark_bar() if barre else alt.Chart(d).mark_line()).encode(
        x=alt.X("Data:T", title=None, axis=alt.Axis(format="%d/%m/%y")),
        y=alt.Y("Valore:Q", title=titolo_y, scale=alt.Scale(zero=barre)),
        color=colore,
        tooltip=[alt.Tooltip("Data:T", title="Data", format="%d/%m/%Y"), alt.Tooltip("Serie:N", title="Serie"),
                 alt.Tooltip("Valore:Q", title="Valore", format=".2f")],
    )
    st.altair_chart(c, width="stretch")


# --------------------------------------------------------------------------
# Barra laterale
# --------------------------------------------------------------------------
sb = st.sidebar
n = sb.slider("Confronta con il prezzo di quanti giorni fa", 1, 60, 7)
mesi = sb.selectbox("Periodo mostrato nel grafico", ["1 mese", "3 mesi", "6 mesi", "1 anno", "5 anni", "Tutto lo storico"],
                    index=1)
giorni_grafico = {"1 mese": 30, "3 mesi": 91, "6 mesi": 182, "1 anno": 365, "5 anni": 1826,
                  "Tutto lo storico": 100_000}[mesi]
if sb.button("Aggiorna i prezzi"):
    st.cache_data.clear()

sb.divider()
sb.subheader("Impostazioni dell'analisi")
freq = sb.radio("Raggruppa i prezzi", ["Giorno per giorno", "Settimana per settimana"])
unita = "giorni" if freq == "Giorno per giorno" else "settimane"
N = sb.slider(f"Quanti {unita} analizzare (i più recenti)", 20, 500, 120)
w = sb.slider(f"Ampiezza della finestra mobile ({unita})", 5, 60, 20,
              help="Quanti periodi consecutivi si guardano insieme per calcolare «chi anticipa chi».")
orizzonte = sb.slider(f"Quanto avanti prevedere ({unita})", 1, 20, 5)
soglia = sb.number_input("Rialzo minimo da prevedere (%)", value=0.0, step=0.5,
                         help="0% = basta che il prezzo salga; 2% = deve salire di più del 2%.")
usa_meteo = sb.checkbox("Usa la temperatura in Europa", value=True,
                        help=f"Media di {', '.join(CITTA)}, da Open-Meteo. Serve per la scheda «Meteo» e per "
                             "provare se il caldo o il freddo aiutano a prevedere il prezzo.")
usa_ovx = sb.checkbox("Usa la volatilità attesa dal mercato (OVX)", value=True,
                      help="L'indice OVX misura quanto gli operatori si aspettano che il petrolio oscilli nei prossimi "
                           "30 giorni, ricavato dai prezzi delle opzioni. Viene aggiunto alle previsioni.")
usa_gpr = sb.checkbox("Usa il rischio geopolitico (GPR)", value=True,
                      help="Il Geopolitical Risk Index conta gli articoli di giornale su guerre, terrorismo e tensioni "
                           "internazionali. Serve per la scheda «Geopolitica» e viene aggiunto alle previsioni.")
usa_pompa = sb.checkbox("Usa i prezzi alla pompa in Italia", value=True,
                        help="Prezzi medi settimanali di benzina e gasolio in Italia, dal Weekly Oil Bulletin della "
                             "Commissione Europea. Servono per la scheda «Pompa (Italia)» e per verificare lo score.")

sb.divider()
sb.subheader("Score rifornimento")
alpha_s = sb.slider("Sensibilità alla turbolenza (α)", 0.0, 2.0, 1.0, 0.1,
                    help="Quanto lo score si avvicina a «neutro» quando il mercato è più agitato del normale. "
                         "0 = nessuno smorzamento; il PDF dello SCORE 4.0 suggerisce valori fra 0.5 e 1.2.")
theta_s = sb.slider("Soglia (θ)", 0.25, 3.0, 1.0, 0.25,
                    help="Di quante oscillazioni tipiche il Brent deve allontanarsi dalla media dei 30 giorni per "
                         "dare +1 o −1. Più alta = segnali più rari ma più netti.")

# --------------------------------------------------------------------------
# Dati
# --------------------------------------------------------------------------
try:
    b, f = scarica(dati.BRENT), scarica(dati.EURUSD)
except Exception as e:
    st.error(f"Non sono riuscito a scaricare i prezzi: {e}")
    st.stop()

base = dati.costruisci_base(b, f)

t = base.index[-1]
tn = t - pd.Timedelta(days=n)
if tn < base.index[0]:
    st.error("I prezzi scaricati non arrivano così indietro nel tempo.")
    st.stop()
data_prima = base.index[base.index <= tn][-1]
ora, prima = base.loc[t], base.loc[data_prima]
d_usd = ora["usd"] / prima["usd"] - 1
d_eur = ora["eur"] / prima["eur"] - 1
d_clip = max(-0.10, min(0.10, d_eur))

# Temperatura rispetto al normale stagionale (°C); None se disattivata o non disponibile.
anomalia, errore_meteo = None, None
if SOLO_SCORE:  # meteo e rischio geopolitico non servono allo score
    usa_meteo = usa_gpr = False
if usa_meteo:
    try:
        anomalia = bm.anomalia_stagionale(scarica_meteo(base.index[0], t))
    except Exception as e:
        errore_meteo = str(e)

# Volatilità attesa dal mercato (OVX, % annuo); None se disattivata o non disponibile.
ovx_serie, errore_ovx = None, None
if usa_ovx:
    try:
        ovx_serie = scarica(dati.OVX)["Close"]
    except Exception as e:
        errore_ovx = str(e)

# Prezzi settimanali alla pompa in Italia; None se disattivati o non disponibili.
pompa_df, errore_pompa = None, None
if usa_pompa:
    try:
        pompa_df = scarica_pompa()
    except Exception as e:
        errore_pompa = str(e)

# Rischio geopolitico giornaliero; None se disattivato o non disponibile.
gpr_df, errore_gpr = None, None
if usa_gpr:
    try:
        gpr_df = scarica_gpr()
    except Exception as e:
        errore_gpr = str(e)

if SOLO_SCORE:
    tab_score = st.container(key="card-score")  # scheda bianca, come nella versione con le schede
else:
    tab1, tab_score, tab_prev, tab_pompa, tab2, tab3, tab_geo, tab4, tab5 = st.tabs(
        ["Prezzo", "Score rifornimento", "Prossimi 5 giorni", "Pompa (Italia)", "Andamento", "Meteo", "Geopolitica",
         "Prova di previsione", "Oscillazione attesa"])

# --------------------------------------------------------------------------
# Scheda 1 - Prezzo
# --------------------------------------------------------------------------
if not SOLO_SCORE:
    with tab1:
        st.caption(f"Ultimo prezzo di chiusura: {t:%d/%m/%Y} · confrontato con il {data_prima:%d/%m/%Y}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Brent in dollari", f"{ora['usd']:.2f} $ al barile", f"{d_usd:+.2%}")
        c2.metric("Brent in euro", f"{ora['eur']:.2f} € al barile", f"{d_eur:+.2%}")
        c3.metric("Variazione in euro, limitata a ±10%", f"{d_clip:+.2%}",
                  help="La stessa variazione del prezzo in euro, ma tagliata a ±10% "
                       "per non dare troppo peso ai salti eccezionali.")
        dati_grafico = base.loc[base.index >= t - pd.Timedelta(days=giorni_grafico), ["usd", "eur"]]
        grafico(dati_grafico.rename(columns={"usd": "Dollari al barile", "eur": "Euro al barile"}), "Prezzo al barile")
        st.caption("Fonte: Yahoo Finance. I prezzi possono arrivare in ritardo e non sono un consiglio di investimento. "
                   "Un barile sono 159 litri di petrolio greggio.")

# --------------------------------------------------------------------------
# Serie nei periodi scelti
# --------------------------------------------------------------------------
def serie(freq: str):
    """Prezzi raggruppati per `freq` e serie allineate: x = ln prezzo in euro, y = agitazione
    (ln(1 + escursione % fra massimo e minimo)), m = temperatura rispetto al normale,
    o = ln volatilità attesa per periodo dall'OVX, g = ln rischio geopolitico (media degli ultimi 7 giorni di
    calendario, o della settimana) (m, o e g None se non disponibili)."""
    bins = aggrega(base, freq)
    x = np.log(bins["eur"].to_numpy())
    y = np.log1p(100 * (bins["high"] / bins["low"] - 1)).to_numpy()
    m = None
    if anomalia is not None:
        m_bin = anomalia if freq == "Giorno per giorno" else anomalia.resample("W-FRI").mean()
        m = m_bin.reindex(bins.index).to_numpy()
    o = None
    if ovx_serie is not None and freq == "Giorno per giorno":
        o = dati.ovx_giornaliero(ovx_serie, bins.index)
    elif ovx_serie is not None:
        o_bin = ovx_serie.reindex(base.index, method="ffill", limit=5).resample("W-FRI").last()
        o = np.log(o_bin.reindex(bins.index).to_numpy() / 100 / np.sqrt(52))
    g = None
    if gpr_df is not None:
        gd = gpr_df["GPRD"]
        g_bin = (gd.rolling("7D").mean().reindex(bins.index, method="ffill", limit=10) if freq == "Giorno per giorno"
                 else gd.resample("W-FRI").mean().reindex(bins.index))
        g = np.log(g_bin.clip(lower=1).to_numpy())
    return bins, x, y, m, o, g


bins, x, y, m, o, g = serie(freq)
periodi_anno = 252 if freq == "Giorno per giorno" else 52

# --------------------------------------------------------------------------
# Scheda «Prossimi 5 giorni» - sempre giorno per giorno, indipendente da «Raggruppa i prezzi»
# --------------------------------------------------------------------------
GIORNI_PREV, FINESTRA_PREV = 5, 20
# Score e oscillazione attesa giorno per giorno, usati da «Score rifornimento» e «Prossimi 5 giorni»: è lo stesso
# calcolo che esporta_score.py scrive in Supabase.
o_g = dati.ovx_giornaliero(ovx_serie, base.index) if ovx_serie is not None else None
try:
    sc, modello_g = bm.score_storico(base, o_g, alpha_s, theta_s, FINESTRA_PREV, GIORNI_PREV)
    sig = float(sc["sigma"].iloc[-1])                                   # oscillazione attesa al giorno (frazione)
    errore_sig = None
except Exception as e:
    sc, sig, errore_sig = None, None, str(e)
    modello_g = "+ agitazione e OVX" if o_g is not None else "+ agitazione"


with tab_score:
    st.subheader("Conviene fare rifornimento adesso?")
    if errore_sig is not None:
        st.error(f"Non riesco a calcolare lo score: {errore_sig}")
    else:
        oggi = sc.iloc[-1]
        classe = int(oggi["classe"])
        testo = {
            1: ("+1 · Rifornisci", "Il Brent è sopra la media degli ultimi 30 giorni più di quanto spieghi il suo "
                "normale oscillare: i prezzi alla pompa tendono a seguirlo con qualche giorno di ritardo, quindi "
                "conviene fare il pieno prima che salgano."),
            0: ("0 · Neutro", "Il Brent è vicino alla sua media degli ultimi 30 giorni, oppure il mercato è troppo "
                "agitato per fidarsi dello scarto: nessuna indicazione, rifornisci quando ti serve."),
            -1: ("−1 · Aspetta", "Il Brent è sotto la media degli ultimi 30 giorni più di quanto spieghi il suo "
                 "normale oscillare: i prezzi alla pompa tendono a scendere nei prossimi giorni, quindi se puoi "
                 "conviene aspettare."),
        }[classe]
        {1: st.success, 0: st.info, -1: st.warning}[classe](f"**{testo[0]}** — {testo[1]}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Score S", f"{oggi['S']:+.2f}", help=f"+1 da {theta_s:+.2f} in su, −1 da {-theta_s:+.2f} in giù.")
        c2.metric("Brent rispetto alla media 30 giorni", f"{100 * (np.exp(oggi['scarto']) - 1):+.1f}%",
                  help=f"Oggi {oggi['prezzo']:.2f} € al barile, media degli ultimi 30 giorni {oggi['media']:.2f} €.")
        c3.metric("Oscillazione attesa in 5 giorni", f"±{100 * oggi['sigma'] * np.sqrt(GIORNI_PREV):.1f}%",
                  help="Il «rumore normale» con cui si confronta lo scarto dalla media.")
        c4.metric("Stabilità", f"{oggi['stabilita']:.2f}",
                  help="1 = mercato calmo, segnale pieno. Sotto 1 il mercato è più agitato del normale e lo score "
                       "viene avvicinato a zero.")

        st.latex(r"S=\frac{\ln\left(P_t/\bar P_{30}\right)}{\sigma\sqrt{5}}\cdot e^{-\alpha\,\max\left(0,\;"
                 r"\sigma/\sigma_{norm}-1\right)}")
        st.caption(
            "Adattamento dello SCORE 4.0: il rapporto fra prezzo di oggi e media dei 30 giorni prende il posto del "
            "rapporto fra tempo di riferimento e tempo effettivo; la divisione per l'oscillazione attesa in 5 giorni "
            "(σ√5) fa da normalizzazione; il fattore esponenziale è la stabilità, fra 0 e 1. "
            f"Con α = {alpha_s:.1f} e θ = {theta_s:.2f}."
        )

        inizio_s = t - pd.Timedelta(days=giorni_grafico)
        d_s = sc.loc[inizio_s:, ["S", "classe"]].dropna().rename_axis("Data").reset_index()
        if len(d_s):
            d_s["Esito"] = d_s["classe"].map({1: "+1 rifornisci", 0: "0 neutro", -1: "−1 aspetta"})
            asse = alt.X("Data:T", title=None, axis=alt.Axis(format="%d/%m/%y"))
            punti = alt.Chart(d_s).mark_circle(size=28).encode(
                x=asse, y=alt.Y("S:Q", title="Score S"),
                color=alt.Color("Esito:N", title=None, legend=alt.Legend(orient="bottom"),
                                scale=alt.Scale(domain=["+1 rifornisci", "0 neutro", "−1 aspetta"],
                                                range=[style.VERDE, style.ORANGE, style.ROSSO])),
                tooltip=[alt.Tooltip("Data:T", title="Data", format="%d/%m/%Y"), alt.Tooltip("S:Q", format="+.2f"),
                         alt.Tooltip("Esito:N")])
            linea = alt.Chart(d_s).mark_line(color=style.N400, strokeWidth=1).encode(x=asse, y="S:Q")
            soglie = alt.Chart(pd.DataFrame({"y": [theta_s, -theta_s]})).mark_rule(strokeDash=[4, 4], color=style.N500
                                                                                 ).encode(y="y:Q")
            st.altair_chart(linea + punti + soglie, width="stretch")
            st.caption("Lo score negli ultimi mesi; le linee tratteggiate sono le soglie ±θ.")

        st.markdown("**Ha funzionato in passato?** Cosa ha fatto il Brent nei 5 giorni di borsa dopo ogni esito "
                    "(con l'oscillazione attesa calcolata ogni volta senza guardare il futuro).")
        ver = bm.verifica_score(sc, GIORNI_PREV).assign(
            Classe=lambda d: d["Classe"].map({"+1": "+1 rifornisci", "0": "0 neutro", "-1": "−1 aspetta",
                                              "Tutti": "Tutti i giorni"}),
            Quota=lambda d: 100 * d["Quota"], **{"Giorni in salita": lambda d: 100 * d["Giorni in salita"]})
        st.dataframe(
            ver.rename(columns={"Classe": "Esito", "Quota": "Quota dei giorni (%)",
                                "Variazione media": "Brent nei 5 giorni dopo (%)",
                                "Giorni in salita": "Volte in cui è salito (%)"}),
            hide_index=True,
            column_config={"Quota dei giorni (%)": st.column_config.NumberColumn(format="%.0f"),
                           "Brent nei 5 giorni dopo (%)": st.column_config.NumberColumn(format="%+.2f"),
                           "Volte in cui è salito (%)": st.column_config.NumberColumn(format="%.0f")},
        )
        periodo = sc["S"].dropna()
        st.caption(
            f"Dal {periodo.index[0]:%d/%m/%Y} al {periodo.index[-1]:%d/%m/%Y}. Con la logica dello score ci si aspetta "
            "che dopo un +1 il Brent salga più spesso della media di tutti i giorni, e dopo un −1 meno spesso: "
            "così il segnale anticipa la pompa ancora di più. Questa prova guarda solo il Brent: quanto si risparmia "
            "davvero lo dice la verifica con i prezzi alla pompa qui sotto. Non è un consiglio di investimento."
        )


        st.markdown("**Verifica con i prezzi alla pompa in Italia**")
        if pompa_df is None:
            st.info("Attiva «Usa i prezzi alla pompa in Italia» nella barra laterale per questa verifica."
                    if not usa_pompa else f"Prezzi alla pompa non disponibili: {errore_pompa}")
        else:
            classe_sett = sc["classe"].reindex(pompa_df.index, method="ffill")
            tab_v, risp = bm.verifica_score_pompa(classe_sett.dropna(), pompa_df.loc[classe_sett.dropna().index])
            st.dataframe(
                tab_v.assign(Classe=lambda d: d["Classe"].map({"+1": "+1 rifornisci", "0": "0 neutro",
                                                               "-1": "−1 aspetta", "Tutte": "Tutte le settimane"}))
                .rename(columns={"Classe": "Esito", "Benzina dopo 1": "Benzina dopo 1 settimana",
                                 "Benzina dopo 2": "Benzina dopo 2 settimane", "Gasolio dopo 1": "Gasolio dopo 1 settimana",
                                 "Gasolio dopo 2": "Gasolio dopo 2 settimane"}),
                hide_index=True,
                column_config={c: st.column_config.NumberColumn(format="%+.2f", help="Variazione media del prezzo alla "
                                                                "pompa, in centesimi al litro")
                               for c in ["Benzina dopo 1 settimana", "Benzina dopo 2 settimane",
                                         "Gasolio dopo 1 settimana", "Gasolio dopo 2 settimane"]},
            )
            r = risp.assign(**{"Volte in cui ha fatto risparmiare": 100 * risp["Volte in cui ha fatto risparmiare"],
                               "Settimane": risp["Settimane"].map({1: "1 settimana", 2: "2 settimane"})})
            st.dataframe(
                r.rename(columns={"Settimane": "Confronto con", "Segnali": "Settimane con +1 o −1",
                                  "Volte in cui ha fatto risparmiare": "Volte in cui ha fatto risparmiare (%)"}),
                hide_index=True,
                column_config={"Risparmio medio (€ per pieno)": st.column_config.NumberColumn(format="%+.2f €"),
                               "Volte in cui ha fatto risparmiare (%)": st.column_config.NumberColumn(format="%.0f")},
            )
            st.caption(
                "La prima tabella dice come è cambiato il prezzo medio italiano alla pompa nelle settimane dopo ogni "
                "esito (lo score è quello del lunedì del listino). Lo score funziona se dopo un +1 la pompa sale e "
                "dopo un −1 scende. La seconda tabella traduce tutto in euro per un pieno da 50 litri: seguendo lo "
                "score (+1 = fare il pieno subito invece che dopo 1 o 2 settimane, −1 = aspettare) quanto si è "
                "risparmiato in media, e quante volte. Un valore positivo vuol dire che lo score ha fatto risparmiare."
            )

if SOLO_SCORE:  # versione incorporata: le altre schede non servono
    st.stop()

with tab_pompa:
    st.subheader("Prezzi medi alla pompa in Italia")
    if not usa_pompa:
        st.info("I prezzi alla pompa sono disattivati: attiva «Usa i prezzi alla pompa in Italia» nella barra laterale.")
    elif pompa_df is None:
        st.warning(f"Non sono riuscito a scaricare i prezzi alla pompa: {errore_pompa}")
    else:
        ult, pen = pompa_df.iloc[-1], pompa_df.iloc[-2]
        c1, c2, c3 = st.columns(3)
        c1.metric("Benzina", f"{ult['Benzina']:.3f} € al litro", f"{100 * (ult['Benzina'] - pen['Benzina']):+.1f} cent",
                  delta_color="inverse")
        c2.metric("Gasolio", f"{ult['Gasolio']:.3f} € al litro", f"{100 * (ult['Gasolio'] - pen['Gasolio']):+.1f} cent",
                  delta_color="inverse")
        c3.metric("Listino del", f"{pompa_df.index[-1]:%d/%m/%Y}",
                  help="I prezzi sono quelli in vigore il lunedì; la Commissione li pubblica qualche giorno dopo.")
        inizio_p = t - pd.Timedelta(days=max(giorni_grafico, 182))
        grafico(pompa_df.loc[inizio_p:], "Euro al litro")
        brent_l = base["eur"].reindex(pompa_df.index, method="ffill") / LITRI_BARILE
        grafico(brent_l.loc[inizio_p:].rename("Brent (petrolio greggio)").to_frame(), "Euro al litro")
        st.caption("Sopra: prezzi medi nazionali con tutte le tasse. Sotto: il Brent convertito in euro al litro, cioè "
                   "il costo della sola materia prima. La differenza sono raffinazione, distribuzione, accise e IVA.")

        st.markdown("**Con quanto ritardo la pompa segue il Brent?**")
        rit = {c: bm.ritardo_pompa(brent_l, pompa_df[c]) for c in pompa_df.columns}
        tab_r = rit["Benzina"][["Ritardo (settimane)"]].copy()
        for c, d in rit.items():
            tab_r[f"{c}: correlazione"] = d["Correlazione"].values
            tab_r[f"{c}: quota trasferita"] = d["Quota trasferita"].values
        st.dataframe(tab_r, hide_index=True,
                     column_config={c: st.column_config.NumberColumn(format="%.2f") for c in tab_r.columns[1:]})
        frasi = []
        for c, d in rit.items():
            k = int(d.loc[d["Correlazione"].idxmax(), "Ritardo (settimane)"])
            frasi.append(f"{ {'Benzina': 'la benzina', 'Gasolio': 'il gasolio'}[c]} reagisce soprattutto dopo **{k} settiman{'a' if k == 1 else 'e'}** e, in "
                         f"tutto, trasferisce circa **{d['Quota trasferita'].clip(lower=0).sum():.2f}** centesimi per "
                         "ogni centesimo di Brent")
        st.markdown("In questi dati " + "; ".join(frasi) + ".")
        st.caption(
            "Per ogni ritardo, la tabella confronta la variazione del Brent in una settimana con quella della pompa "
            "dopo 0, 1, 2… settimane. La correlazione dice quanto i due movimenti vanno insieme; la quota trasferita "
            "dice quanti centesimi alla pompa segue ogni centesimo di Brent al litro. Fonte: EU Weekly Oil Bulletin, "
            "Commissione Europea, raccolto da [fuel-prices.eu](https://www.fuel-prices.eu/research/) (CC BY 4.0)."
        )

with tab_prev:
    st.subheader(f"Il prezzo nei prossimi {GIORNI_PREV} giorni di borsa")
    valuta = st.radio("Mostra in", ["Euro", "Dollari"], horizontal=True, key="valuta_prev")
    col_p, simbolo = ("eur", "€") if valuta == "Euro" else ("usd", "$")
    if errore_sig is not None:
        st.error(f"Non riesco a calcolare la previsione: {errore_sig}")
    else:
        p0 = float(ora[col_p])
        k = np.arange(GIORNI_PREV + 1)                                   # 0 = oggi, poi i giorni di borsa successivi
        date_f = pd.DatetimeIndex([t]).append(pd.bdate_range(t + pd.Timedelta(days=1), periods=GIORNI_PREV))
        fut = pd.DataFrame({"Data": date_f, "Centro": p0})
        for nome, z in (("68", 1.0), ("95", 1.96)):
            fut[f"min{nome}"] = p0 * np.exp(-z * sig * np.sqrt(k))
            fut[f"max{nome}"] = p0 * np.exp(z * sig * np.sqrt(k))

        c1, c2, c3 = st.columns(3)
        c1.metric(f"Prezzo al {t:%d/%m/%Y}", f"{p0:.2f} {simbolo} al barile")
        c2.metric("Oscillazione attesa", f"{100 * sig:.2f}% al giorno",
                  help=f"Dal modello «{NOMI_OSC[modello_g].removeprefix('Modello: ')}» della scheda «Oscillazione "
                       f"attesa», calcolato giorno per giorno sugli ultimi {FINESTRA_PREV} giorni.")
        ultimo = fut.iloc[-1]
        c3.metric(f"Il {ultimo['Data']:%d/%m}, in 2 casi su 3", f"{ultimo['min68']:.2f} – {ultimo['max68']:.2f} {simbolo}",
                  help="Intervallo in cui il prezzo dovrebbe trovarsi in circa 2 casi su 3 alla fine dei 5 giorni.")

        storico = base.loc[base.index >= t - pd.Timedelta(days=42), [col_p]].rename(columns={col_p: "Valore"})
        linee = pd.concat([
            storico.rename_axis("Data").reset_index().assign(Serie="Prezzo vero"),
            fut[["Data", "Centro"]].rename(columns={"Centro": "Valore"}).assign(Serie="Previsione"),
        ])
        asse_x = alt.X("Data:T", title=None, axis=alt.Axis(format="%d/%m/%y"))
        fascia = lambda nome, opacita: alt.Chart(fut).mark_area(opacity=opacita, color=style.BLUE_GREEN).encode(
            x=asse_x, y=alt.Y(f"min{nome}:Q"), y2=f"max{nome}:Q",
            tooltip=[alt.Tooltip("Data:T", title="Data", format="%d/%m/%Y"),
                     alt.Tooltip(f"min{nome}:Q", title="Da", format=".2f"),
                     alt.Tooltip(f"max{nome}:Q", title="A", format=".2f")])
        serie_l = alt.Chart(linee).mark_line().encode(
            x=asse_x,
            y=alt.Y("Valore:Q", title=f"{simbolo} al barile", scale=alt.Scale(zero=False)),
            color=alt.Color("Serie:N", title=None, legend=alt.Legend(orient="bottom"),
                            scale=alt.Scale(domain=["Prezzo vero", "Previsione"], range=[style.DEEP, style.BLUE_GREEN])),
            strokeDash=alt.StrokeDash("Serie:N", legend=None,
                                      scale=alt.Scale(domain=["Prezzo vero", "Previsione"], range=[[1, 0], [6, 4]])),
            tooltip=[alt.Tooltip("Data:T", title="Data", format="%d/%m/%Y"), alt.Tooltip("Serie:N", title="Serie"),
                     alt.Tooltip("Valore:Q", title=f"{simbolo} al barile", format=".2f")],
        )
        st.altair_chart(fascia("95", 0.12) + fascia("68", 0.25) + serie_l, width="stretch")

        tabella = fut.iloc[1:].assign(**{
            "Giorno": [f"{['lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom'][d.dayofweek]} {d:%d/%m}"
                       for d in fut["Data"].iloc[1:]],
            "Previsione": fut["Centro"].iloc[1:].map(f"{{:.2f}} {simbolo}".format),
            "2 casi su 3": [f"{a:.2f} – {b:.2f} {simbolo}" for a, b in zip(fut.min68.iloc[1:], fut.max68.iloc[1:])],
            "19 casi su 20": [f"{a:.2f} – {b:.2f} {simbolo}" for a, b in zip(fut.min95.iloc[1:], fut.max95.iloc[1:])],
        })[["Giorno", "Previsione", "2 casi su 3", "19 casi su 20"]]
        st.dataframe(tabella, hide_index=True)
        st.caption(
            "**Come leggerla.** La linea tratteggiata è la previsione centrale: resta al prezzo di oggi perché la "
            "direzione del Brent non si può prevedere dal passato (lo mostra la scheda «Prova di previsione»). Quello "
            "che si può prevedere è quanto il prezzo si muoverà: la fascia più scura è dove dovrebbe trovarsi in circa "
            "2 casi su 3, quella più chiara in circa 19 casi su 20. La fascia si allarga perché più si guarda avanti, "
            "più il prezzo ha tempo per allontanarsi. Non tiene conto delle festività di borsa e non è un consiglio "
            "di investimento."
        )

# --------------------------------------------------------------------------
# Scheda 2 - Andamento
# --------------------------------------------------------------------------
with tab2:
    xn = x[-(N + 1):]
    h = 100 * bm.altezze(xn)                                         # variazioni percentuali (logaritmiche)
    idx = bins.index[-len(h):]
    ag = bm.aggregati(h)

    st.subheader("Di quanto è salito o sceso il prezzo in ogni periodo")
    st.caption("Ogni barra è la variazione percentuale del prezzo in euro rispetto al periodo prima. "
               "Verde = salita, rosso = discesa.")
    grafico(pd.DataFrame({"Salita": np.clip(h, 0, None), "Discesa": np.clip(h, None, 0)}, index=idx),
            "Variazione (%)", barre=True, colori=[style.VERDE, style.ROSSO])

    cA, cB = st.columns([1, 1])
    with cA:
        st.markdown(f"**Riepilogo degli ultimi {N} {unita}**")
        tab = pd.DataFrame(
            {
                "Misura": ["Movimento complessivo (salite + discese)", "Totale delle salite", "Totale delle discese",
                           "Variazione tipica in un periodo", "Salita più grande", "Discesa più grande",
                           "Variazione dall'inizio alla fine"],
                "Valore (%)": [ag["variazione_totale"], ag["parte_positiva"], ag["parte_negativa"], ag["rms"],
                               ag["salto_max"], ag["salto_min"], ag["net"]],
            }
        )
        st.dataframe(tab, hide_index=True, column_config={"Valore (%)": st.column_config.NumberColumn(format="%+.2f")})
    with cB:
        eff = bm.efficienza_percorso(h)
        daily = 100 * np.diff(np.log(base["eur"].to_numpy()))
        sigma = float(np.sqrt(np.mean(daily[-60:] ** 2)))
        k = int(((base.index > data_prima) & (base.index <= t)).sum())
        z = (100 * np.log(ora["eur"] / prima["eur"])) / (sigma * np.sqrt(k)) if sigma > 0 and k > 0 else float("nan")
        st.metric("Quanto è stato lineare l'andamento", f"{eff:.2f}",
                  help="Da 0 a 1. Vicino a 1: il prezzo è andato dritto in una direzione. "
                       "Vicino a 0: è salito e sceso molto, ma alla fine si è spostato poco.")
        st.metric(f"Forza della variazione degli ultimi {n} giorni", f"{z:+.2f} volte il normale",
                  help="La variazione di questi giorni confrontata con l'oscillazione abituale del prezzo "
                       "(calcolata sugli ultimi 60 giorni di borsa). Fra −1 e +1 è normale amministrazione; "
                       "oltre ±2 è un movimento forte.")
        st.caption(
            "La sola differenza fra inizio e fine non dice come ci si è arrivati: un periodo calmo e uno molto "
            "agitato possono finire allo stesso prezzo. Il movimento complessivo, la variazione tipica e la "
            "linearità descrivono proprio il percorso."
        )

    st.subheader("Chi anticipa chi: il prezzo o l'agitazione del mercato?")
    A = bm.area_levy_mobile(x, y, w)
    serie_A = pd.Series(A, index=bins.index).iloc[-N:]
    grafico(serie_A.rename("Indice di anticipo").to_frame(), "Indice di anticipo")
    ultimo = serie_A.dropna()
    st.metric("Valore più recente", f"{ultimo.iloc[-1]:+.2f}" if len(ultimo) else "non disponibile")
    st.caption(
        "L'«agitazione» è quanto il prezzo oscilla dentro lo stesso periodo (distanza fra massimo e minimo). "
        f"L'indice confronta, sugli ultimi {w} {unita} di volta in volta, l'ordine in cui si muovono prezzo e "
        "agitazione. **Sopra zero: si muove prima il prezzo e poi l'agitazione. Sotto zero: prima l'agitazione e "
        "poi il prezzo.** Vicino a zero: nessuno dei due anticipa l'altro. (Tecnicamente è l'«area di Lévy».)"
    )

# --------------------------------------------------------------------------
# Scheda 3 - Meteo
# --------------------------------------------------------------------------
with tab3:
    st.subheader("Fa più caldo o più freddo del normale in Europa?")
    if not usa_meteo:
        st.info("La temperatura è disattivata: attiva «Usa la temperatura in Europa» nella barra laterale.")
    elif anomalia is None:
        st.warning(f"Non sono riuscito a scaricare le temperature da Open-Meteo: {errore_meteo}")
    else:
        c1, c2 = st.columns(2)
        c1.metric(f"Ultimo giorno ({anomalia.index[-1]:%d/%m/%Y})", f"{anomalia.iloc[-1]:+.1f} °C rispetto al normale")
        c2.metric("Media degli ultimi 30 giorni", f"{anomalia.iloc[-30:].mean():+.1f} °C rispetto al normale")
        inizio_g = t - pd.Timedelta(days=giorni_grafico)
        grafico(anomalia.rolling(7, min_periods=4).mean().loc[inizio_g:].rename("Media su 7 giorni").to_frame(),
                "°C rispetto al normale")
        grafico(base.loc[inizio_g:, ["eur"]].rename(columns={"eur": "Euro al barile"}), "Prezzo al barile")
        st.caption(
            f"Temperatura media di {', '.join(CITTA)}. Il «normale» è la media dello stesso periodo dell'anno dal "
            f"{anomalia.index[0].year} a oggi: sopra zero fa più caldo del solito, sotto zero più freddo. In teoria un inverno più freddo "
            "fa consumare più gasolio da riscaldamento e può spingere il prezzo; la scheda «Prova di previsione» "
            "verifica se succede davvero. Dati meteo: [Open-Meteo.com](https://open-meteo.com) (licenza CC BY 4.0)."
        )

# --------------------------------------------------------------------------
# Scheda «Geopolitica»
# --------------------------------------------------------------------------
with tab_geo:
    st.subheader("Quanto è alto il rischio geopolitico?")
    if not usa_gpr:
        st.info("Il rischio geopolitico è disattivato: attiva «Usa il rischio geopolitico (GPR)» nella barra laterale.")
    elif gpr_df is None:
        st.warning(f"Non sono riuscito a scaricare il rischio geopolitico (GPR): {errore_gpr}")
    else:
        gd = gpr_df["GPRD"]
        ultimo_g = gd.index[-1]
        c1, c2, c3 = st.columns(3)
        c1.metric(f"Media degli ultimi 7 giorni (al {ultimo_g:%d/%m/%Y})", f"{gd.iloc[-7:].mean():.0f}",
                  help="100 è il livello medio dal 1985 al 2019. 200 vuol dire il doppio degli articoli sul tema.")
        c2.metric("Media degli ultimi 30 giorni", f"{gd.iloc[-30:].mean():.0f}")
        c3.metric("Minacce / atti (30 giorni)",
                  f"{gpr_df['GPRD_THREAT'].iloc[-30:].mean():.0f} / {gpr_df['GPRD_ACT'].iloc[-30:].mean():.0f}",
                  help="Il GPR si divide in minacce (tensioni, avvertimenti, rischio di guerra) e atti (attacchi, "
                       "guerre in corso). Entrambi in scala 100 = media 1985–2019.")
        inizio_g = t - pd.Timedelta(days=giorni_grafico)
        grafico(gd.rolling("30D").mean().loc[inizio_g:].rename("Media su 30 giorni").to_frame()
                .join(gd.rolling("7D").mean().loc[inizio_g:].rename("Media su 7 giorni")), "Indice (100 = normale)")
        grafico(base.loc[inizio_g:, ["eur"]].rename(columns={"eur": "Euro al barile"}), "Prezzo al barile")
        eventi = gpr_df.loc[gpr_df["event"].notna() & (gpr_df["event"].astype(str).str.strip() != ""), ["event", "GPRD"]]
        if len(eventi):
            st.markdown("**Eventi principali più recenti** (etichette originali in inglese)")
            st.dataframe(
                eventi.iloc[::-1].head(10).rename_axis("Data").reset_index()
                .assign(Data=lambda d: d["Data"].dt.strftime("%d/%m/%Y"))
                .rename(columns={"event": "Evento", "GPRD": "GPR del giorno"}),
                hide_index=True, column_config={"GPR del giorno": st.column_config.NumberColumn(format="%.0f")},
            )
        st.caption(
            "Il Geopolitical Risk Index conta, ogni giorno, la quota di articoli di 10 grandi giornali che parlano di "
            "guerre, terrorismo e tensioni fra Paesi. Le crisi in Medio Oriente o fra produttori di petrolio possono "
            "far salire il prezzo o renderlo più agitato; le schede «Prova di previsione» e «Oscillazione attesa» "
            "verificano se succede davvero. Il file è aggiornato dagli autori con qualche giorno di ritardo. Fonte: "
            "D. Caldara e M. Iacoviello, «Measuring Geopolitical Risk», American Economic Review, 2022, dati da "
            "[matteoiacoviello.com](https://www.matteoiacoviello.com/gpr.htm)."
        )

# --------------------------------------------------------------------------
# Scheda 4 - Prova di previsione
# --------------------------------------------------------------------------
with tab4:
    passo = 21 if freq == "Giorno per giorno" else 4  # circa un mese
    st.subheader("L'andamento passato aiuta a prevedere il prezzo?")
    st.markdown(
        f"Domanda: il prezzo in euro salirà di oltre **{soglia:.1f}%** nei prossimi **{orizzonte} {unita}**? "
        "La prova procede **a finestre scorrevoli**, come se il modello fosse usato davvero nel tempo: il primo 40% "
        f"dello storico serve solo per imparare; poi, ogni {passo} {unita} (circa un mese), il modello si riaddestra "
        "su tutto il passato disponibile e prevede il mese successivo, che non ha mai visto. Il confronto è con una "
        "**stima di riferimento** che non guarda il passato recente e dà sempre la stessa probabilità: quanto spesso "
        "il prezzo è salito fino a quel momento."
    )
    st.markdown(
        f"**Oscillazione (sigma e MAD)**: quanto il prezzo si è mosso negli ultimi {w} {unita}. *Sigma* è "
        "l'oscillazione tipica; *MAD* è la stessa idea ma non si lascia influenzare da un singolo salto. Non dicono se "
        "il prezzo salirà o scenderà, ma quanto è probabile un movimento grande: contano soprattutto quando il "
        "«rialzo minimo da prevedere» è sopra lo 0%."
        + (f" **Temperatura**: media della temperatura rispetto al normale sugli ultimi {w} {unita}."
           if m is not None else "")
        + (" **OVX**: quanto il mercato si aspetta che il petrolio oscilli nei prossimi 30 giorni."
           if o is not None else "")
        + (" **GPR**: rischio geopolitico, media degli ultimi 7 giorni." if g is not None else "")
    )
    if st.button("Esegui la prova"):
        try:
            with st.spinner("Eseguo la prova su tutto lo storico…"):
                feat = bm.costruisci_features(x, y, w, orizzonte, meteo=m, ovx=o, gpr=g)
                res, meta = bm.validazione(feat, orizzonte, soglia / 100, passo=passo,
                                           anni=bins.index[feat["t"].to_numpy()].year)
        except Exception as e:
            st.error(str(e))
        else:
            res = res.assign(**{
                "Insieme di predittori": res["Insieme di predittori"].map(NOMI_INSIEMI),
                "Skill": 100 * res["Skill"],
                "Anni vinti": res["Anni vinti"].astype(str) + " su " + res["Anni"].astype(str),
            }).drop(columns="Anni").rename(columns={
                "Insieme di predittori": "Dati usati per prevedere",
                "Brier": "Errore medio",
                "Skill": "Miglioramento sul riferimento (%)",
                "AUC": "Capacità di distinguere",
                "Anni vinti": "Anni in cui fa meglio",
            })
            st.dataframe(
                res, hide_index=True,
                column_config={
                    "Errore medio": st.column_config.NumberColumn(
                        format="%.4f", help="Più è basso meglio è (punteggio di Brier)."),
                    "Miglioramento sul riferimento (%)": st.column_config.NumberColumn(
                        format="%+.1f", help="Positivo: il modello sbaglia meno della stima di riferimento. "
                                             "Negativo: sbaglia di più."),
                    "Capacità di distinguere": st.column_config.NumberColumn(
                        format="%.3f", help="0.5 = come tirare a indovinare; 1 = distingue sempre i rialzi "
                                            "dai non-rialzi (AUC)."),
                    "Anni in cui fa meglio": st.column_config.TextColumn(
                        help="In quanti anni del periodo di verifica il modello sbaglia meno della stima di "
                             "riferimento. Un modello utile vince nella maggior parte degli anni, non solo in media."),
                },
            )
            st.caption(
                f"Periodo di verifica: dal {bins.index[meta['primo_test']]:%d/%m/%Y} al "
                f"{bins.index[meta['ultimo_test']]:%d/%m/%Y}, {meta['n_test']} casi di cui {meta['pos_test']} con "
                f"rialzo ({meta['base_rate']:.1%}) · modello riaddestrato {meta['n_passi']} volte · errore medio della "
                f"stima di riferimento {meta['brier_base']:.4f} · con questi casi la «capacità di distinguere» può "
                f"scostarsi da 0.5 per puro caso fino a circa ±{2 * meta['auc_se']:.3f}"
            )
            migliore = res.loc[res["Miglioramento sul riferimento (%)"].idxmax()]
            vinti, anni_tot = (int(v) for v in migliore["Anni in cui fa meglio"].split(" su "))
            if (res["Miglioramento sul riferimento (%)"] <= 0).all():
                st.warning("Nessun gruppo di dati fa meglio della stima di riferimento: su questi prezzi l'andamento "
                           "recente non aiuta a prevedere quello futuro.")
            elif migliore["Capacità di distinguere"] - 0.5 > 2 * meta["auc_se"] and vinti > anni_tot / 2:
                st.success(f"«{migliore['Dati usati per prevedere']}» fa meglio della stima di riferimento, più di "
                           f"quanto il caso da solo spiegherebbe, e ci riesce in {vinti} anni su {anni_tot}.")
            else:
                st.info("Qualche gruppo di dati fa un po' meglio della stima di riferimento, ma di poco o solo in "
                        "alcuni anni: potrebbe essere fortuna, non una vera capacità di previsione.")
    st.caption(
        "Attenzione: i periodi vicini si sovrappongono (il rialzo dei prossimi giorni è in gran parte lo stesso per "
        f"oggi e per domani), quindi i casi davvero indipendenti sono circa uno ogni {orizzonte} {unita}. "
        "Inoltre il Brent quotato è un contratto con scadenza mensile: quando si passa da un contratto al "
        "successivo il prezzo fa piccoli salti che non sono veri movimenti del mercato."
    )

# --------------------------------------------------------------------------
# Scheda 5 - Oscillazione attesa
# --------------------------------------------------------------------------
with tab5:
    passo = 21 if freq == "Giorno per giorno" else 4  # circa un mese
    al_periodo = "al giorno" if freq == "Giorno per giorno" else "alla settimana"
    st.subheader(f"Quanto si muoverà il prezzo nei prossimi {orizzonte} {unita}?")
    st.markdown(
        "Prevedere se il prezzo salirà o scenderà è quasi impossibile; prevedere **quanto si muoverà** è molto più "
        "fattibile, perché i periodi agitati tendono a durare. Il modello usa l'oscillazione recente (*sigma* e *MAD*, "
        f"sugli ultimi {w} {unita} e sugli ultimi 5) e l'agitazione, cioè la distanza fra massimo e minimo"
        + (", più la volatilità attesa dal mercato (OVX)" if o is not None else "")
        + (". Nella prova c'è anche un modello con il rischio geopolitico (GPR)." if g is not None else ".")
    )
    if usa_ovx and o is None:
        st.warning(f"Non sono riuscito a scaricare l'OVX, continuo senza: {errore_ovx}")
    feat_osc = bm.costruisci_features_oscillazione(x, y, w, orizzonte, meteo=m, ovx=o, gpr=g)
    try:
        cols_oggi = bm.INSIEMI_OSC["+ agitazione e OVX" if o is not None else "+ agitazione"]
        attesa = 100 * bm.prevedi_oscillazione(feat_osc, cols_oggi)
    except Exception as e:
        st.error(str(e))
    else:
        normale = 100 * float(np.exp(feat_osc["bersaglio"].median()))
        escursione = attesa * np.sqrt(orizzonte)
        c1, c2, c3 = st.columns(3)
        c1.metric("Oscillazione attesa", f"{attesa:.2f}% {al_periodo}",
                  f"{attesa - normale:+.2f} punti rispetto al normale", delta_color="inverse",
                  help=f"Il normale è l'oscillazione tipica (mediana) di tutto lo storico: {normale:.2f}% {al_periodo}.")
        c2.metric(f"Movimento probabile in {orizzonte} {unita}", f"±{escursione:.1f}%",
                  help="In circa 2 casi su 3 la variazione complessiva del prezzo resta dentro questo intervallo; "
                       "nel restante terzo va oltre, in su o in giù.")
        c3.metric("In euro al barile", f"±{ora['eur'] * escursione / 100:.2f} €",
                  help=f"Lo stesso intervallo applicato al prezzo attuale di {ora['eur']:.2f} € al barile.")
        if ovx_serie is not None:
            ovx_oggi = ovx_serie.dropna()
            st.caption(
                f"OVX al {ovx_oggi.index[-1]:%d/%m/%Y}: **{ovx_oggi.iloc[-1]:.1f}**, cioè il mercato si aspetta "
                f"un'oscillazione di circa {ovx_oggi.iloc[-1] / np.sqrt(periodi_anno):.2f}% {al_periodo}. "
                "L'OVX è calcolato sulle opzioni del petrolio WTI americano, che si muove quasi insieme al Brent. "
                "La previsione in alto usa il modello «+ agitazione e OVX»."
            )

    st.markdown("**Quanto è affidabile?** La prova usa le stesse finestre scorrevoli della scheda «Prova di "
                "previsione» e confronta i modelli con riferimenti semplici.")
    if st.button("Esegui la prova dell'oscillazione"):
        try:
            with st.spinner("Eseguo la prova su tutto lo storico…"):
                res_o, serie_o, meta_o = bm.valida_oscillazione(feat_osc, orizzonte, passo=passo,
                                                                anni=bins.index.year)
        except Exception as e:
            st.error(str(e))
        else:
            tab_o = res_o.assign(**{
                "Previsione": res_o["Previsione"].map(NOMI_OSC),
                "Miglioramento": 100 * res_o["Miglioramento"],
                "Anni vinti": res_o["Anni vinti"].astype(str) + " su " + res_o["Anni"].astype(str),
            }).drop(columns="Anni").rename(columns={
                "Bias": "Bias", "MAD": "MAD", "Sigma": "Sigma",
                "Miglioramento": "Miglioramento (%)", "Anni vinti": "Anni in cui fa meglio",
            })
            st.dataframe(
                tab_o, hide_index=True,
                column_config={
                    "Bias": st.column_config.NumberColumn(
                        format="%+.3f", help="Errore medio, in punti percentuali. Positivo: in media prevede più oscillazione di "
                                             "quella vera; negativo: meno. Vicino a zero è meglio."),
                    "MAD": st.column_config.NumberColumn(
                        format="%.3f", help="Errore assoluto medio: di quanto sbaglia in media, in punti percentuali, senza guardare il "
                                            "segno. Più è basso meglio è."),
                    "Sigma": st.column_config.NumberColumn(
                        format="%.3f", help="Deviazione standard dell'errore: quanto variano gli errori: più è basso, più la previsione è costante."),
                    "Miglioramento (%)": st.column_config.NumberColumn(
                        format="%+.1f", help="Rispetto a «come nel periodo appena passato»: positivo vuol dire che "
                                             "sbaglia meno (errore quadratico medio)."),
                    "Anni in cui fa meglio": st.column_config.TextColumn(
                        help="In quanti anni sbaglia meno di «come nel periodo appena passato»."),
                },
            )
            st.caption(
                f"Periodo di verifica: dal {bins.index[meta_o['primo_test']]:%d/%m/%Y} al "
                f"{bins.index[meta_o['ultimo_test']]:%d/%m/%Y}, {meta_o['n_test']} casi · modello riaddestrato "
                f"{meta_o['n_passi']} volte · oscillazione misurata in % {al_periodo}."
            )
            modelli = res_o[res_o["Previsione"].isin(bm.INSIEMI_OSC)]
            migliore = modelli.loc[modelli["Miglioramento"].idxmax()]
            if migliore["Miglioramento"] > 0 and migliore["Anni vinti"] > migliore["Anni"] / 2:
                st.success(f"«{NOMI_OSC[migliore['Previsione']]}» sbaglia meno del periodo appena passato del "
                           f"{100 * migliore['Miglioramento']:.0f}% e ci riesce in {migliore['Anni vinti']} anni su "
                           f"{migliore['Anni']}.")
            else:
                st.info("Il modello non fa meglio, in modo costante, che ripetere l'oscillazione del periodo appena "
                        "passato.")
            nome_m = migliore["Previsione"]
            grafico(serie_o.assign(Data=bins.index[serie_o["t"]]).set_index("Data")[["Reale", nome_m]]
                    .rename(columns={"Reale": "Oscillazione vera", nome_m: "Prevista"})
                    .rolling(passo, min_periods=1).mean(), f"% {al_periodo}")
            st.caption(f"Oscillazione vera e prevista nel periodo di verifica (media mobile su {passo} {unita}).")
