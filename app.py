"""App «Prezzo del petrolio»: Brent da Yahoo Finance e analisi del suo andamento
(matematica del paper "sisma", in brent_math.py), con la temperatura in Europa da
Open-Meteo come possibile dato di previsione. Avvio: `streamlit run app.py`."""
import altair as alt
import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

import brent_math as bm

st.set_page_config(page_title="Prezzo del petrolio", page_icon="🛢️", layout="wide")
st.title("🛢️ Prezzo del petrolio (Brent)")

BRENT = "BZ=F"        # Brent Crude Oil Futures (USD/barile)
EURUSD = "EURUSD=X"   # dollari per 1 euro

# Nomi comprensibili per i gruppi di dati usati nella prova di previsione (chiavi di bm.INSIEMI).
NOMI_INSIEMI = {
    "Livello 1 (dx, dy)": "Solo le variazioni recenti",
    "+ coseno": "+ quanto prezzo e agitazione si muovono insieme",
    "+ area di Lévy": "+ chi anticipa chi",
    "+ oscillazione": "+ quanto oscilla il prezzo (sigma e MAD)",
    "Tutto": "Tutti i dati insieme",
    "+ meteo": "+ temperatura in Europa",
    "Tutto + meteo": "Tutti i dati + temperatura in Europa",
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


@st.cache_data(ttl=900, show_spinner="Scarico i prezzi da Yahoo Finance…")
def scarica(ticker: str) -> pd.DataFrame:
    d = yf.Ticker(ticker).history(period="max", interval="1d")
    if d.empty:
        raise ValueError(f"Yahoo Finance non ha restituito dati per {ticker}")
    d = d[["High", "Low", "Close"]].dropna()
    d = d[(d.Low > 0) & (d.High >= d.Low)]  # scarta le righe con prezzi impossibili
    d.index = d.index.tz_localize(None).normalize()
    return d


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
    st.altair_chart(c, use_container_width=True)


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

# --------------------------------------------------------------------------
# Dati
# --------------------------------------------------------------------------
try:
    b, f = scarica(BRENT), scarica(EURUSD)
except Exception as e:
    st.error(f"Non sono riuscito a scaricare i prezzi: {e}")
    st.stop()

# Solo i giorni in cui il Brent quota; il cambio è riportato sull'ultimo valore disponibile.
base = pd.DataFrame(
    {"usd": b["Close"], "high": b["High"], "low": b["Low"],
     "fx": f["Close"].reindex(b.index, method="ffill")}
).dropna()
base["eur"] = base["usd"] / base["fx"]

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
if usa_meteo:
    try:
        anomalia = bm.anomalia_stagionale(scarica_meteo(base.index[0], t))
    except Exception as e:
        errore_meteo = str(e)

tab1, tab2, tab3, tab4 = st.tabs(["Prezzo", "Andamento", "Meteo", "Prova di previsione"])

# --------------------------------------------------------------------------
# Scheda 1 - Prezzo
# --------------------------------------------------------------------------
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
bins = aggrega(base, freq)
x = np.log(bins["eur"].to_numpy())                                   # livello: ln prezzo in euro
y = np.log1p(100 * (bins["high"] / bins["low"] - 1)).to_numpy()      # agitazione: ln(1 + escursione % fra massimo e minimo)
m = None                                                             # meteo: anomalia di temperatura nei periodi
if anomalia is not None:
    m_bin = anomalia if freq == "Giorno per giorno" else anomalia.resample("W-FRI").mean()
    m = m_bin.reindex(bins.index).to_numpy()

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
            "Variazione (%)", barre=True, colori=["#2e7d32", "#c62828"])

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
    )
    if st.button("Esegui la prova"):
        try:
            with st.spinner("Eseguo la prova su tutto lo storico…"):
                feat = bm.costruisci_features(x, y, w, orizzonte, meteo=m)
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
