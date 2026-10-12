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
        if not meteo.attivo:
            st.info("La temperatura è disattivata: attiva «Usa la temperatura in Europa» nella barra laterale.")
            return
        if not meteo.disponibile:
            st.warning(f"Non sono riuscito a scaricare le temperature da Open-Meteo: {meteo.errore}")
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
            f"Temperatura media di {', '.join(FonteMeteo.CITTA)}. Il «normale» è la media dello stesso periodo dell'anno "
            f"dal {anomalia.index[0].year} a oggi: sopra zero fa più caldo del solito, sotto zero più freddo. In teoria "
            "un inverno più freddo fa consumare più gasolio da riscaldamento e può spingere il prezzo; la scheda «Prova "
            "di previsione» verifica se succede davvero. Dati meteo: [Open-Meteo.com](https://open-meteo.com) (licenza "
            "CC BY 4.0)."
        )
