"""Menù in cima alla pagina: i bottoni delle sezioni e, sulla stessa riga, quelli delle schede della sezione."""
from __future__ import annotations

import streamlit as st

from .schede import SEZIONI, Scheda, Sezione


class Menu:
    CHIAVE = "sezione"  # anche il nome del parametro nell'indirizzo

    @classmethod
    def scegli(cls) -> tuple[Sezione, type[Scheda]]:
        """Disegna il menù e restituisce sezione e scheda scelte. Si apre sulla prima sezione, o su quella
        nell'indirizzo; ogni sezione ricorda l'ultima scheda aperta."""
        per_nome = {s.nome: s for s in SEZIONI}
        with st.container(key="card-menu", horizontal=True, vertical_alignment="center", gap="small"):
            # senza format_func: con bind l'indirizzo contiene il testo mostrato sul bottone
            nome = st.segmented_control("Sezione", list(per_nome), default=SEZIONI[0].nome, required=True,
                                        key=cls.CHIAVE, bind="query-params", wrap=True, label_visibility="collapsed")
            sezione = per_nome.get(nome, SEZIONI[0])
            per_titolo = {s.titolo: s for s in sezione.schede}
            titolo = st.segmented_control("Scheda", list(per_titolo), default=sezione.schede[0].titolo, required=True,
                                          key=f"scheda-{sezione.nome.lower()}", persist_state="session", wrap=True,
                                          label_visibility="collapsed")
        return sezione, per_titolo.get(titolo, sezione.schede[0])
