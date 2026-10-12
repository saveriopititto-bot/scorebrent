from __future__ import annotations

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from ..grafici import Grafici
from ..stile import Palette
from .base import Scheda
from .oscillazione import SchedaOscillazione


class SchedaProssimi(Scheda):
    """Sempre giorno per giorno, indipendente da «Raggruppa i prezzi»: usa l'oscillazione attesa dello score."""

    titolo = "Prossimi 5 giorni"
    FASCE = (("68", 1.0), ("95", 1.96))  # z per 2 casi su 3 e per 19 casi su 20
    GIORNI_SETTIMANA = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]

    @property
    def giorni(self) -> int:
        return self.ctx.parametri_score.orizzonte

    def fasce(self, p0: float, sig: float) -> pd.DataFrame:
        """Previsione centrale (il prezzo di oggi) e fasce p0·exp(±z·σ·√k) per oggi e i giorni di borsa successivi."""
        t = self.ctx.confronto.t
        k = np.arange(self.giorni + 1)                                   # 0 = oggi, poi i giorni di borsa successivi
        date_f = pd.DatetimeIndex([t]).append(pd.bdate_range(t + pd.Timedelta(days=1), periods=self.giorni))
        fut = pd.DataFrame({"Data": date_f, "Centro": p0})
        for nome, z in self.FASCE:
            fut[f"min{nome}"] = p0 * np.exp(-z * sig * np.sqrt(k))
            fut[f"max{nome}"] = p0 * np.exp(z * sig * np.sqrt(k))
        return fut

    def mostra(self) -> None:
        st.subheader(f"Il prezzo nei prossimi {self.giorni} giorni di borsa")
        valuta = st.radio("Mostra in", ["Euro", "Dollari"], horizontal=True, key="valuta_prev")
        col_p, simbolo = ("eur", "€") if valuta == "Euro" else ("usd", "$")
        if self.ctx.errore_score is not None:
            st.error(f"Non riesco a calcolare la previsione: {self.ctx.errore_score}")
            return
        t, sig = self.ctx.confronto.t, self.ctx.sigma_oggi
        p0 = float(self.ctx.confronto.ora[col_p])
        fut = self.fasce(p0, sig)

        c1, c2, c3 = st.columns(3)
        c1.metric(f"Prezzo al {t:%d/%m/%Y}", f"{p0:.2f} {simbolo} al barile")
        c2.metric("Oscillazione attesa", f"{100 * sig:.2f}% al giorno",
                  help=f"Dal modello «{SchedaOscillazione.NOMI[self.ctx.modello_score].removeprefix('Modello: ')}» "
                       f"della scheda «Oscillazione attesa», calcolato giorno per giorno sugli ultimi "
                       f"{self.ctx.parametri_score.finestra} giorni.")
        ultimo = fut.iloc[-1]
        c3.metric(f"Il {ultimo['Data']:%d/%m}, in 2 casi su 3", f"{ultimo['min68']:.2f} – {ultimo['max68']:.2f} {simbolo}",
                  help="Intervallo in cui il prezzo dovrebbe trovarsi in circa 2 casi su 3 alla fine dei 5 giorni.")

        self._grafico(fut, col_p, simbolo)
        self._tabella(fut, simbolo)
        st.caption(
            "**Come leggerla.** La linea tratteggiata è la previsione centrale: resta al prezzo di oggi perché la "
            "direzione del Brent non si può prevedere dal passato (lo mostra la scheda «Prova di previsione»). Quello "
            "che si può prevedere è quanto il prezzo si muoverà: la fascia più scura è dove dovrebbe trovarsi in circa "
            "2 casi su 3, quella più chiara in circa 19 casi su 20. La fascia si allarga perché più si guarda avanti, "
            "più il prezzo ha tempo per allontanarsi. Non tiene conto delle festività di borsa e non è un consiglio "
            "di investimento."
        )

    def _grafico(self, fut: pd.DataFrame, col_p: str, simbolo: str) -> None:
        base, t = self.ctx.base, self.ctx.confronto.t
        storico = base.loc[base.index >= t - pd.Timedelta(days=42), [col_p]].rename(columns={col_p: "Valore"})
        linee = pd.concat([
            storico.rename_axis("Data").reset_index().assign(Serie="Prezzo vero"),
            fut[["Data", "Centro"]].rename(columns={"Centro": "Valore"}).assign(Serie="Previsione"),
        ])
        asse_x = Grafici.asse_x()

        def fascia(nome: str, opacita: float) -> alt.Chart:
            return alt.Chart(fut).mark_area(opacity=opacita, color=Palette.BLUE_GREEN).encode(
                x=asse_x, y=alt.Y(f"min{nome}:Q"), y2=f"max{nome}:Q",
                tooltip=[alt.Tooltip("Data:T", title="Data", format="%d/%m/%Y"),
                         alt.Tooltip(f"min{nome}:Q", title="Da", format=".2f"),
                         alt.Tooltip(f"max{nome}:Q", title="A", format=".2f")])

        serie_l = alt.Chart(linee).mark_line().encode(
            x=asse_x,
            y=alt.Y("Valore:Q", title=f"{simbolo} al barile", scale=alt.Scale(zero=False)),
            color=alt.Color("Serie:N", title=None, legend=alt.Legend(orient="bottom"),
                            scale=alt.Scale(domain=["Prezzo vero", "Previsione"], range=[Palette.DEEP, Palette.BLUE_GREEN])),
            strokeDash=alt.StrokeDash("Serie:N", legend=None,
                                      scale=alt.Scale(domain=["Prezzo vero", "Previsione"], range=[[1, 0], [6, 4]])),
            tooltip=[alt.Tooltip("Data:T", title="Data", format="%d/%m/%Y"), alt.Tooltip("Serie:N", title="Serie"),
                     alt.Tooltip("Valore:Q", title=f"{simbolo} al barile", format=".2f")],
        )
        st.altair_chart(fascia("95", 0.12) + fascia("68", 0.25) + serie_l, width="stretch")

    def _tabella(self, fut: pd.DataFrame, simbolo: str) -> None:
        tabella = fut.iloc[1:].assign(**{
            "Giorno": [f"{self.GIORNI_SETTIMANA[d.dayofweek]} {d:%d/%m}" for d in fut["Data"].iloc[1:]],
            "Previsione": fut["Centro"].iloc[1:].map(f"{{:.2f}} {simbolo}".format),
            "2 casi su 3": [f"{a:.2f} – {b:.2f} {simbolo}" for a, b in zip(fut.min68.iloc[1:], fut.max68.iloc[1:])],
            "19 casi su 20": [f"{a:.2f} – {b:.2f} {simbolo}" for a, b in zip(fut.min95.iloc[1:], fut.max95.iloc[1:])],
        })[["Giorno", "Previsione", "2 casi su 3", "19 casi su 20"]]
        st.dataframe(tabella, hide_index=True)
