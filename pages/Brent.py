"""App Streamlit: Brent da Yahoo Finance + analisi differenziale (matematica del paper "sisma")."""
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

import brent_math as bm

st.set_page_config(page_title="Brent", page_icon="🛢️", layout="wide")
st.title("🛢️ Brent da Yahoo Finance")

BRENT = "BZ=F"        # Brent Crude Oil Futures (USD/barile)
EURUSD = "EURUSD=X"   # dollari per 1 euro


@st.cache_data(ttl=900, show_spinner="Scarico i dati da Yahoo Finance…")
def scarica(ticker: str) -> pd.DataFrame:
    d = yf.Ticker(ticker).history(period="5y", interval="1d")
    if d.empty:
        raise ValueError(f"Yahoo Finance non ha restituito dati per {ticker}")
    d = d[["High", "Low", "Close"]].dropna()
    d.index = d.index.tz_localize(None).normalize()
    return d


def aggrega(base: pd.DataFrame, freq: str) -> pd.DataFrame:
    if freq == "Giornaliero":
        return base
    return base.resample("W-FRI").agg(
        {"usd": "last", "high": "max", "low": "min", "fx": "last", "eur": "last"}
    ).dropna()


# --------------------------------------------------------------------------
# Barra laterale
# --------------------------------------------------------------------------
sb = st.sidebar
n = sb.slider("n (giorni di confronto per ΔB)", 1, 60, 7)
mesi = sb.selectbox("Periodo del grafico", ["1 mese", "3 mesi", "6 mesi", "1 anno", "5 anni"], index=1)
giorni_grafico = {"1 mese": 30, "3 mesi": 91, "6 mesi": 182, "1 anno": 365, "5 anni": 1826}[mesi]
if sb.button("Aggiorna ora"):
    st.cache_data.clear()

sb.divider()
sb.subheader("Analisi differenziale")
freq = sb.radio("Bin", ["Giornaliero", "Settimanale"], horizontal=True)
N = sb.slider("Ultimi N bin da analizzare", 20, 500, 120)
w = sb.slider("Finestra w (bin)", 5, 60, 20)
orizzonte = sb.slider("Orizzonte di previsione (bin)", 1, 20, 5)
soglia = sb.number_input("Soglia di rialzo (%)", value=0.0, step=0.5)

# --------------------------------------------------------------------------
# Dati
# --------------------------------------------------------------------------
try:
    b, f = scarica(BRENT), scarica(EURUSD)
except Exception as e:
    st.error(f"Download non riuscito: {e}")
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
    st.error("Lo storico scaricato non copre così tanti giorni.")
    st.stop()
data_prima = base.index[base.index <= tn][-1]
ora, prima = base.loc[t], base.loc[data_prima]
d_usd = ora["usd"] / prima["usd"] - 1
d_eur = ora["eur"] / prima["eur"] - 1
d_clip = max(-0.10, min(0.10, d_eur))

tab1, tab2, tab3 = st.tabs(["Prezzo", "Analisi differenziale", "Validazione"])

# --------------------------------------------------------------------------
# Scheda 1 - Prezzo
# --------------------------------------------------------------------------
with tab1:
    st.caption(f"Ultima chiusura disponibile: {t:%d/%m/%Y} · confronto con {data_prima:%d/%m/%Y}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Brent", f"{ora['usd']:.2f} $/bbl", f"{d_usd:+.2%}")
    c2.metric("Brent in euro", f"{ora['eur']:.2f} €/bbl", f"{d_eur:+.2%}")
    c3.metric("ΔB (limitato a ±10%)", f"{d_clip:+.2%}",
              help="Variazione relativa in euro su n giorni, come nel modello di scoring")
    grafico = base.loc[base.index >= t - pd.Timedelta(days=giorni_grafico), ["usd", "eur"]]
    st.line_chart(grafico.rename(columns={"usd": "Brent ($/bbl)", "eur": "Brent (€/bbl)"}))
    st.caption("Fonte: Yahoo Finance (BZ=F ed EURUSD=X). I dati possono avere ritardo e non sono una consulenza finanziaria.")

# --------------------------------------------------------------------------
# Serie nei bin scelti
# --------------------------------------------------------------------------
bins = aggrega(base, freq)
x = np.log(bins["eur"].to_numpy())                                   # livello: ln prezzo in euro
y = np.log1p(100 * (bins["high"] / bins["low"] - 1)).to_numpy()      # attività: ln(1 + range % intraday)

