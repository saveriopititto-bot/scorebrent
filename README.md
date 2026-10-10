# Prezzo del petrolio (Brent)

App [Streamlit](https://streamlit.io) che scarica il prezzo del petrolio Brent da Yahoo Finance, lo converte in euro e ne analizza l'andamento. Può usare anche la temperatura in Europa, da [Open-Meteo](https://open-meteo.com), per capire se il caldo o il freddo aiutano a prevedere il prezzo. Tutta l'interfaccia è in italiano, con i termini tecnici spiegati in parole semplici.

## Cosa mostra

L'app ha cinque schede.

- **Prezzo**: ultimo prezzo di chiusura in dollari e in euro al barile, variazione rispetto a *n* giorni prima e grafico del periodo scelto (da 1 mese a tutto lo storico, che parte dal 2007).
- **Andamento**: di quanto il prezzo è salito o sceso in ogni giorno o settimana, con un riepilogo:
  - movimento complessivo, variazione tipica, salita e discesa più grandi;
  - quanto è stato lineare l'andamento;
  - forza della variazione recente rispetto all'oscillazione normale;
  - un indice che dice se si muove prima il prezzo o l'agitazione del mercato (l'«area di Lévy»).
- **Meteo**: quanto fa più caldo o più freddo del normale in Europa, con il grafico accanto a quello del prezzo.
  - La temperatura è la media giornaliera di Berlino, Parigi, Londra, Milano e Madrid.
  - Il «normale» è la media dello stesso periodo dell'anno su tutti gli anni disponibili.
- **Prova di previsione**: controlla se l'andamento passato aiuta davvero a prevedere un rialzo nei giorni o nelle settimane successive.
  - La prova procede a finestre scorrevoli su tutto lo storico. Il primo 40% serve solo per imparare; poi, ogni mese circa, il modello si riaddestra su tutto il passato e prevede il mese successivo.
  - Il risultato è confrontato con una stima di riferimento che non guarda il passato recente. Per ogni gruppo di dati si vede anche in quanti anni fa meglio del riferimento.
  - Fra i dati usati per prevedere c'è l'oscillazione recente del prezzo: *sigma* (deviazione standard) e *MAD* (deviazione assoluta mediana, meno sensibile ai salti isolati). Contano soprattutto quando si chiede un rialzo minimo sopra lo 0%.
  - Se la temperatura è attiva, la prova include anche due gruppi di dati con la temperatura rispetto al normale.
- **Oscillazione attesa**: quanto si muoverà il prezzo nei prossimi giorni o settimane, in % e in euro al barile. Prevedere quanto si muove è molto più fattibile che prevedere in che direzione, perché i periodi agitati tendono a durare.
  - Il modello è una regressione sul logaritmo dell'oscillazione, che usa sigma e MAD recenti (su 5 periodi e sulla finestra mobile) e l'agitazione, cioè la distanza fra massimo e minimo.
  - La prova a finestre scorrevoli lo confronta con due riferimenti: «come nel periodo appena passato» e «media storica».
  - Gli errori sono misurati come *bias* (errore medio), *MAD* (errore assoluto medio) e *sigma* (deviazione standard dell'errore). Un grafico mostra l'oscillazione vera e quella prevista.

Le impostazioni dell'analisi sono nella barra laterale: raggruppamento per giorni o settimane, periodo analizzato, finestra mobile, orizzonte, soglia di rialzo e uso della temperatura.

## Avvio

Serve Python 3.10 o successivo.

```bash
pip install -r requirements.txt
streamlit run app.py
```

L'app si apre nel browser all'indirizzo http://localhost:8501. Deve poter raggiungere:

- Yahoo Finance (`query1.finance.yahoo.com`, `query2.finance.yahoo.com`, `fc.yahoo.com`) per i prezzi;
- Open-Meteo (`archive-api.open-meteo.com`, `api.open-meteo.com`) per le temperature. Se Open-Meteo non risponde, l'app funziona lo stesso senza la temperatura.

## File

| File | Contenuto |
|---|---|
| `app.py` | L'interfaccia: download di prezzi e temperature, schede, grafici e testi. |
| `brent_math.py` | La matematica: variazioni fra periodi, riepiloghi, area di Lévy, sigma e MAD, temperatura rispetto al normale, regressione logistica, previsione dell'oscillazione e prova a finestre scorrevoli. Non dipende da Streamlit. |
| `requirements.txt` | Le librerie Python necessarie. |
| `.streamlit/config.toml` | Configurazione di Streamlit: nasconde il pulsante «Deploy». |

## Dati e avvertenze

- **Fonti**: contratto future sul Brent `BZ=F` (dollari al barile) e cambio `EURUSD=X`, scaricati con [yfinance](https://github.com/ranaroussi/yfinance) per tutto lo storico disponibile e aggiornati al massimo ogni 15 minuti.
- **Meteo**: temperatura media giornaliera da [Open-Meteo.com](https://open-meteo.com), licenza CC BY 4.0, aggiornata al massimo ogni 6 ore. Lo storico arriva con qualche giorno di ritardo: gli ultimi giorni vengono dalle previsioni. L'API gratuita di Open-Meteo è per uso non commerciale.
- **Salti fra contratti**: `BZ=F` è un contratto con scadenza mensile. Il passaggio da un contratto al successivo produce piccoli salti che non sono veri movimenti del mercato.
- **Previsioni**: i periodi vicini si sovrappongono, quindi i casi davvero indipendenti nella prova di previsione sono meno di quanti sembrano.
- **Uso**: i dati possono arrivare in ritardo. L'app ha scopo di analisi e non è un consiglio di investimento.
