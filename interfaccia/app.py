"""L'app: impostazioni, dati e schede."""
from __future__ import annotations

import streamlit as st

from .contesto import Contesto
from .impostazioni import Impostazioni
from .schede import SCHEDE, SchedaScore
from .stile import Stile


class App:
    """Con ?pagina=score l'app mostra solo la scheda «Score rifornimento», senza titolo né barra laterale: è la
    versione incorporata in FuelMode (scheda «Petrolio»). Le impostazioni restano quelle predefinite."""

    def __init__(self):
        self.solo_score = st.query_params.get("pagina") == "score"

    def esegui(self) -> None:
        st.set_page_config(page_title="Prezzo del petrolio", page_icon="🛢️", layout="wide",
                           initial_sidebar_state="collapsed" if self.solo_score else "auto")
        Stile.applica()  # stile di FuelMode; il titolo dell'app è nella barra delle schede
        if self.solo_score:
            Stile.senza_cornice()

        imp = Impostazioni.da_barra_laterale()
        if self.solo_score:
            imp = imp.per_score()
        ctx = Contesto.carica(imp)

        if self.solo_score:
            with st.container(key="card-score"):  # scheda bianca, come nella versione con le schede
                SchedaScore(ctx).mostra_protetta()
            return
        for scheda, tab in zip(SCHEDE, st.tabs([s.titolo for s in SCHEDE])):
            with tab:
                scheda(ctx).mostra_protetta()
