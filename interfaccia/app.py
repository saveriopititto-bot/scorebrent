"""L'app: impostazioni, dati e schede."""
from __future__ import annotations

import streamlit as st

from .contesto import Contesto
from .impostazioni import Impostazioni
from .menu import Menu
from .schede import SchedaScore
from .stile import Stile


class App:
    """Con ?pagina=score l'app mostra solo la scheda «Score rifornimento», senza titolo né barra laterale: è la
    versione incorporata in FuelMode (scheda «Petrolio»). Le impostazioni restano quelle predefinite."""

    def __init__(self):
        self.solo_score = st.query_params.get("pagina") == "score"

    def esegui(self) -> None:
        st.set_page_config(page_title="Prezzo del petrolio", page_icon="🛢️", layout="wide",
                           initial_sidebar_state="collapsed" if self.solo_score else "auto")
        Stile.applica()  # stile di FuelMode
        if self.solo_score:
            Stile.senza_cornice()

        ctx = Contesto.carica(Impostazioni.da_barra_laterale())
        if self.solo_score:
            scheda = SchedaScore
        else:
            _, scheda = Menu.scegli()
        with st.container(key="card-scheda"):  # si calcola solo la scheda aperta
            scheda(ctx).mostra_protetta()
