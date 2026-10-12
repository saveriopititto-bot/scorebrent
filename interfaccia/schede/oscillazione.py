from __future__ import annotations

import numpy as np
import streamlit as st

from brent.oscillazione import PrevisioneOscillazione, ProvaOscillazione

from ..grafici import Grafici
from .base import Scheda


class SchedaOscillazione(Scheda):
    titolo = "Oscillazione attesa"
    # Nomi comprensibili per le previsioni dell'oscillazione (chiavi di PrevisioneOscillazione.INSIEMI più i
    # riferimenti).
    NOMI = {
        "Oscillazione recente": "Modello: oscillazione recente (sigma e MAD)",
        "+ agitazione": "Modello: + agitazione (massimo − minimo)",
        "+ agitazione e meteo": "Modello: + agitazione e temperatura",
        "+ agitazione e OVX": "Modello: + agitazione e OVX",
        "+ agitazione e GPR": "Modello: + agitazione e rischio geopolitico",
        "Tutto": "Modello: tutti i dati disponibili",
        PrevisioneOscillazione.COME_PASSATO: "Riferimento: come nel periodo appena passato",
        PrevisioneOscillazione.OVX_GREZZO: "Riferimento: OVX così com'è",
        PrevisioneOscillazione.MEDIA_STORICA: "Riferimento: media storica",
    }

    def mostra(self) -> None:
        imp, serie, ctx = self.imp, self.ctx.serie, self.ctx
        unita, orizzonte, al_periodo = imp.unita, imp.orizzonte, imp.freq.al_periodo
        previsione = PrevisioneOscillazione(imp.w, orizzonte, passo=imp.freq.passo)
        st.subheader(f"Quanto si muoverà il prezzo nei prossimi {orizzonte} {unita}?")
        st.markdown(
            "**Quanto si muoverà** il prezzo è molto più prevedibile della direzione, perché i periodi agitati tendono "
            f"a durare. Il modello usa l'oscillazione recente (*sigma* e *MAD*, sugli ultimi {imp.w} e 5 {unita}), "
            "l'agitazione (massimo − minimo)" + (" e la volatilità attesa dal mercato (OVX)." if serie.o is not None else ".")
        )
        if ctx.ovx.attivo and serie.o is None:
            st.warning(f"Non sono riuscito a scaricare l'OVX, continuo senza: {ctx.ovx.errore}")
        feat = previsione.features(serie.x, serie.y, **serie.esterni)
        modello = previsione.modello_predefinito(serie.o is not None)
        try:
            attesa = 100 * previsione.prevedi(feat, previsione.INSIEMI[modello])
        except Exception as e:
            st.error(str(e))
        else:
            self._oggi(attesa, modello, feat, orizzonte, unita, al_periodo)

        st.markdown("**Quanto è affidabile?** Stessa prova a finestre scorrevoli della «Prova di previsione», contro "
                    "riferimenti semplici.")
        if st.button("Esegui la prova dell'oscillazione"):
            try:
                with st.spinner("Eseguo la prova su tutto lo storico…"):
                    prova = previsione.valida(feat, anni=serie.date.year)
            except Exception as e:
                st.error(str(e))
            else:
                self._risultati(prova, unita, al_periodo)

    def _oggi(self, attesa: float, modello: str, feat, orizzonte: int, unita: str, al_periodo: str) -> None:
        ora = self.ctx.confronto.ora
        normale = 100 * float(np.exp(feat["bersaglio"].median()))
        escursione = attesa * np.sqrt(orizzonte)
        c1, c2, c3 = st.columns(3)
        c1.metric("Oscillazione attesa", f"{attesa:.2f}% {al_periodo}",
                  f"{attesa - normale:+.2f} punti rispetto al normale", delta_color="inverse",
                  help=f"Modello «{self.NOMI[modello].removeprefix('Modello: ')}». Il normale è la mediana di tutto lo "
                       f"storico: {normale:.2f}% {al_periodo}.")
        c2.metric(f"Movimento probabile in {orizzonte} {unita}", f"±{escursione:.1f}%",
                  help="In circa 2 casi su 3 la variazione complessiva del prezzo resta dentro questo intervallo; "
                       "nel restante terzo va oltre, in su o in giù.")
        c3.metric("In euro al barile", f"±{ora['eur'] * escursione / 100:.2f} €",
                  help=f"Lo stesso intervallo applicato al prezzo attuale di {ora['eur']:.2f} € al barile.")
        if self.ctx.ovx.disponibile:
            ovx_oggi = self.ctx.ovx.valore.dropna()
            st.caption(
                f"OVX al {ovx_oggi.index[-1]:%d/%m/%Y}: **{ovx_oggi.iloc[-1]:.1f}**, cioè il mercato delle opzioni si "
                f"aspetta circa {ovx_oggi.iloc[-1] / np.sqrt(self.imp.freq.periodi_anno):.2f}% {al_periodo}. È calcolato "
                "sul WTI americano, che si muove quasi insieme al Brent."
            )

    def _risultati(self, prova: ProvaOscillazione, unita: str, al_periodo: str) -> None:
        res_o, serie_o, meta_o = prova.tabella, prova.serie, prova.meta
        date, passo = self.ctx.serie.date, self.imp.freq.passo
        tab_o = res_o.assign(**{
            "Previsione": res_o["Previsione"].map(self.NOMI),
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
            f"Periodo di verifica: dal {date[meta_o.primo_test]:%d/%m/%Y} al "
            f"{date[meta_o.ultimo_test]:%d/%m/%Y}, {meta_o.n_test} casi · modello riaddestrato "
            f"{meta_o.n_passi} volte · oscillazione misurata in % {al_periodo}."
        )
        modelli = res_o[res_o["Previsione"].isin(list(PrevisioneOscillazione.INSIEMI))]
        migliore = modelli.loc[modelli["Miglioramento"].idxmax()]
        if migliore["Miglioramento"] > 0 and migliore["Anni vinti"] > migliore["Anni"] / 2:
            st.success(f"«{self.NOMI[migliore['Previsione']]}» sbaglia meno del periodo appena passato del "
                       f"{100 * migliore['Miglioramento']:.0f}% e ci riesce in {migliore['Anni vinti']} anni su "
                       f"{migliore['Anni']}.")
        else:
            st.info("Il modello non fa meglio, in modo costante, che ripetere l'oscillazione del periodo appena "
                    "passato.")
        nome_m = migliore["Previsione"]
        Grafici.nel_tempo(serie_o.assign(Data=date[serie_o["t"]]).set_index("Data")[["Reale", nome_m]]
                          .rename(columns={"Reale": "Oscillazione vera", nome_m: "Prevista"})
                          .rolling(passo, min_periods=1).mean(), f"% {al_periodo}")
        st.caption(f"Oscillazione vera e prevista nel periodo di verifica (media mobile su {passo} {unita}).")
