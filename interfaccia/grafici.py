"""Grafici Altair condivisi dalle schede."""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st


class Grafici:
    ASSE_DATE = alt.Axis(format="%d/%m/%y")

    @classmethod
    def asse_x(cls) -> alt.X:
        return alt.X("Data:T", title=None, axis=cls.ASSE_DATE)

    @classmethod
    def nel_tempo(cls, df: pd.DataFrame, titolo_y: str, barre: bool = False, colori: list[str] | None = None) -> None:
        """Grafico nel tempo con date in formato italiano (gg/mm/aa); una serie per colonna di `df`."""
        d = df.rename_axis("Data").reset_index().melt("Data", var_name="Serie", value_name="Valore").dropna()
        if barre:
            d = d[d["Valore"] != 0]
        colore = alt.Color("Serie:N", title=None, sort=list(df.columns), legend=alt.Legend(orient="bottom"),
                           scale=alt.Scale(domain=list(df.columns), range=colori) if colori else alt.Undefined)
        c = (alt.Chart(d).mark_bar() if barre else alt.Chart(d).mark_line()).encode(
            x=cls.asse_x(),
            y=alt.Y("Valore:Q", title=titolo_y, scale=alt.Scale(zero=barre)),
            color=colore,
            tooltip=[alt.Tooltip("Data:T", title="Data", format="%d/%m/%Y"), alt.Tooltip("Serie:N", title="Serie"),
                     alt.Tooltip("Valore:Q", title="Valore", format=".2f")],
        )
        st.altair_chart(c, width="stretch")
