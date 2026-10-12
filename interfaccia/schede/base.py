"""Classe base delle schede."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

import streamlit as st

from ..contesto import Contesto, DatoFacoltativo
from ..impostazioni import Impostazioni


class Scheda(ABC):
    """Una scheda dell'app: il titolo è il suo bottone nel menù, `mostra` ne disegna il contenuto."""

    titolo: ClassVar[str]

    def __init__(self, ctx: Contesto):
        self.ctx = ctx

    @property
    def imp(self) -> Impostazioni:
        return self.ctx.imp

    @abstractmethod
    def mostra(self) -> None: ...

    def mostra_protetta(self) -> None:
        """Come `mostra`, ma un errore imprevisto resta dentro la scheda e non blocca le altre."""
        try:
            self.mostra()
        except Exception as e:
            st.exception(e)

    @staticmethod
    def manca(dato: DatoFacoltativo, interruttore: str, cosa: str) -> bool:
        """Se il dato non c'è dice perché (disattivato o non scaricato) e restituisce True."""
        if not dato.attivo:
            st.info(f"Per questa parte attiva «{interruttore}» in «Dati», nella barra laterale.")
        elif not dato.disponibile:
            st.warning(f"Non sono riuscito a scaricare {cosa}: {dato.errore}")
        return not dato.disponibile
