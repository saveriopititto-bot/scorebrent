from __future__ import annotations

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from brent.pompa import AnalisiPompa
from brent.score import Esito

from ..grafici import Grafici
from ..stile import Palette
from .base import Scheda


class SchedaScore(Scheda):
    titolo = "Score rifornimento"

    TESTI = {
        Esito.RIFORNISCI: ("+1 · Rifornisci", "Il Brent è sopra la media degli ultimi 30 giorni più di quanto spieghi il "
                           "suo normale oscillare: i prezzi alla pompa tendono a seguirlo con qualche giorno di ritardo, "
                           "quindi conviene fare il pieno prima che salgano."),
        Esito.NEUTRO: ("0 · Neutro", "Il Brent è vicino alla sua media degli ultimi 30 giorni, oppure il mercato è troppo "
                       "agitato per fidarsi dello scarto: nessuna indicazione, rifornisci quando ti serve."),
        Esito.ASPETTA: ("−1 · Aspetta", "Il Brent è sotto la media degli ultimi 30 giorni più di quanto spieghi il suo "
                        "normale oscillare: i prezzi alla pompa tendono a scendere nei prossimi giorni, quindi se puoi "
                        "conviene aspettare."),
    }
    AVVISI = {Esito.RIFORNISCI: st.success, Esito.NEUTRO: st.info, Esito.ASPETTA: st.warning}
    COLORI = {Esito.RIFORNISCI: Palette.VERDE, Esito.NEUTRO: Palette.ORANGE, Esito.ASPETTA: Palette.ROSSO}

    def mostra(self) -> None:
        st.subheader("Conviene fare rifornimento adesso?")
        if self.ctx.errore_score is not None:
            st.error(f"Non riesco a calcolare lo score: {self.ctx.errore_score}")
            return
        self._oggi()
        self._grafico()
        self._verifica_brent()
        self._verifica_pompa()
        st.caption("Analisi sui dati di mercato, non è un consiglio di investimento.")

    def _oggi(self) -> None:
        oggi = self.ctx.score.oggi
        p = self.ctx.parametri_score
        esito = Esito(int(oggi["classe"]))
        titolo, testo = self.TESTI[esito]
        self.AVVISI[esito](f"**{titolo}** — {testo}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Score S", f"{oggi['S']:+.2f}", help=f"+1 da {p.soglia:+.2f} in su, −1 da {-p.soglia:+.2f} in giù.")
        c2.metric("Brent rispetto alla media 30 giorni", f"{100 * (np.exp(oggi['scarto']) - 1):+.1f}%",
                  help=f"Oggi {oggi['prezzo']:.2f} € al barile, media degli ultimi 30 giorni {oggi['media']:.2f} €.")
        c3.metric("Oscillazione attesa in 5 giorni", f"±{100 * oggi['sigma'] * np.sqrt(p.orizzonte):.1f}%",
                  help="Il «rumore normale» con cui si confronta lo scarto dalla media.")
        c4.metric("Stabilità", f"{oggi['stabilita']:.2f}",
                  help="1 = mercato calmo, segnale pieno. Sotto 1 il mercato è più agitato del normale e lo score "
                       "viene avvicinato a zero.")

        st.latex(r"S=\frac{\ln\left(P_t/\bar P_{30}\right)}{\sigma\sqrt{5}}\cdot e^{-\alpha\,\max\left(0,\;"
                 r"\sigma/\sigma_{norm}-1\right)}")
        st.caption(f"Adattamento dello SCORE 4.0, con α = {p.alpha:.1f} e θ = {p.soglia:.2f}. I passaggi sono nella "
                   "scheda «Formule».")

    def _grafico(self) -> None:
        theta = self.ctx.parametri_score.soglia
        inizio_s = self.ctx.confronto.t - pd.Timedelta(days=self.imp.giorni_grafico)
        d_s = self.ctx.score.tabella.loc[inizio_s:, ["S", "classe"]].dropna().rename_axis("Data").reset_index()
        if not len(d_s):
            return
        d_s["Esito"] = d_s["classe"].map({e.value: e.etichetta for e in Esito})
        asse = Grafici.asse_x()
        punti = alt.Chart(d_s).mark_circle(size=28).encode(
            x=asse, y=alt.Y("S:Q", title="Score S"),
            color=alt.Color("Esito:N", title=None, legend=alt.Legend(orient="bottom"),
                            scale=alt.Scale(domain=[e.etichetta for e in Esito], range=list(self.COLORI.values()))),
            tooltip=[alt.Tooltip("Data:T", title="Data", format="%d/%m/%Y"), alt.Tooltip("S:Q", format="+.2f"),
                     alt.Tooltip("Esito:N")])
        linea = alt.Chart(d_s).mark_line(color=Palette.N400, strokeWidth=1).encode(x=asse, y="S:Q")
        soglie = alt.Chart(pd.DataFrame({"y": [theta, -theta]})).mark_rule(strokeDash=[4, 4], color=Palette.N500
                                                                          ).encode(y="y:Q")
        st.altair_chart(linea + punti + soglie, width="stretch")
        st.caption("Lo score negli ultimi mesi; le linee tratteggiate sono le soglie ±θ.")

    @staticmethod
    def _etichette(totale: str, nome_totale: str) -> dict[str, str]:
        return {**{e.codice: e.etichetta for e in Esito}, totale: nome_totale}

    def _verifica_brent(self) -> None:
        st.markdown("**Ha funzionato in passato?** Cosa ha fatto il Brent nei 5 giorni di borsa dopo ogni esito "
                    "(con l'oscillazione attesa calcolata ogni volta senza guardare il futuro).")
        sc = self.ctx.score.tabella
        ver = self.ctx.parametri_score.verifica(sc).assign(
            Classe=lambda d: d["Classe"].map(self._etichette("Tutti", "Tutti i giorni")),
            Quota=lambda d: 100 * d["Quota"], **{"Giorni in salita": lambda d: 100 * d["Giorni in salita"]})
        st.dataframe(
            ver.rename(columns={"Classe": "Esito", "Quota": "Quota dei giorni (%)",
                                "Variazione media": "Brent nei 5 giorni dopo (%)",
                                "Giorni in salita": "Volte in cui è salito (%)"}),
            hide_index=True,
            column_config={"Quota dei giorni (%)": st.column_config.NumberColumn(format="%.0f"),
                           "Brent nei 5 giorni dopo (%)": st.column_config.NumberColumn(format="%+.2f"),
                           "Volte in cui è salito (%)": st.column_config.NumberColumn(format="%.0f")},
        )
        periodo = sc["S"].dropna()
        st.caption(
            f"Dal {periodo.index[0]:%d/%m/%Y} al {periodo.index[-1]:%d/%m/%Y}. Il segnale è coerente se dopo un +1 il "
            "Brent sale più spesso che in «Tutti i giorni» e dopo un −1 meno spesso."
        )

    def _verifica_pompa(self) -> None:
        st.markdown("**Verifica con i prezzi alla pompa in Italia**")
        pompa = self.ctx.pompa
        if self.manca(pompa, "Prezzi alla pompa in Italia", "i prezzi alla pompa"):
            return
        ver = AnalisiPompa(pompa.valore).verifica_score(self.ctx.score.tabella["classe"])
        colonne = {f"{c} dopo {h}": f"{c} dopo {h} settiman{'a' if h == 1 else 'e'}"
                   for c in ("Benzina", "Gasolio") for h in (1, 2)}
        st.dataframe(
            ver.tabella.assign(Classe=lambda d: d["Classe"].map(self._etichette("Tutte", "Tutte le settimane")))
            .rename(columns={"Classe": "Esito", **colonne}),
            hide_index=True,
            column_config={c: st.column_config.NumberColumn(format="%+.2f", help="Variazione media del prezzo alla "
                                                            "pompa, in centesimi al litro")
                           for c in colonne.values()},
        )
        risp = ver.risparmio
        r = risp.assign(**{"Volte in cui ha fatto risparmiare": 100 * risp["Volte in cui ha fatto risparmiare"],
                           "Settimane": risp["Settimane"].map({1: "1 settimana", 2: "2 settimane"})})
        st.dataframe(
            r.rename(columns={"Settimane": "Confronto con", "Segnali": "Settimane con +1 o −1",
                              "Volte in cui ha fatto risparmiare": "Volte in cui ha fatto risparmiare (%)"}),
            hide_index=True,
            column_config={"Risparmio medio (€ per pieno)": st.column_config.NumberColumn(format="%+.2f €"),
                           "Volte in cui ha fatto risparmiare (%)": st.column_config.NumberColumn(format="%.0f")},
        )
        st.caption(
            "Sopra: come è cambiata la pompa dopo ogni esito (score del lunedì del listino); funziona se dopo un +1 "
            "sale e dopo un −1 scende. Sotto: quanto si è risparmiato in media su un pieno da 50 litri seguendo lo "
            "score (+1 = pieno subito, −1 = aspettare 1 o 2 settimane)."
        )
