from __future__ import annotations

import streamlit as st

from brent.rialzo import PrevisioneRialzo, ProvaRialzo

from .base import Scheda


class SchedaProva(Scheda):
    titolo = "Prova di previsione"
    # Nomi comprensibili per i gruppi di dati usati nella prova (chiavi di PrevisioneRialzo.INSIEMI).
    NOMI = {
        "Livello 1 (dx, dy)": "Solo le variazioni recenti",
        "+ coseno": "+ quanto prezzo e agitazione si muovono insieme",
        "+ area di Lévy": "+ chi anticipa chi",
        "+ oscillazione": "+ quanto oscilla il prezzo (sigma e MAD)",
        "+ meteo": "+ temperatura in Europa",
        "+ OVX": "+ volatilità attesa dal mercato (OVX)",
        "+ GPR": "+ rischio geopolitico (GPR)",
        "Tutto": "Tutti i dati disponibili",
    }

    def mostra(self) -> None:
        imp, serie = self.imp, self.ctx.serie
        unita, w, orizzonte, soglia = imp.unita, imp.w, imp.orizzonte, imp.soglia
        passo = imp.freq.passo
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
               if serie.m is not None else "")
            + (" **OVX**: quanto il mercato si aspetta che il petrolio oscilli nei prossimi 30 giorni."
               if serie.o is not None else "")
            + (" **GPR**: rischio geopolitico, media degli ultimi 7 giorni." if serie.g is not None else "")
        )
        if st.button("Esegui la prova"):
            try:
                with st.spinner("Eseguo la prova su tutto lo storico…"):
                    previsione = PrevisioneRialzo(w, orizzonte, soglia / 100, passo=passo)
                    feat = previsione.features(serie.x, serie.y, **serie.esterni)
                    prova = previsione.valida(feat, anni=serie.date[feat["t"].to_numpy()].year)
            except Exception as e:
                st.error(str(e))
            else:
                self._risultati(prova)
        st.caption(
            "Attenzione: i periodi vicini si sovrappongono (il rialzo dei prossimi giorni è in gran parte lo stesso per "
            f"oggi e per domani), quindi i casi davvero indipendenti sono circa uno ogni {orizzonte} {unita}. "
            "Inoltre il Brent quotato è un contratto con scadenza mensile: quando si passa da un contratto al "
            "successivo il prezzo fa piccoli salti che non sono veri movimenti del mercato."
        )

    def _risultati(self, prova: ProvaRialzo) -> None:
        res, meta, date = prova.tabella, prova.meta, self.ctx.serie.date
        res = res.assign(**{
            "Insieme di predittori": res["Insieme di predittori"].map(self.NOMI),
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
            f"Periodo di verifica: dal {date[meta.primo_test]:%d/%m/%Y} al "
            f"{date[meta.ultimo_test]:%d/%m/%Y}, {meta.n_test} casi di cui {meta.pos_test} con "
            f"rialzo ({meta.base_rate:.1%}) · modello riaddestrato {meta.n_passi} volte · errore medio della "
            f"stima di riferimento {meta.brier_base:.4f} · con questi casi la «capacità di distinguere» può "
            f"scostarsi da 0.5 per puro caso fino a circa ±{2 * meta.auc_se:.3f}"
        )
        migliore = res.loc[res["Miglioramento sul riferimento (%)"].idxmax()]
        vinti, anni_tot = (int(v) for v in migliore["Anni in cui fa meglio"].split(" su "))
        if (res["Miglioramento sul riferimento (%)"] <= 0).all():
            st.warning("Nessun gruppo di dati fa meglio della stima di riferimento: su questi prezzi l'andamento "
                       "recente non aiuta a prevedere quello futuro.")
        elif migliore["Capacità di distinguere"] - 0.5 > 2 * meta.auc_se and vinti > anni_tot / 2:
            st.success(f"«{migliore['Dati usati per prevedere']}» fa meglio della stima di riferimento, più di "
                       f"quanto il caso da solo spiegherebbe, e ci riesce in {vinti} anni su {anni_tot}.")
        else:
            st.info("Qualche gruppo di dati fa un po' meglio della stima di riferimento, ma di poco o solo in "
                    "alcuni anni: potrebbe essere fortuna, non una vera capacità di previsione.")
