from __future__ import annotations

import pandas as pd
import streamlit as st

from ..grafici import Grafici
from .base import Scheda


class SchedaGeopolitica(Scheda):
    titolo = "Geopolitica"

    def mostra(self) -> None:
        st.subheader("Quanto è alto il rischio geopolitico?")
        gpr = self.ctx.gpr
        if self.manca(gpr, "Rischio geopolitico (GPR)", "il rischio geopolitico (GPR)"):
            return
        gpr_df = gpr.valore
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
        inizio_g = self.ctx.confronto.t - pd.Timedelta(days=self.imp.giorni_grafico)
        Grafici.nel_tempo(gd.rolling("30D").mean().loc[inizio_g:].rename("Media su 30 giorni").to_frame()
                          .join(gd.rolling("7D").mean().loc[inizio_g:].rename("Media su 7 giorni")),
                          "Indice (100 = normale)")
        Grafici.nel_tempo(self.ctx.base.loc[inizio_g:, ["eur"]].rename(columns={"eur": "Euro al barile"}),
                          "Prezzo al barile")
        self._eventi(gpr_df)
        st.caption(
            "Quota di articoli di 10 grandi giornali su guerre, terrorismo e tensioni fra Paesi. Se le crisi muovono il "
            "Brent lo verificano «Prova di previsione» e «Oscillazione attesa». Aggiornato dagli autori con qualche "
            "giorno di ritardo. Fonte: D. Caldara e M. Iacoviello, «Measuring Geopolitical Risk», American Economic "
            "Review, 2022, [matteoiacoviello.com](https://www.matteoiacoviello.com/gpr.htm)."
        )

    @staticmethod
    def _eventi(gpr_df: pd.DataFrame) -> None:
        eventi = gpr_df.loc[gpr_df["event"].notna() & (gpr_df["event"].astype(str).str.strip() != ""), ["event", "GPRD"]]
        if not len(eventi):
            return
        st.markdown("**Eventi principali più recenti** (etichette originali in inglese)")
        st.dataframe(
            eventi.iloc[::-1].head(10).rename_axis("Data").reset_index()
            .assign(Data=lambda d: d["Data"].dt.strftime("%d/%m/%Y"))
            .rename(columns={"event": "Evento", "GPRD": "GPR del giorno"}),
            hide_index=True, column_config={"GPR del giorno": st.column_config.NumberColumn(format="%.0f")},
        )
