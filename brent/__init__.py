"""Modello matematico del Brent, senza Streamlit: lo usano sia l'app (interfaccia/) sia lo script che esporta
lo score in Supabase (esporta_score.py), così i due calcolano lo stesso valore.

Moduli
------
- fonti: download di prezzi (Yahoo Finance), temperature (Open-Meteo), rischio geopolitico (GPR) e prezzi alla pompa.
- mercato: prezzi del Brent in euro, raggruppamento per giorno o settimana e serie dell'analisi (x, y, m, o, g).
- cammino: variazioni fra periodi, riepiloghi e area di Lévy.
- meteo: temperatura rispetto al normale stagionale.
- modelli: standardizzazione, regressione logistica e ridge, prova a finestre scorrevoli, punteggi.
- rialzo: previsione del rialzo (classificazione) e sua prova.
- oscillazione: previsione dell'oscillazione (regressione sul logaritmo) e sua prova.
- score: score di rifornimento (adattamento dello SCORE 4.0).
- pompa: ritardo della pompa rispetto al Brent e verifica dello score sui prezzi alla pompa.
- capacita: Cp e Cpk dello score su finestre mobili, area di Lévy e rete neurale che li prevede.

Corrispondenze con il paper "sisma" (analisi differenziale + firma del cammino)
-------------------------------------------------------------------------------
| paper (sismologia)                     | Brent                                      |
|----------------------------------------|--------------------------------------------|
| bin temporale (mese / 5 giorni)        | bin giornaliero o settimanale              |
| magnitudo equivalente M_eq = livello   | x_k = ln(prezzo del Brent in euro)         |
| altezza differenziale h_k = dM_eq      | h_k = x_k - x_{k-1}  (rendimento log.)     |
| canale di tasso r = log10(1 + n)       | y_k = ln(1 + range intraday in %)          |
| censura dei bin vuoti                  | non serve (ogni giorno di borsa ha prezzo) |
| bersaglio: bin successivo > mediana    | bersaglio: rialzo oltre soglia nei prossimi|
|                                        | `orizzonte` bin                            |
| (nessuno)                              | m_k = temperatura in Europa rispetto al    |
|                                        | normale stagionale (Open-Meteo), opzionale |
| (nessuno)                              | o_k = volatilita' attesa dal mercato delle |
|                                        | opzioni sul petrolio (OVX), opzionale      |
| (nessuno)                              | g_k = rischio geopolitico (GPR di Caldara  |
|                                        | e Iacoviello), opzionale                   |
"""
