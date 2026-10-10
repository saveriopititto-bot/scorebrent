# Prezzo del petrolio (Brent)

App [Streamlit](https://streamlit.io) che scarica il prezzo del petrolio Brent da Yahoo Finance, lo converte in euro e ne analizza l'andamento. Ogni giorno dà uno **score di rifornimento** (+1 rifornisci, 0 neutro, −1 aspetta) e una previsione per i prossimi 5 giorni. Può usare anche la temperatura in Europa, da [Open-Meteo](https://open-meteo.com), l'indice di volatilità del petrolio OVX, il rischio geopolitico (GPR) e i prezzi settimanali alla pompa in Italia, per capire se aiutano a prevedere il prezzo e quanto oscillerà. Tutta l'interfaccia è in italiano, con i termini tecnici spiegati in parole semplici.

## Da dove partire

1. **Score rifornimento**: l'indicazione di oggi (+1 rifornisci, 0 neutro, −1 aspetta). In fondo alla scheda c'è la verifica con i prezzi veri alla pompa, che dice se seguirlo ha fatto risparmiare.
2. **Prossimi 5 giorni**: fin dove può arrivare il Brent nei prossimi giorni.
3. **Pompa (Italia)**: i prezzi medi di benzina e gasolio, e dopo quante settimane seguono il Brent.

Le altre schede servono ad approfondire: andamento del prezzo, meteo, geopolitica e le prove dei modelli di previsione.

## Cosa mostra

L'app ha nove schede.

- **Prezzo**: ultimo prezzo di chiusura in dollari e in euro al barile, variazione rispetto a *n* giorni prima e grafico del periodo scelto (da 1 mese a tutto lo storico, che parte dal 2007).
- **Score rifornimento**: un adattamento dello SCORE 4.0 che dà ogni giorno uno di tre esiti.
  - **+1 rifornisci**: il Brent è sopra la media degli ultimi 30 giorni più di quanto spieghi il suo normale oscillare. I prezzi alla pompa tendono a seguirlo con qualche giorno o settimana di ritardo (la scheda «Pompa (Italia)» misura quanto), quindi conviene fare il pieno prima che salgano.
  - **−1 aspetta**: il Brent è sotto la media più del normale, e la pompa tenderà a scendere.
  - **0 neutro**: il Brent è vicino alla media, oppure il mercato è troppo agitato per fidarsi dello scarto.
  - La scheda mostra lo score di oggi e le sue parti, la formula e un grafico degli ultimi mesi con le soglie.
  - Una tabella mostra cosa ha fatto il Brent nei 5 giorni dopo ogni esito, su tutto lo storico.
  - Se i prezzi alla pompa sono attivi, una verifica mostra come è cambiato il prezzo medio italiano di benzina e gasolio 1 e 2 settimane dopo ogni esito. Dice anche quanto si sarebbe risparmiato in media, per pieno da 50 litri, seguendo lo score.
- **Prossimi 5 giorni**: grafico con il prezzo delle ultime settimane e, tratteggiata, la previsione per i prossimi 5 giorni di borsa, in euro o in dollari.
  - La linea tratteggiata resta al prezzo di oggi, perché la direzione del Brent non si può prevedere dal passato.
  - Attorno ci sono due fasce: dove il prezzo dovrebbe trovarsi in circa 2 casi su 3 e in circa 19 casi su 20. Si allargano giorno dopo giorno.
  - L'ampiezza delle fasce viene dalla previsione dell'oscillazione (modello «+ agitazione e OVX», giorno per giorno, finestra di 20 giorni) e non dipende da «Raggruppa i prezzi».
  - Una tabella riporta gli stessi valori giorno per giorno.
- **Pompa (Italia)**: prezzi medi nazionali settimanali di benzina e gasolio, tasse incluse, dal Weekly Oil Bulletin della Commissione Europea.
  - Ultimo listino con la variazione rispetto alla settimana prima, e grafico accanto al Brent convertito in euro al litro.
  - Tabella del ritardo: per 0–4 settimane, quanto la variazione della pompa segue quella del Brent (correlazione) e quanti centesimi alla pompa segue ogni centesimo di Brent (quota trasferita). Una frase riassume dopo quante settimane reagisce la pompa e quanto trasferisce in tutto.
- **Andamento**: di quanto il prezzo è salito o sceso in ogni giorno o settimana, con un riepilogo:
  - movimento complessivo, variazione tipica, salita e discesa più grandi;
  - quanto è stato lineare l'andamento;
  - forza della variazione recente rispetto all'oscillazione normale;
  - un indice che dice se si muove prima il prezzo o l'agitazione del mercato (l'«area di Lévy»).
