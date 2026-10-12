"""App «Prezzo del petrolio»: Brent da Yahoo Finance e analisi del suo andamento (matematica del paper "sisma", nel
pacchetto `brent`), con temperatura in Europa, OVX, rischio geopolitico e prezzi alla pompa come dati di contorno.
L'interfaccia è nel pacchetto `interfaccia`. Avvio: `streamlit run app.py`."""
from interfaccia.app import App

App().esegui()
