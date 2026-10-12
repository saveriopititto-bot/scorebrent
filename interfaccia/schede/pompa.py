from __future__ import annotations

import pandas as pd
import streamlit as st

from brent.pompa import AnalisiPompa

from ..grafici import Grafici
from .base import Scheda


class SchedaPompa(Scheda):
    titolo = "Pompa (Italia)"
    ARTICOLI = {"Benzina": "la benzina", "Gasolio": "il gasolio"}

    def mostra(self) -> None:
        st.subheader("Prezzi medi alla pompa in Italia")
        pompa = self.ctx.pompa
        if not pompa.attivo:
            st.info("I prezzi alla pompa sono disattivati: attiva «Usa i prezzi alla pompa in Italia» nella barra "
                    "laterale.")
            return
        if not pompa.disponibile:
            st.warning(f"Non sono riuscito a scaricare i prezzi alla pompa: {pompa.errore}")
            return
        analisi = AnalisiPompa(pompa.valore)
        pompa_df = analisi.prezzi
        ult, pen = pompa_df.iloc[-1], pompa_df.iloc[-2]
        c1, c2, c3 = st.columns(3)
        c1.metric("Benzina", f"{ult['Benzina']:.3f} € al litro", f"{100 * (ult['Benzina'] - pen['Benzina']):+.1f} cent",
                  delta_color="inverse")
        c2.metric("Gasolio", f"{ult['Gasolio']:.3f} € al litro", f"{100 * (ult['Gasolio'] - pen['Gasolio']):+.1f} cent",
                  delta_color="inverse")
        c3.metric("Listino del", f"{pompa_df.index[-1]:%d/%m/%Y}",
                  help="I prezzi sono quelli in vigore il lunedì; la Commissione li pubblica qualche giorno dopo.")
        inizio_p = self.ctx.confronto.t - pd.Timedelta(days=max(self.imp.giorni_grafico, 182))
        Grafici.nel_tempo(pompa_df.loc[inizio_p:], "Euro al litro")
        brent_l = analisi.brent_al_litro(self.ctx.base["eur"])
        Grafici.nel_tempo(brent_l.loc[inizio_p:].rename("Brent (petrolio greggio)").to_frame(), "Euro al litro")
        st.caption("Sopra: prezzi medi nazionali con tutte le tasse. Sotto: il Brent convertito in euro al litro, cioè "
                   "il costo della sola materia prima. La differenza sono raffinazione, distribuzione, accise e IVA.")
        self._ritardo(analisi, brent_l)

    def _ritardo(self, analisi: AnalisiPompa, brent_l: pd.Series) -> None:
        st.markdown("**Con quanto ritardo la pompa segue il Brent?**")
        rit = {c: analisi.ritardo(brent_l, c) for c in analisi.carburanti}
        tab_r = rit["Benzina"][["Ritardo (settimane)"]].copy()
        for c, d in rit.items():
            tab_r[f"{c}: correlazione"] = d["Correlazione"].values
            tab_r[f"{c}: quota trasferita"] = d["Quota trasferita"].values
        st.dataframe(tab_r, hide_index=True,
                     column_config={c: st.column_config.NumberColumn(format="%.2f") for c in tab_r.columns[1:]})
        frasi = []
        for c, d in rit.items():
            k = int(d.loc[d["Correlazione"].idxmax(), "Ritardo (settimane)"])
            frasi.append(f"{self.ARTICOLI[c]} reagisce soprattutto dopo **{k} settiman{'a' if k == 1 else 'e'}** e, "
                         f"in tutto, trasferisce circa **{d['Quota trasferita'].clip(lower=0).sum():.2f}** centesimi "
                         "per ogni centesimo di Brent")
        st.markdown("In questi dati " + "; ".join(frasi) + ".")
        st.caption(
            "Per ogni ritardo, la tabella confronta la variazione del Brent in una settimana con quella della pompa "
            "dopo 0, 1, 2… settimane. La correlazione dice quanto i due movimenti vanno insieme; la quota trasferita "
            "dice quanti centesimi alla pompa segue ogni centesimo di Brent al litro. Fonte: EU Weekly Oil Bulletin, "
            "Commissione Europea, raccolto da [fuel-prices.eu](https://www.fuel-prices.eu/research/) (CC BY 4.0)."
        )
