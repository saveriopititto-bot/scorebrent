"""Temperatura rispetto al normale stagionale."""
from __future__ import annotations

import numpy as np
import pandas as pd


class AnomaliaStagionale:
    """Temperatura giornaliera meno il suo normale stagionale.

    Il normale e' la media, su tutti gli anni disponibili, dello stesso giorno dell'anno, smussata con una media
    mobile circolare di `smussamento` giorni (il 29 febbraio conta come 28). Positivo = piu' caldo del normale."""

    def __init__(self, smussamento: int = 31):
        self.smussamento = smussamento

    @staticmethod
    def giorno_dell_anno(indice: pd.DatetimeIndex) -> np.ndarray:
        """Da 1 a 365; negli anni bisestili dal 1° marzo si toglie 1."""
        return np.minimum(indice.dayofyear - ((indice.is_leap_year) & (indice.dayofyear > 59)), 365)

    def calcola(self, temp: pd.Series) -> pd.Series:
        temp = temp.dropna()
        if temp.empty:
            return temp
        doy = self.giorno_dell_anno(temp.index)
        clima = temp.groupby(doy).mean().reindex(range(1, 366)).interpolate(limit_direction="both")
        k = self.smussamento // 2
        giro = pd.concat([clima.iloc[-k:], clima, clima.iloc[:k]])
        clima = giro.rolling(self.smussamento, center=True, min_periods=1).mean().iloc[k : k + 365]
        return temp - clima.to_numpy()[doy - 1]
