"""Prezzi alla pompa (settimanali): con quanto ritardo seguono il Brent e verifica dello score."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .score import Esito


@dataclass(frozen=True)
class VerificaPompa:
    """`tabella`: per esito, variazione media della pompa dopo 1 e 2 settimane in centesimi al litro.
    `risparmio`: quanto si guadagna in media, per pieno, seguendo lo score nelle settimane con +1 o -1."""

    tabella: pd.DataFrame
    risparmio: pd.DataFrame


class AnalisiPompa:
    """Prezzi settimanali alla pompa: una colonna per carburante, euro al litro, indice = lunedì del listino."""

    LITRI_BARILE = 158.987

    def __init__(self, prezzi: pd.DataFrame, max_ritardo: int = 4, settimane=(1, 2), litri: float = 50.0):
        self.prezzi = prezzi
        self.max_ritardo, self.settimane, self.litri = max_ritardo, settimane, litri

    @property
    def carburanti(self) -> list[str]:
        return list(self.prezzi.columns)

    def brent_al_litro(self, eur_barile: pd.Series) -> pd.Series:
        """Il Brent in euro al litro, allineato alle settimane del listino."""
        return eur_barile.reindex(self.prezzi.index, method="ffill") / self.LITRI_BARILE

    def ritardo(self, brent_l: pd.Series, carburante: str) -> pd.DataFrame:
        """Quanto e con che ritardo la pompa segue il Brent, su serie settimanali allineate. Per ogni ritardo k in
        settimane: correlazione fra la variazione del Brent nella settimana w e quella della pompa nella settimana
        w+k, e quota trasferita (pendenza della retta: centesimi alla pompa per centesimo di Brent)."""
        db = brent_l.diff()
        dp = self.prezzi[carburante].diff()
        righe = []
        for k in range(self.max_ritardo + 1):
            d = pd.concat([db, dp.shift(-k)], axis=1).dropna()
            if len(d) < 30:
                continue
            x, y = d.iloc[:, 0].values, d.iloc[:, 1].values
            righe.append({"Ritardo (settimane)": k, "Correlazione": float(np.corrcoef(x, y)[0, 1]),
                          "Quota trasferita": float(np.polyfit(x, y, 1)[0]), "Settimane": len(d)})
        return pd.DataFrame(righe)

    def verifica_score(self, classe_giornaliera: pd.Series) -> VerificaPompa:
        """Verifica dello score sui prezzi alla pompa. L'esito di ogni settimana è quello dello score nel lunedì del
        listino (o nell'ultimo giorno di borsa prima). Con +1 si rifornisce subito invece di dopo (si guadagna
        l'aumento), con -1 si aspetta (si guadagna il calo)."""
        classe = classe_giornaliera.reindex(self.prezzi.index, method="ffill").dropna()
        pompa = self.prezzi.loc[classe.index]
        righe, risparmio = [], []
        for nome_c, sel in [(e.codice, classe == e.value) for e in Esito] + [("Tutte", classe.notna())]:
            riga = {"Classe": nome_c, "Settimane": int(sel.sum())}
            for carb in pompa.columns:
                for h in self.settimane:
                    dv = (pompa[carb].shift(-h) - pompa[carb])[sel].dropna()
                    riga[f"{carb} dopo {h}"] = float(100 * dv.mean()) if len(dv) else np.nan
            righe.append(riga)
        segnale = classe.where(classe != 0)
        for carb in pompa.columns:
            for h in self.settimane:
                g = (segnale * (pompa[carb].shift(-h) - pompa[carb])).dropna()
                risparmio.append({"Carburante": carb, "Settimane": h, "Segnali": len(g),
                                  "Risparmio medio (€ per pieno)": float(self.litri * g.mean()) if len(g) else np.nan,
                                  "Volte in cui ha fatto risparmiare": float((g > 0).mean()) if len(g) else np.nan})
        return VerificaPompa(pd.DataFrame(righe), pd.DataFrame(risparmio))
