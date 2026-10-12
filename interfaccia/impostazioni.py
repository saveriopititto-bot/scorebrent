"""Impostazioni scelte dall'utente nella barra laterale."""
from __future__ import annotations

from dataclasses import dataclass, replace

import streamlit as st

from brent.fonti import FonteMeteo
from brent.mercato import Frequenza


@dataclass(frozen=True)
class Impostazioni:
    n: int                 # giorni per la variazione mostrata in alto
    giorni_grafico: int    # periodo mostrato nei grafici
    freq: Frequenza
    N: int                 # periodi recenti analizzati nella scheda «Andamento»
    w: int                 # ampiezza della finestra mobile
    orizzonte: int
    soglia: float          # rialzo minimo da prevedere, in %
    usa_meteo: bool
    usa_ovx: bool
    usa_gpr: bool
    usa_pompa: bool
    alpha: float           # sensibilità dello score alla turbolenza
    theta: float           # soglia dello score

    PERIODI = {"1 mese": 30, "3 mesi": 91, "6 mesi": 182, "1 anno": 365, "5 anni": 1826, "Tutto lo storico": 100_000}

    @property
    def unita(self) -> str:
        return self.freq.unita

    def per_score(self) -> Impostazioni:
        """Versione incorporata in FuelMode: meteo e rischio geopolitico non servono allo score."""
        return replace(self, usa_meteo=False, usa_gpr=False)

    @classmethod
    def da_barra_laterale(cls) -> Impostazioni:
        """Quattro gruppi, nell'ordine del menù: score, prezzo e grafici, analisi, dati."""
        sb = st.sidebar
        sb.subheader("Score rifornimento")
        alpha = sb.slider("Sensibilità alla turbolenza (α)", 0.0, 2.0, 1.0, 0.1,
                          help="Quanto lo score si avvicina a «neutro» quando il mercato è più agitato del normale. "
                               "0 = nessuno smorzamento; lo SCORE 4.0 suggerisce valori fra 0.5 e 1.2.")
        theta = sb.slider("Soglia (θ)", 0.25, 3.0, 1.0, 0.25,
                          help="Di quante oscillazioni tipiche il Brent deve allontanarsi dalla media dei 30 giorni "
                               "per dare +1 o −1. Più alta = segnali più rari ma più netti.")

        sb.subheader("Prezzo e grafici")
        mesi = sb.selectbox("Periodo mostrato nei grafici", list(cls.PERIODI), index=1)
        n = sb.slider("Confronta con il prezzo di quanti giorni fa", 1, 60, 7)

        sb.subheader("Analisi")
        freq = Frequenza(sb.radio("Raggruppa i prezzi", [f.value for f in Frequenza]))
        unita = freq.unita
        N = sb.slider(f"Quanti {unita} analizzare (i più recenti)", 20, 500, 120)
        w = sb.slider(f"Ampiezza della finestra mobile ({unita})", 5, 60, 20,
                      help="Quanti periodi consecutivi si guardano insieme per sigma, MAD e «chi anticipa chi».")
        orizzonte = sb.slider(f"Quanto avanti prevedere ({unita})", 1, 20, 5)
        soglia = sb.number_input("Rialzo minimo da prevedere (%)", value=0.0, step=0.5,
                                 help="0% = basta che il prezzo salga; 2% = deve salire di più del 2%.")

        sb.subheader("Dati")
        usa_pompa = sb.checkbox("Prezzi alla pompa in Italia", value=True,
                                help="Medie settimanali di benzina e gasolio (Weekly Oil Bulletin della Commissione "
                                     "Europea). Per la scheda «Pompa (Italia)» e la verifica dello score.")
        usa_ovx = sb.checkbox("Volatilità attesa dal mercato (OVX)", value=True,
                              help="Quanto gli operatori si aspettano che il petrolio oscilli nei prossimi 30 giorni, "
                                   "dai prezzi delle opzioni. Entra nello score e nelle previsioni.")
        usa_meteo = sb.checkbox("Temperatura in Europa", value=True,
                                help=f"Media di {', '.join(FonteMeteo.CITTA)}, da Open-Meteo. Per la scheda «Meteo» "
                                     "e le previsioni.")
        usa_gpr = sb.checkbox("Rischio geopolitico (GPR)", value=True,
                              help="Articoli di giornale su guerre, terrorismo e tensioni internazionali. Per la scheda "
                                   "«Geopolitica» e le previsioni.")
        if sb.button("Aggiorna i dati", icon=":material/refresh:", help="Riscarica tutto invece di usare i dati in "
                                                                          "memoria."):
            st.cache_data.clear()
        return cls(n, cls.PERIODI[mesi], freq, N, w, orizzonte, soglia, usa_meteo, usa_ovx, usa_gpr, usa_pompa,
                   alpha, theta)
