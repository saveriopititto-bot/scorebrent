from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from brent.cammino import CamminoPiano, Percorso

from ..grafici import Grafici
from ..stile import Palette
from .base import Scheda


class SchedaAndamento(Scheda):
    titolo = "Andamento"

    def mostra(self) -> None:
        serie, N, unita = self.ctx.serie, self.imp.N, self.imp.unita
        percorso = Percorso(serie.x[-(N + 1):], scala=100)        # variazioni percentuali (logaritmiche)
        h, ag = percorso.altezze, percorso.riepilogo()
        idx = serie.date[-len(h):]

        st.subheader("Di quanto è salito o sceso il prezzo in ogni periodo")
        st.caption("Ogni barra è la variazione percentuale del prezzo in euro rispetto al periodo prima. "
                   "Verde = salita, rosso = discesa.")
        Grafici.nel_tempo(pd.DataFrame({"Salita": np.clip(h, 0, None), "Discesa": np.clip(h, None, 0)}, index=idx),
                          "Variazione (%)", barre=True, colori=[Palette.VERDE, Palette.ROSSO])

        cA, cB = st.columns([1, 1])
        with cA:
            st.markdown(f"**Riepilogo degli ultimi {N} {unita}**")
            tab = pd.DataFrame(
                {
                    "Misura": ["Movimento complessivo (salite + discese)", "Totale delle salite", "Totale delle discese",
                               "Variazione tipica in un periodo", "Salita più grande", "Discesa più grande",
                               "Variazione dall'inizio alla fine"],
                    "Valore (%)": [ag.variazione_totale, ag.parte_positiva, ag.parte_negativa, ag.rms,
                                   ag.salto_max, ag.salto_min, ag.net],
                }
            )
            st.dataframe(tab, hide_index=True, column_config={"Valore (%)": st.column_config.NumberColumn(format="%+.2f")})
        with cB:
            self._forza(ag.efficienza)
        self._anticipo()

    def _forza(self, eff: float) -> None:
        c, base = self.ctx.confronto, self.ctx.base
        daily = Percorso(np.log(base["eur"].to_numpy()), scala=100).altezze
        sigma = float(np.sqrt(np.mean(daily[-60:] ** 2)))
        k = int(((base.index > c.data_prima) & (base.index <= c.t)).sum())
        z = (100 * np.log(c.ora["eur"] / c.prima["eur"])) / (sigma * np.sqrt(k)) if sigma > 0 and k > 0 else float("nan")
        st.metric("Quanto è stato lineare l'andamento", f"{eff:.2f}",
                  help="Da 0 a 1. Vicino a 1: il prezzo è andato dritto in una direzione. "
                       "Vicino a 0: è salito e sceso molto, ma alla fine si è spostato poco.")
        st.metric(f"Forza della variazione degli ultimi {self.imp.n} giorni", f"{z:+.2f} volte il normale",
                  help="La variazione di questi giorni confrontata con l'oscillazione abituale del prezzo "
                       "(calcolata sugli ultimi 60 giorni di borsa). Fra −1 e +1 è normale amministrazione; "
                       "oltre ±2 è un movimento forte.")
        st.caption(
            "La sola differenza fra inizio e fine non dice come ci si è arrivati: un periodo calmo e uno molto "
            "agitato possono finire allo stesso prezzo. Il movimento complessivo, la variazione tipica e la "
            "linearità descrivono proprio il percorso."
        )

    def _anticipo(self) -> None:
        serie, w, N, unita = self.ctx.serie, self.imp.w, self.imp.N, self.imp.unita
        st.subheader("Chi anticipa chi: il prezzo o l'agitazione del mercato?")
        A = CamminoPiano(serie.x, serie.y).area_levy_mobile(w)
        serie_A = pd.Series(A, index=serie.date).iloc[-N:]
        Grafici.nel_tempo(serie_A.rename("Indice di anticipo").to_frame(), "Indice di anticipo")
        ultimo = serie_A.dropna()
        st.metric("Valore più recente", f"{ultimo.iloc[-1]:+.2f}" if len(ultimo) else "non disponibile")
        st.caption(
            "L'«agitazione» è quanto il prezzo oscilla dentro lo stesso periodo (distanza fra massimo e minimo). "
            f"L'indice confronta, sugli ultimi {w} {unita} di volta in volta, l'ordine in cui si muovono prezzo e "
            "agitazione. **Sopra zero: si muove prima il prezzo e poi l'agitazione. Sotto zero: prima l'agitazione e "
            "poi il prezzo.** Vicino a zero: nessuno dei due anticipa l'altro. (Tecnicamente è l'«area di Lévy».)"
        )