# --------------------------------------------------------------------------
# Scheda 2 - Analisi differenziale
# --------------------------------------------------------------------------
with tab2:
    xn = x[-(N + 1):]
    h = 100 * bm.altezze(xn)                                         # rendimenti log. in %
    idx = bins.index[-len(h):]
    ag = bm.aggregati(h)

    st.subheader("Altezze differenziali fra bin consecutivi")
    st.caption(
        "h_k = ln B_k − ln B_{k−1}, in %: l'analogo di ΔM_eq del paper. "
        "Verde = intensificazione (prezzo in salita), rosso = attenuazione."
    )
    st.bar_chart(
        pd.DataFrame({"Rialzo (+)": np.clip(h, 0, None), "Ribasso (−)": np.clip(h, None, 0)}, index=idx),
        color=["#2e7d32", "#c62828"],
    )

    cA, cB = st.columns([1, 1])
    with cA:
        st.markdown("**Aggregati sugli ultimi N bin**")
        tab = pd.DataFrame(
            {
                "Statistica": ["Variazione totale Σ|h|", "Parte positiva", "Parte negativa", "RMS (volatilità per bin)",
                               "Salto massimo", "Salto minimo", "net (lineare, telescopica)"],
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
        st.metric("Efficienza del percorso |net| / Σ|h|", f"{eff:.2f}",
                  help="1 = salita/discesa rettilinea; vicino a 0 = molto movimento ma poca strada netta")
        st.metric("Forza del movimento di ΔB", f"{z:+.2f} σ",
                  help="Variazione su n giorni divisa per σ_giornaliera·√k (σ = RMS degli ultimi 60 rendimenti giornalieri)")
        st.caption(
            "La somma delle altezze è telescopica (eq. 4): vale solo ln(B_fine/B_inizio) e non distingue un mese "
            "tranquillo da uno turbolento. Per questo ΔB da solo ignora il percorso; "
            "variazione totale, RMS ed efficienza lo descrivono."
        )

    st.subheader("Area di Lévy: prezzo contro attività")
    A = bm.area_levy_mobile(x, y, w)
    serie_A = pd.Series(A, index=bins.index).iloc[-N:]
    st.line_chart(serie_A.rename("Area di Lévy normalizzata"))
    ultimo = serie_A.dropna()
    st.metric("Ultima finestra", f"{ultimo.iloc[-1]:+.2f}" if len(ultimo) else "n/d")
    st.caption(
        "Cammino nel piano (x = ln prezzo in €, y = ln(1 + range intraday %)), finestra scorrevole di w bin, "
        "normalizzata per le deviazioni standard degli incrementi. **A > 0: il prezzo anticipa l'attività; "
        "A < 0: l'attività anticipa il prezzo.** Per un cammino rettilineo vale 0."
    )

# --------------------------------------------------------------------------
# Scheda 3 - Validazione
# --------------------------------------------------------------------------
with tab3:
    st.subheader("Il passato prevede il Brent dei prossimi bin?")
    st.markdown(
        f"Bersaglio: il Brent in euro sale di oltre **{soglia:.1f}%** nei prossimi **{orizzonte}** bin. "
        "Split temporale 60/40 senza rimescolamento, confronto con una baseline a frequenza costante "
        "(skill = 1 − Brier_modello / Brier_baseline), come nel §3.6 del paper."
    )
    if st.button("Esegui validazione"):
        try:
            feat = bm.costruisci_features(x, y, w, orizzonte)
            res, meta = bm.validazione(feat, orizzonte, soglia / 100)
        except Exception as e:
            st.error(str(e))
        else:
            st.dataframe(
                res, hide_index=True,
                column_config={"Brier": st.column_config.NumberColumn(format="%.4f"),
                               "Skill": st.column_config.NumberColumn(format="%+.3f"),
                               "AUC": st.column_config.NumberColumn(format="%.3f")},
            )
            st.caption(
                f"Training {meta['n_train']} · test {meta['n_test']} osservazioni ({meta['pos_test']} rialzi nel test) · "
                f"baseline: frequenza di rialzo nel training {meta['base_rate_train']:.1%} (Brier {meta['brier_base']:.4f}) · "
                f"incertezza dell'AUC sotto ipotesi nulla ≈ ±{meta['auc_se']:.3f}"
            )
            migliore = res.loc[res["Skill"].idxmax()]
            if (res["Skill"] <= 0).all():
                st.warning("Nessun insieme di predittori batte la baseline: su questi dati il passato recente non "
                           "anticipa il Brent futuro. Il termine α·ΔB del modello resta quindi una scommessa non dimostrata.")
            elif migliore["AUC"] - 0.5 > 2 * meta["auc_se"]:
                st.success(f"«{migliore['Insieme di predittori']}» batte la baseline con un AUC oltre l'incertezza attesa. "
                           "Prima di fidarti ripeti il test su altri periodi e orizzonti.")
            else:
                st.info("Qualche skill positivo, ma dentro l'incertezza attesa con così pochi casi indipendenti: "
                        "non è evidenza di capacità predittiva.")
    st.caption(
        "Cautele: i bersagli di bin vicini si sovrappongono, quindi i casi indipendenti sono circa N/orizzonte; "
        "la serie BZ=F è un future a scadenza mensile e il passaggio da una scadenza alla successiva produce salti "
        "che non sono vero movimento di prezzo e gonfiano variazione totale e area di Lévy."
    )