- **Meteo**: quanto fa più caldo o più freddo del normale in Europa, con il grafico accanto a quello del prezzo.
  - La temperatura è la media giornaliera di Berlino, Parigi, Londra, Milano e Madrid.
  - Il «normale» è la media dello stesso periodo dell'anno su tutti gli anni disponibili.
- **Geopolitica**: il Geopolitical Risk Index (GPR) di Caldara e Iacoviello, accanto al grafico del prezzo.
  - Media degli ultimi 7 e 30 giorni, e la divisione fra minacce e atti; 100 è il livello medio dal 1985 al 2019.
  - Grafico delle medie su 7 e 30 giorni e tabella degli eventi principali più recenti, con le etichette originali in inglese.
- **Prova di previsione**: controlla se l'andamento passato aiuta davvero a prevedere un rialzo nei giorni o nelle settimane successive.
  - La prova procede a finestre scorrevoli su tutto lo storico. Il primo 40% serve solo per imparare; poi, ogni mese circa, il modello si riaddestra su tutto il passato e prevede il mese successivo.
  - Il risultato è confrontato con una stima di riferimento che non guarda il passato recente. Per ogni gruppo di dati si vede anche in quanti anni fa meglio del riferimento.
  - Fra i dati usati per prevedere c'è l'oscillazione recente del prezzo: *sigma* (deviazione standard) e *MAD* (deviazione assoluta mediana, meno sensibile ai salti isolati). Contano soprattutto quando si chiede un rialzo minimo sopra lo 0%.
  - Se la temperatura, l'OVX o il GPR sono attivi, la prova include anche un gruppo di dati con ciascuno di essi. «Tutti i dati disponibili» li comprende tutti.
