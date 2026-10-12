"""Menù in cima alla pagina: nome dell'app e un bottone per sezione."""
from __future__ import annotations

import streamlit as st

from .schede import SEZIONI, Sezione
from .stile import Palette


class Menu:
    CHIAVE = "sezione"  # anche il nome del parametro nell'indirizzo

    @classmethod
    def scegli(cls) -> Sezione:
        """Disegna il menù e restituisce la sezione scelta (la prima, se l'indirizzo non ne indica una)."""
        per_nome = {s.nome: s for s in SEZIONI}
        with st.container(key="card-menu", horizontal=True, horizontal_alignment="distribute",
                          vertical_alignment="center"):
            st.markdown(f'<p class="x-brand">{Palette.BRAND}</p>', unsafe_allow_html=True)
            # senza format_func: con bind l'indirizzo contiene il testo mostrato sul bottone
            nome = st.segmented_control("Sezione", list(per_nome), default=SEZIONI[0].nome, required=True,
                                        key=cls.CHIAVE, bind="query-params", label_visibility="collapsed")
        return per_nome.get(nome, SEZIONI[0])
