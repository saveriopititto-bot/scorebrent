from __future__ import annotations

import pandas as pd
import streamlit as st

from brent.capacita import FinestreCapacita, LimitiSpecifica, PrevisioneCapacita, ProvaCapacita

from ..caricamento import Caricamento
from ..grafici import Grafici
from ..stile import Palette
from .base import Scheda


class SchedaCapacita(Scheda):
    titolo = "Capacità dello score"
    NOMI = {PrevisioneCapacita.RETE: "Rete neurale", PrevisioneCapacita.RIFERIMENTO: "Riferimento: domani come oggi"}

    def mostra(self) -> None:
        st.subheader("Quanto resta stabile lo score?")
        if self.ctx.errore_score is not None:
            st.error(f"Non riesco a calcolare lo score: {self.ctx.errore_score}")
            return
        limiti = LimitiSpecifica()
        st.markdown(
            "Lo score si tratta come un processo che dovrebbe restare fra due limiti fissi, **−1 e +1**: le soglie "
            "dello score con θ = 1, sopra e sotto le quali si passa a +1 e −1. Su ogni finestra di **5 giorni di "
            "borsa**:\n"
            "- **Cp** dice quanto lo score oscilla rispetto alla larghezza della fascia: alto = si muove poco;\n"
            "- **Cpk** guarda anche dove sta la media: basso = lo score è vicino a uscire da un lato, anche se "
            "oscilla poco.\n\n"
            "Valori sopra 1 vogliono dire che, se continua così, lo score resta quasi sempre dentro la fascia."
        )
        s = self.ctx.score.tabella["S"]
        finestre = FinestreCapacita(limiti=limiti)
        W = finestre.tabella(s)
        if len(W) < 2:
            st.error("Troppo pochi giorni di score per calcolare Cp e Cpk.")
            return
        self._oggi(W, s, limiti)
        theta = self.ctx.parametri_score.soglia
        if theta != limiti.usl:
            st.caption(f"I limiti restano ±1 anche con la soglia θ = {theta:.2f} scelta nella barra laterale.")
        self._grafico(W)

        st.markdown("**Si può prevedere la prossima finestra?** Una rete neurale con uno strato nascosto prevede Cp e "
                    "Cpk della finestra di domani da quelli di oggi e di ieri (con media, sigma e area di Lévy). La "
                    "prova va a finestre scorrevoli: impara dal primo 70% dello storico, poi ogni 21 finestre si "
                    "riaddestra sul passato e prevede quelle dopo.")
        if st.button("Esegui la prova della rete"):
            try:
                with st.spinner("Addestro la rete su tutto lo storico (può volerci un minuto)…"):
                    prova, prossima = Caricamento.prova_capacita(s)
            except Exception as e:
                st.error(str(e))
            else:
                self._risultati(prova, prossima)

    def _oggi(self, W: pd.DataFrame, s: pd.Series, limiti: LimitiSpecifica) -> None:
        oggi, ieri = W.iloc[-1], W.iloc[-2]
        dentro = 100 * float(s.dropna().iloc[-5:].between(limiti.lsl, limiti.usl, inclusive="neither").mean())
        c1, c2, c3 = st.columns(3)
        c1.metric("Cp ultimi 5 giorni", f"{oggi.cp:.2f}", f"{oggi.cp - ieri.cp:+.2f} rispetto a ieri",
                  help=f"(USL − LSL) / 6σ, con σ = {oggi.sigma:.3f}. Il massimo mostrato è 10.")
        c2.metric("Cpk ultimi 5 giorni", f"{oggi.cpk:.2f}", f"{oggi.cpk - ieri.cpk:+.2f} rispetto a ieri",
                  help=f"min(USL − μ, μ − LSL) / 3σ, con media μ = {oggi.mu:+.2f}.")
        c3.metric("Giorni dentro la fascia", f"{dentro:.0f}%",
                  help="Quota degli ultimi 5 giorni con score fra −1 e +1. Per Cp e Cpk i "
                       "valori fuori sono portati sul limite.")

    def _grafico(self, W: pd.DataFrame) -> None:
        inizio = self.ctx.confronto.t - pd.Timedelta(days=self.imp.giorni_grafico)
        d = W.loc[inizio:, ["cp", "cpk"]].rename(columns={"cp": "Cp", "cpk": "Cpk"})
        if len(d):
            Grafici.nel_tempo(d, "Indice", colori=[Palette.BLUE_GREEN, Palette.ORANGE])
            st.caption("Cp e Cpk della finestra di 5 giorni che finisce in ogni data (al massimo 10).")

    def _risultati(self, prova: ProvaCapacita, prossima: tuple[float, float]) -> None:
        t, m, area = prova.tabella, prova.meta, prova.area
        tab = t.assign(**{
            "Previsione": t["Previsione"].map(self.NOMI),
            "Miglioramento Cp": 100 * t["Miglioramento Cp"],
            "Miglioramento Cpk": 100 * t["Miglioramento Cpk"],
        }).rename(columns={"Miglioramento Cp": "Miglioramento Cp (%)", "Miglioramento Cpk": "Miglioramento Cpk (%)"})
        errore = st.column_config.NumberColumn(format="%.3f", help="Errore assoluto medio: più è basso meglio è.")
        bias = st.column_config.NumberColumn(format="%+.3f", help="Errore medio: positivo = in media prevede troppo.")
        meglio = st.column_config.NumberColumn(format="%+.1f", help="Rispetto a «domani come oggi»: positivo vuol "
                                                                    "dire che sbaglia meno (errore assoluto medio).")
        st.dataframe(tab, hide_index=True, column_config={
            "MAE Cp": errore, "MAE Cpk": errore, "Bias Cp": bias, "Bias Cpk": bias,
            "Miglioramento Cp (%)": meglio, "Miglioramento Cpk (%)": meglio})
        s = prova.serie
        st.caption(
            f"Periodo di verifica: dal {s.fine.iloc[0]:%d/%m/%Y} al {s.fine.iloc[-1]:%d/%m/%Y}, {m.n_test} finestre · "
            f"rete riaddestrata {m.n_passi} volte · giorni con score fuori da ±1, portati sul limite: "
            f"{100 * m.quota_tagliata:.0f}%. Due finestre vicine hanno 4 giorni su 5 in comune, quindi «domani come "
            "oggi» è un riferimento molto difficile da battere."
        )
        rete = t.iloc[0]
        if rete["Miglioramento Cp"] > 0 and rete["Miglioramento Cpk"] > 0:
            st.success("La rete sbaglia meno di «domani come oggi» sia su Cp sia su Cpk.")
        elif rete["Miglioramento Cp"] > 0 or rete["Miglioramento Cpk"] > 0:
            st.info("La rete fa meglio di «domani come oggi» solo su uno dei due indici.")
        else:
            st.warning("La rete non fa meglio di «domani come oggi»: Cp e Cpk di domani si prevedono meglio "
                       "ripetendo quelli di oggi.")
        cp, cpk = prossima
        c1, c2 = st.columns(2)
        c1.metric("Cp previsto per domani", f"{cp:.2f}", help="Rete addestrata su tutto lo storico.")
        c2.metric("Cpk previsto per domani", f"{cpk:.2f}", help="Rete addestrata su tutto lo storico.")
        Grafici.nel_tempo(s.set_index("fine")[["Cpk reale", "Cpk rete"]].rename_axis(None)
                          .rename(columns={"Cpk reale": "Cpk vero", "Cpk rete": "Cpk previsto"})
                          .rolling(21, min_periods=1).mean(), "Cpk", colori=[Palette.DEEP, Palette.ORANGE])
        st.caption("Cpk vero e previsto dalla rete nel periodo di verifica (media mobile su 21 finestre).")
        st.caption(
            f"Area di Lévy del cammino (S, dS) su 5 giorni: media {area.media:.3g}, contro {area.riferimento:.3g} di "
            f"una passeggiata casuale con gli stessi movimenti (z = {area.z:+.1f}). Con |z| oltre 2 lo score non si "
            "muove come una passeggiata casuale."
        )
