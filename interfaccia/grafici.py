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
    def nel_tempo(
        cls,
        df: pd.DataFrame,
        titolo_y: str,
        barre: bool = False,
        colori: list[str] | None = None,
        outliers: pd.DataFrame | None = None,
    ) -> None:
        """Grafico nel tempo con date in formato italiano (gg/mm/aa); una serie per colonna di `df`.
        Se fornito, `outliers` sovrappone punti rossi con tooltip di dettaglio sulle anomalie."""
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
        if outliers is not None and not outliers.empty:
            punti = alt.Chart(outliers).mark_circle(size=55, color="#d64545").encode(
                x=cls.asse_x(),
                y=alt.Y("Valore:Q"),
                tooltip=[
                    alt.Tooltip("Data:T", title="Data (Outlier)", format="%d/%m/%Y"),
                    alt.Tooltip("Valore:Q", title="Oscillazione reale", format=".2f"),
                    alt.Tooltip("Previsto:Q", title="Prevista", format=".2f"),
                    alt.Tooltip("Scostamento:Q", title="Scostamento residuo", format="%+.2f"),
                    alt.Tooltip("Z_score:Q", title="Deviazioni (σ)", format="+.1f"),
                ],
            )
            c = c + punti
        st.altair_chart(c, width="stretch")
