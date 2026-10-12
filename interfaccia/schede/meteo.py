from __future__ import annotations

import pandas as pd
import streamlit as st

from brent.fonti import FonteMeteo

from ..grafici import Grafici
from .base import Scheda


class SchedaMeteo(Scheda):
    titolo = "Meteo"

    def mostra(self) -> None:
        st.subheader("Fa più caldo o più freddo del normale in Europa?")
        meteo = self.ctx.meteo
        if self.manca(meteo, "Temperatura in Europa", "le temperature da Open-Meteo"):
            return
        anomalia = meteo.valore
        c1, c2 = st.columns(2)
        c1.metric(f"Ultimo giorno ({anomalia.index[-1]:%d/%m/%Y})", f"{anomalia.iloc[-1]:+.1f} °C rispetto al normale")
        c2.metric("Media degli ultimi 30 giorni", f"{anomalia.iloc[-30:].mean():+.1f} °C rispetto al normale")
        inizio_g = self.ctx.confronto.t - pd.Timedelta(days=self.imp.giorni_grafico)
        Grafici.nel_tempo(anomalia.rolling(7, min_periods=4).mean().loc[inizio_g:].rename("Media su 7 giorni").to_frame(),
                          "°C rispetto al normale")
        Grafici.nel_tempo(self.ctx.base.loc[inizio_g:, ["eur"]].rename(columns={"eur": "Euro al barile"}),
                          "Prezzo al barile")
        st.caption(
            f"Media di {', '.join(FonteMeteo.CITTA)}. Il «normale» è la media dello stesso periodo dell'anno dal "
            f"{anomalia.index[0].year}. Un inverno freddo fa consumare più gasolio da riscaldamento: se questo muove "
            "il prezzo lo verifica la «Prova di previsione». Dati: [Open-Meteo.com](https://open-meteo.com) (CC BY 4.0)."
        )
