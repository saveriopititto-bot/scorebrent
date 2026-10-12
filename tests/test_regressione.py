"""Il modello deve riprodurre i risultati di riferimento salvati in tests/riferimenti/ (vedi tests/riferimenti.py)."""
import numpy as np
import pandas as pd
import pytest

from .riferimenti import CARTELLA, calcola


@pytest.fixture(scope="module")
def risultati(prezzi):
    return calcola(prezzi)


@pytest.mark.parametrize("nome", ["score", "rialzo", "oscillazione"])
def test_come_il_riferimento(risultati, nome):
    atteso = pd.read_csv(CARTELLA / f"{nome}.csv")
    ottenuto = risultati[nome].reset_index(drop=True)
    if nome == "score":
        ottenuto["data"] = ottenuto["data"].dt.strftime("%Y-%m-%d")
    assert list(ottenuto.columns) == list(atteso.columns)
    assert len(ottenuto) == len(atteso)
    for c in atteso.columns:
        if atteso[c].dtype.kind in "fi":
            np.testing.assert_allclose(ottenuto[c].astype(float), atteso[c], rtol=1e-7, atol=1e-10, err_msg=c)
        else:
            assert ottenuto[c].astype(str).tolist() == atteso[c].astype(str).tolist(), c


def test_esiti_dello_score_invariati(risultati):
    """L'esito (+1, 0, −1) che arriva a FuelMode deve essere identico giorno per giorno."""
    atteso = pd.read_csv(CARTELLA / "score.csv")
    assert (risultati["score"]["classe"].to_numpy() == atteso["classe"].to_numpy()).all()