- **Oscillazione attesa**: quanto si muoverà il prezzo nei prossimi giorni o settimane, in % e in euro al barile. Prevedere quanto si muove è molto più fattibile che prevedere in che direzione, perché i periodi agitati tendono a durare.
  - Il modello è una regressione sul logaritmo dell'oscillazione. Usa sigma e MAD recenti (su 5 periodi e sulla finestra mobile), l'agitazione (cioè la distanza fra massimo e minimo) e, se attivo, l'OVX.
  - La scheda mostra anche l'OVX di oggi, tradotto in oscillazione attesa al giorno o alla settimana.
  - Nella prova c'è anche un modello con il rischio geopolitico (GPR).
  - La prova a finestre scorrevoli confronta i modelli con tre riferimenti: «come nel periodo appena passato», «OVX così com'è» e «media storica».
  - Gli errori sono misurati come *bias* (errore medio), *MAD* (errore assoluto medio) e *sigma* (deviazione standard dell'errore). Un grafico mostra l'oscillazione vera e quella prevista.

## Impostazioni

Sono nella barra laterale, tranne la scelta della valuta, che sta dentro la scheda «Prossimi 5 giorni».

| Impostazione | Cosa fa | Schede |
|---|---|---|
| Confronta con il prezzo di quanti giorni fa | Giorni per la variazione mostrata in alto | Prezzo, Andamento |
| Periodo mostrato nel grafico | Da 1 mese a tutto lo storico | Prezzo, Meteo |
| Aggiorna i prezzi | Riscarica prezzi, OVX, GPR, temperature e prezzi alla pompa invece di usare quelli in memoria | Tutte |
| Raggruppa i prezzi | Giorno per giorno o settimana per settimana | Andamento, Prova di previsione, Oscillazione attesa |
| Quanti giorni/settimane analizzare | Quanti periodi recenti mostrare nei grafici e nel riepilogo | Andamento |
| Ampiezza della finestra mobile | Quanti periodi si guardano insieme per calcolare sigma, MAD, «chi anticipa chi» e la temperatura media | Andamento, Prova di previsione, Oscillazione attesa |
| Quanto avanti prevedere | L'orizzonte della previsione | Prova di previsione, Oscillazione attesa |
| Rialzo minimo da prevedere | 0% = basta che il prezzo salga; 2% = deve salire di più del 2% | Prova di previsione |
| Usa la temperatura in Europa | Scarica le temperature e le aggiunge alle previsioni | Meteo, Prova di previsione, Oscillazione attesa |
| Usa la volatilità attesa dal mercato (OVX) | Scarica l'OVX e lo aggiunge alle previsioni | Prova di previsione, Oscillazione attesa, Prossimi 5 giorni |
| Usa il rischio geopolitico (GPR) | Scarica il GPR e lo aggiunge alle previsioni | Geopolitica, Prova di previsione, Oscillazione attesa |
| Usa i prezzi alla pompa in Italia | Scarica i prezzi settimanali di benzina e gasolio | Pompa (Italia), Score rifornimento |
| Sensibilità alla turbolenza (α) | Quanto lo score si avvicina a «neutro» quando il mercato è più agitato del normale | Score rifornimento |
| Soglia (θ) | Di quante oscillazioni tipiche il Brent deve allontanarsi dalla media dei 30 giorni per dare +1 o −1 | Score rifornimento |
| Mostra in (dentro la scheda) | Euro o dollari | Prossimi 5 giorni |

## Come leggere i risultati

**Prova di previsione** (il prezzo salirà?)

- *Miglioramento sul riferimento*: positivo vuol dire che il modello sbaglia meno della stima che dà sempre la stessa probabilità.
- *Capacità di distinguere*: 0.5 è come tirare a indovinare, 1 è perfetto. Sotto la tabella c'è il margine dentro cui può variare per puro caso.
- *Anni in cui fa meglio*: un modello utile vince nella maggior parte degli anni, non solo in media.
- Con rialzo minimo 0% è normale che nessun gruppo batta il riferimento: la direzione del prezzo dal solo passato è quasi imprevedibile. Con una soglia sopra lo 0% contano di più sigma e MAD.

**Score rifornimento**

- Lo score continuo S misura di quante «oscillazioni tipiche in 5 giorni» il Brent è lontano dalla media dei 30 giorni. Diventa +1 sopra θ e −1 sotto −θ; con θ = 1 lo scarto deve superare un movimento normale di 5 giorni.
- La *stabilità* vale 1 con mercato calmo. Quando l'oscillazione attesa supera quella normale scende verso 0 e avvicina lo score a «neutro».
- Per regolarlo: se nella tabella storica +1 e −1 si comportano quasi come «Tutti i giorni», alza θ. I segnali diventano più rari ma più netti. Abbassa α se vuoi che lo score resti attivo anche nei periodi agitati.
- Lo score riguarda il Brent: la scelta del distributore dipende anche dai prezzi locali, che l'app non conosce.
- Nella tabella storica, il segnale è coerente se dopo un +1 il Brent è salito più spesso della media di tutti i giorni e dopo un −1 meno spesso. Questa tabella guarda solo il Brent.
- La verifica con i prezzi alla pompa è la prova vera. Lo score funziona se dopo un +1 la pompa è salita e dopo un −1 è scesa. Il *risparmio medio per pieno* è positivo se seguirlo ha fatto spendere meno: con +1 si fa il pieno subito invece che 1 o 2 settimane dopo, con −1 si aspetta. Conta anche quante volte ha fatto risparmiare, non solo la media.

**Pompa (Italia)**

- Nella tabella del ritardo, la riga con la correlazione più alta dice dopo quante settimane la pompa reagisce al Brent. Una correlazione vicina a 0 vuol dire che a quel ritardo non c'è legame.
- La *quota trasferita* dice quanti centesimi alla pompa segue ogni centesimo di Brent al litro. Sommata sui vari ritardi è di solito sotto 1: accise e costi fissi non seguono il petrolio.
- Il grafico del Brent in €/litro mostra il costo della sola materia prima. La distanza dal prezzo alla pompa sono tasse, raffinazione e distribuzione.

**Prossimi 5 giorni**

- La fascia più scura contiene il prezzo in circa 2 casi su 3, quella più chiara in circa 19 su 20, se il prezzo si comporta come nel passato. Nei giorni di notizie improvvise può uscirne più spesso.
- Le date sono i giorni lavorativi successivi: non tengono conto delle festività di borsa.

**Meteo e Geopolitica**

- Sono dati di contesto: mostrano se fa più freddo o più caldo del solito in Europa e se il mondo è più teso del normale. Il grafico del prezzo sotto serve per confrontarli a occhio.
- Che contino davvero per il Brent lo dicono le prove: nella «Prova di previsione» e nell'«Oscillazione attesa» si confrontano i gruppi con e senza temperatura o GPR. Se il gruppo con il dato in più non fa meglio, quel dato non aiuta a prevedere.
- Per il GPR, un valore sopra 100 vuol dire più articoli del solito su guerre e tensioni. Le *minacce* misurano la paura di un conflitto, gli *atti* i conflitti in corso. Gli eventi in tabella sono le etichette degli autori, in inglese.

**Oscillazione attesa** (quanto si muoverà il prezzo?)

- *Oscillazione attesa*: movimento tipico previsto per ogni giorno o settimana. Se è sopra il normale, il mercato è più agitato del solito.
- *Movimento probabile*: in circa 2 casi su 3 la variazione complessiva resta dentro questo intervallo.
- La previsione in alto e le fasce di «Prossimi 5 giorni» usano il modello «+ agitazione e OVX» (o «+ agitazione» se l'OVX non c'è), anche se nella prova un altro modello fa meglio. Temperatura e GPR entrano solo nella prova.
- Nella prova, *bias* vicino a zero vuol dire che il modello non sovrastima né sottostima. *MAD* e *sigma* più bassi vogliono dire errori più piccoli e più costanti. *Miglioramento* e *anni in cui fa meglio* sono misurati contro «come nel periodo appena passato». Il riferimento «OVX così com'è» dice quanto vale da sola l'opinione del mercato: se un modello lo batte, aggiunge qualcosa a ciò che il mercato già sa.

## Metodo in breve

- **Prova a finestre scorrevoli**: entrambe le prove imparano sul primo 40% dello storico. Poi, ogni 21 giorni (o 4 settimane), si riaddestrano su tutto il passato e prevedono il blocco successivo. Dal periodo di studio si escludono i casi il cui esito non era ancora noto all'inizio del blocco, così il modello non vede mai il futuro.
- **Previsione del rialzo**: regressione logistica con penalità ridge sui dati della finestra mobile, cioè variazione di prezzo e agitazione, legame fra i due, area di Lévy, sigma, MAD, temperatura, OVX e GPR.
- **Previsione dell'oscillazione**: regressione ridge sul logaritmo dell'oscillazione dei prossimi periodi, con una correzione per non sottostimarla tornando dalla scala logaritmica. La previsione mostrata in alto nella scheda usa il modello «+ agitazione e OVX», oppure «+ agitazione» se l'OVX non è disponibile.
- **Score rifornimento**: S = ln(Pₜ / P̄₃₀) / (σ·√5) · e^(−α·max(0, σ/σ_norm − 1)). Pₜ è il Brent in euro di oggi e P̄₃₀ la media degli ultimi 30 giorni di calendario. σ è l'oscillazione attesa al giorno (modello «+ agitazione e OVX») e σ_norm l'oscillazione tipica osservata fino a quel giorno. È lo SCORE 4.0 riadattato: il rapporto fra prezzo e media prende il posto del rapporto fra tempo di riferimento e tempo effettivo, σ√5 fa da normalizzazione e l'esponenziale è la stabilità. Per i giorni passati σ viene calcolata con il modello riaddestrato ogni mese, senza guardare il futuro.
- **Fasce dei prossimi 5 giorni**: con oscillazione attesa σ al giorno, dopo k giorni la fascia va da P·e^(−zσ√k) a P·e^(zσ√k), con z = 1 (2 casi su 3) e z = 1.96 (19 su 20). In dollari si usa la stessa ampiezza in percentuale.
- **OVX**: è una volatilità annua in %. Per confrontarlo con l'oscillazione per periodo si divide per √252 (giorni) o √52 (settimane).
- **Ritardo della pompa**: sulle serie settimanali allineate al lunedì del listino, la variazione del Brent in €/litro nella settimana w si confronta con quella della pompa nella settimana w+k, per k da 0 a 4. La quota trasferita è la pendenza della retta; la somma delle quote positive dice quanto passa in tutto alla pompa.
- **Verifica dello score sulla pompa**: per ogni listino si prende l'esito dello score del lunedì (o dell'ultimo giorno di borsa prima). Il risparmio per pieno è 50 × esito × (prezzo dopo h settimane − prezzo di oggi), mediato sulle settimane con +1 o −1.
- **GPR**: nei dati per prevedere entra il logaritmo della media degli ultimi 7 giorni di calendario, oppure della media della settimana. Quando gli ultimi giorni non sono ancora pubblicati si usa l'ultimo valore disponibile, per al massimo 10 giorni di borsa.
- **Temperatura rispetto al normale**: il normale è la media dello stesso giorno dell'anno su tutti gli anni disponibili, smussata su 31 giorni.

