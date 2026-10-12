from __future__ import annotations

import pandas as pd
import streamlit as st

from ..grafici import Grafici
from .base import Scheda


class SchedaPrezzo(Scheda):
    titolo = "Prezzo"

    def mostra(self) -> None:
        c = self.ctx.confronto
        st.caption(f"Ultimo prezzo di chiusura: {c.t:%d/%m/%Y} · confrontato con il {c.data_prima:%d/%m/%Y}")
        c1, c2 = st.columns(2)
        c1.metric("Brent in dollari", f"{c.ora['usd']:.2f} $ al barile", f"{c.d_usd:+.2%}")
        c2.metric("Brent in euro", f"{c.ora['eur']:.2f} € al barile", f"{c.d_eur:+.2%}")
        base = self.ctx.base
        dati_grafico = base.loc[base.index >= c.t - pd.Timedelta(days=self.imp.giorni_grafico), ["usd", "eur"]]
        Grafici.nel_tempo(dati_grafico.rename(columns={"usd": "Dollari al barile", "eur": "Euro al barile"}),
                          "Prezzo al barile")
        st.caption("Fonte: Yahoo Finance, i prezzi possono arrivare in ritardo. Un barile sono 159 litri di petrolio greggio.")
