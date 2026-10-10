"""App «Prezzo del petrolio»: Brent da Yahoo Finance e analisi del suo andamento
(matematica del paper "sisma", in brent_math.py). Avvio: `streamlit run app.py`."""
import altair as alt
import numpy as np
import pandas as pd
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
    "Tutto": "Tutti i dati insieme",
}


@st.cache_data(ttl=900, show_spinner="Scarico i prezzi da Yahoo Finance…")
def scarica(ticker: str) -> pd.DataFrame:
    d = yf.Ticker(ticker).history(period="5y", interval="1d")
    if d.empty:
        raise ValueError(f"Yahoo Finance non ha restituito dati per {ticker}")
    d = d[["High", "Low", "Close"]].dropna()
    d.index = d.index.tz_localize(None).normalize()
    return d


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
mesi = sb.selectbox("Periodo mostrato nel grafico", ["1 mese", "3 mesi", "6 mesi", "1 anno", "5 anni"], index=1)
giorni_grafico = {"1 mese": 30, "3 mesi": 91, "6 mesi": 182, "1 anno": 365, "5 anni": 1826}[mesi]
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

tab1, tab2, tab3 = st.tabs(["Prezzo", "Andamento", "Prova di previsione"])

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
# Scheda 3 - Prova di previsione
# --------------------------------------------------------------------------
with tab3:
    st.subheader("L'andamento passato aiuta a prevedere il prezzo?")
    st.markdown(
        f"Domanda: il prezzo in euro salirà di oltre **{soglia:.1f}%** nei prossimi **{orizzonte} {unita}**? "
        "Il modello impara sul primo 60% dei dati (periodo di studio) e viene messo alla prova sul restante 40% "
        "(periodo di verifica), che non ha mai visto. Il confronto è con una **stima di riferimento** che non guarda "
        "il passato recente e dà sempre la stessa probabilità: quanto spesso il prezzo è salito nel periodo di studio."
    )
    if st.button("Esegui la prova"):
        try:
            feat = bm.costruisci_features(x, y, w, orizzonte)
            res, meta = bm.validazione(feat, orizzonte, soglia / 100)
        except Exception as e:
            st.error(str(e))
        else:
            res = res.assign(**{
                "Insieme di predittori": res["Insieme di predittori"].map(NOMI_INSIEMI),
                "Skill": 100 * res["Skill"],
            }).rename(columns={
                "Insieme di predittori": "Dati usati per prevedere",
                "Brier": "Errore medio",
                "Skill": "Miglioramento sul riferimento (%)",
                "AUC": "Capacità di distinguere",
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
                },
            )
            st.caption(
                f"Periodo di studio: {meta['n_train']} casi · periodo di verifica: {meta['n_test']} casi, di cui "
                f"{meta['pos_test']} con rialzo · la stima di riferimento dà sempre {meta['base_rate_train']:.1%} di "
                f"probabilità di rialzo (errore medio {meta['brier_base']:.4f}) · con così pochi casi la «capacità di "
                f"distinguere» può scostarsi da 0.5 per puro caso fino a circa ±{2 * meta['auc_se']:.3f}"
            )
            migliore = res.loc[res["Miglioramento sul riferimento (%)"].idxmax()]
            if (res["Miglioramento sul riferimento (%)"] <= 0).all():
                st.warning("Nessun gruppo di dati fa meglio della stima di riferimento: su questi prezzi l'andamento "
                           "recente non aiuta a prevedere quello futuro.")
            elif migliore["Capacità di distinguere"] - 0.5 > 2 * meta["auc_se"]:
                st.success(f"«{migliore['Dati usati per prevedere']}» fa meglio della stima di riferimento, più di "
                           "quanto il caso da solo spiegherebbe. Prima di fidarti, ripeti la prova cambiando periodo "
                           "e orizzonte.")
            else:
                st.info("Qualche gruppo di dati fa un po' meglio della stima di riferimento, ma di poco: con così "
                        "pochi casi potrebbe essere fortuna, non una vera capacità di previsione.")
    st.caption(
        "Attenzione: i periodi vicini si sovrappongono (il rialzo dei prossimi giorni è in gran parte lo stesso per "
        f"oggi e per domani), quindi i casi davvero indipendenti sono circa uno ogni {orizzonte} {unita}. "
        "Inoltre il Brent quotato è un contratto con scadenza mensile: quando si passa da un contratto al "
        "successivo il prezzo fa piccoli salti che non sono veri movimenti del mercato."
    )