## Avvio

Serve Python 3.10 o successivo.

```bash
pip install -r requirements.txt
streamlit run app.py
```

L'app si apre nel browser all'indirizzo http://localhost:8501. Deve poter raggiungere:

- Yahoo Finance (`query1.finance.yahoo.com`, `query2.finance.yahoo.com`, `fc.yahoo.com`) per i prezzi e l'OVX;
- Open-Meteo (`archive-api.open-meteo.com`, `api.open-meteo.com`) per le temperature. Se Open-Meteo non risponde, l'app funziona lo stesso senza la temperatura;
- `www.matteoiacoviello.com` per il rischio geopolitico (GPR). Anche senza GPR l'app funziona;
- `www.fuel-prices.eu` per i prezzi settimanali alla pompa in Italia. Anche senza, l'app funziona.

### Su Streamlit Community Cloud

L'app si pubblica scegliendo questo repository, il branch `main` e il file `app.py`; le librerie vengono installate da `requirements.txt`.

Dopo un aggiornamento che cambia sia `app.py` sia `brent_math.py`, Streamlit può ricaricare solo `app.py` e tenere in memoria la versione vecchia di `brent_math.py`. Ne nasce un errore come `got an unexpected keyword argument`. In quel caso basta riavviare l'app: **Manage app → ⋮ → Reboot app**.

## File

| File | Contenuto |
|---|---|
| `app.py` | L'interfaccia: download di prezzi, OVX, GPR, temperature e prezzi alla pompa, schede, grafici e testi. |
| `brent_math.py` | La matematica: variazioni fra periodi, riepiloghi, area di Lévy, sigma e MAD, temperatura rispetto al normale, regressione logistica, previsione dell'oscillazione, score di rifornimento e prova a finestre scorrevoli. Non dipende da Streamlit. |
| `requirements.txt` | Le librerie Python necessarie. |
| `.streamlit/config.toml` | Configurazione di Streamlit: nasconde il pulsante «Deploy». |

## Dati e avvertenze

- **Fonti**: contratto future sul Brent `BZ=F` (dollari al barile) e cambio `EURUSD=X`, scaricati con [yfinance](https://github.com/ranaroussi/yfinance) per tutto lo storico disponibile e aggiornati al massimo ogni 15 minuti.
- **OVX**: CBOE Crude Oil Volatility Index (`^OVX` su Yahoo Finance), disponibile dal 2007. È la volatilità a 30 giorni attesa dalle opzioni sul petrolio WTI americano, che si muove quasi insieme al Brent. Se non si scarica, l'app continua senza.
- **Prezzi alla pompa**: prezzi medi nazionali settimanali di Euro-super 95 e gasolio in Italia, tasse incluse, in vigore il lunedì. Vengono dal Weekly Oil Bulletin della Commissione Europea, ripubblicato in un unico file Parquet da fuel-prices.eu, che lo controlla cella per cella sul file storico ufficiale. Attribuzione richiesta: «EU Weekly Oil Bulletin, European Commission; compiled by fuel-prices.eu», licenza CC BY 4.0. Il listino esce qualche giorno dopo il lunedì. Per leggere il Parquet serve `pyarrow`, che arriva con Streamlit.
- **GPR**: Geopolitical Risk Index giornaliero (`data_gpr_daily_recent.xls`) di D. Caldara e M. Iacoviello, «Measuring Geopolitical Risk», *American Economic Review*, 2022, da [matteoiacoviello.com](https://www.matteoiacoviello.com/gpr.htm). Conta la quota di articoli di 10 grandi giornali su guerre, terrorismo e tensioni internazionali; parte dal 1985 ed è aggiornato dagli autori con qualche giorno di ritardo. Gli autori chiedono di citare l'articolo e il sito, con la data di scaricamento. Per leggere il file serve la libreria `xlrd`.
- **Meteo**: temperatura media giornaliera da [Open-Meteo.com](https://open-meteo.com), licenza CC BY 4.0, aggiornata al massimo ogni 6 ore. Lo storico arriva con qualche giorno di ritardo: gli ultimi giorni vengono dalle previsioni. L'API gratuita di Open-Meteo è per uso non commerciale e ha limiti di richieste. Se la scheda Meteo mostra un avviso, l'app continua senza temperatura.
- **Salti fra contratti**: `BZ=F` è un contratto con scadenza mensile. Il passaggio da un contratto al successivo produce piccoli salti che non sono veri movimenti del mercato.
- **Previsioni**: i periodi vicini si sovrappongono, quindi i casi davvero indipendenti nella prova di previsione sono meno di quanti sembrano.
- **Uso**: i dati possono arrivare in ritardo. L'app ha scopo di analisi e non è un consiglio di investimento.
