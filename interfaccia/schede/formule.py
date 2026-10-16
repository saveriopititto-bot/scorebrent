"""Scheda «Formule»: tutte le formule del modello matematico (pacchetto `brent`), con spiegazioni e passaggi. Solo
testo e LaTeX: non usa i dati scaricati."""
from __future__ import annotations

import streamlit as st

from .base import Scheda


class SchedaFormule(Scheda):
    titolo = "Formule"

    @staticmethod
    def _sezione(titolo: str) -> None:
        st.markdown(f"### {titolo}")

    def mostra(self) -> None:
        st.subheader("Le formule del modello")
        st.markdown(
            "Questa pagina raccoglie tutta la matematica usata dall'app, nell'ordine in cui viene applicata: dai prezzi "
            "scaricati fino allo score di rifornimento. Per ogni formula c'è il significato in parole semplici e, dove "
            "serve, i passaggi che la giustificano. I nomi fra parentesi `così` sono quelli di classi e metodi del "
            "pacchetto `brent`, per chi vuole ritrovarli nel codice."
        )
        st.markdown(
            "**Indice** · 1. Dati e notazione · 2. Variazioni e riepiloghi · 3. Area di Lévy · 4. Temperatura rispetto "
            "al normale · 5. Prova di previsione del rialzo · 6. Oscillazione attesa · 7. Prossimi 5 giorni · "
            "8. Score rifornimento · 9. Prezzi alla pompa"
        )

        # ------------------------------------------------------------------
        self._sezione("1. Dati e notazione")
        st.markdown(
            "Per ogni giorno di borsa $t$ si hanno chiusura, massimo e minimo del Brent in dollari "
            "($P^{\\text{USD}}_t$, $H_t$, $L_t$) e il cambio $F_t$ (dollari per 1 euro, riportato sull'ultimo valore disponibile). "
            "Il prezzo in euro al barile è"
        )
        st.latex(r"P_t = \frac{P^{\text{USD}}_t}{F_t}.")
        st.markdown(
            "Con «Settimana per settimana» i giorni sono raggruppati in settimane che finiscono il venerdì: chiusura = "
            "ultima della settimana, massimo = il più alto, minimo = il più basso. Indichiamo con $k$ il periodo (giorno "
            "o settimana). Le due serie di base, ispirate al paper «sisma» da cui viene il metodo, sono:"
        )
        st.latex(r"x_k = \ln P_k \qquad\text{(livello: logaritmo del prezzo)}")
        st.latex(r"y_k = \ln\!\left(1 + 100\left(\frac{H_k}{L_k}-1\right)\right) \qquad\text{(agitazione)}")
        st.markdown(
            "Si usa il logaritmo del prezzo perché le sue differenze sono variazioni percentuali (vedi §2) e sono "
            "additive nel tempo. L'agitazione $y_k$ è il logaritmo di $1 +$ l'escursione percentuale fra massimo e "
            "minimo dentro il periodo: misura quanto il prezzo si è mosso *dentro* il giorno, anche se ha chiuso "
            "dove aveva aperto. Il $+1$ evita $\\ln 0$ nei periodi fermi; il logaritmo comprime i pochi giorni "
            "molto agitati."
        )
        st.markdown("**Dati esterni facoltativi**, tutti allineati alle date dei prezzi:")
        st.latex(r"o_k = \ln\frac{\mathrm{OVX}_k/100}{\sqrt{252}}\quad\text{(giorni)}\qquad "
                 r"o_k = \ln\frac{\mathrm{OVX}_k/100}{\sqrt{52}}\quad\text{(settimane)}")
        st.markdown(
            "L'OVX è una volatilità *annua* in percentuale. Se i rendimenti di giorni diversi sono indipendenti, le "
            "varianze si sommano: in un anno di 252 giorni di borsa $\\sigma_{\\text{anno}}^2 = 252\\,\\sigma_{\\text{giorno}}^2$, "
            "quindi $\\sigma_{\\text{giorno}} = \\sigma_{\\text{anno}}/\\sqrt{252}$ (e $\\sqrt{52}$ per le settimane). "
            "L'ultimo valore disponibile vale per al massimo 5 giorni di borsa."
        )
        st.latex(r"g_k = \ln\Big(\max\big(1,\ \overline{\mathrm{GPR}}_k\big)\Big)")
        st.markdown(
            "dove $\\overline{\\mathrm{GPR}}_k$ è la media del Geopolitical Risk Index sugli ultimi 7 giorni di "
            "calendario (o sulla settimana). Il $\\max(1,\\cdot)$ evita il logaritmo di zero. La temperatura $m_k$ è "
            "descritta al §4."
        )

        # ------------------------------------------------------------------
        self._sezione("2. Variazioni e riepiloghi (scheda «Andamento»)")
        st.markdown("**Altezze differenziali** (`Percorso.altezze`): la variazione da un periodo al successivo.")
        st.latex(r"h_k = x_k - x_{k-1} = \ln\frac{P_k}{P_{k-1}}")
        st.markdown(
            "È il *rendimento logaritmico*. Per variazioni piccole coincide con quella percentuale, perché "
            "$\\ln(1+u)\\approx u$: per esempio $\\ln(1{,}02) = 0{,}0198$. Nell'app è moltiplicato per 100 e "
            "mostrato in %."
        )
        st.markdown("**Riepiloghi** (`Riepilogo`) su $K$ periodi:")
        st.latex(r"\text{netto} = \sum_{k=1}^{K} h_k = x_K - x_0")
        st.markdown(
            "*Passaggio:* la somma è «telescopica», i termini intermedi si cancellano: "
            "$(x_1-x_0)+(x_2-x_1)+\\dots+(x_K-x_{K-1}) = x_K - x_0$. Il netto dipende quindi solo da inizio e fine, "
            "non dal percorso. Le misure seguenti invece dipendono dal percorso:"
        )
        st.latex(r"\text{movimento complessivo} = \sum_k |h_k| \qquad "
                 r"\text{salite} = \sum_{h_k>0} h_k \qquad \text{discese} = \sum_{h_k<0} h_k")
        st.latex(r"\text{variazione tipica (RMS)} = \sqrt{\frac{1}{K}\sum_k h_k^2} \qquad "
                 r"\text{salita max} = \max_k h_k \qquad \text{discesa max} = \min_k h_k")
        st.markdown("Vale salite + discese = netto e salite − discese = movimento complessivo.")
        st.markdown("**Linearità dell'andamento** (`Riepilogo.efficienza`):")
        st.latex(r"E = \frac{\left|\sum_k h_k\right|}{\sum_k |h_k|} \in [0,1]")
        st.markdown(
            "Per la disuguaglianza triangolare $|\\sum h_k| \\le \\sum |h_k|$, quindi $E \\le 1$. $E = 1$ se tutte le "
            "variazioni hanno lo stesso segno (percorso dritto); $E \\approx 0$ se salite e discese si compensano."
        )
        st.markdown("**Forza della variazione degli ultimi $n$ giorni**:")
        st.latex(r"z = \frac{100\,\ln(P_t/P_{t-n})}{\sigma_{60}\sqrt{k}}, \qquad "
                 r"\sigma_{60} = \sqrt{\frac{1}{60}\sum_{j=0}^{59} \big(100\,h_{t-j}\big)^2}")
        st.markdown(
            "$k$ è il numero di giorni di borsa fra le due date e $\\sigma_{60}$ l'oscillazione giornaliera (RMS) degli "
            "ultimi 60 giorni di borsa. Se ogni giorno ha deviazione standard $\\sigma$ e i giorni sono indipendenti, la "
            "somma di $k$ variazioni ha deviazione standard $\\sigma\\sqrt{k}$: $z$ dice quindi di quante deviazioni "
            "standard «normali» si è mosso il prezzo. Fra −1 e +1 è normale, oltre ±2 è un movimento forte."
        )
        st.markdown(
            "Nella scheda «Prezzo», la variazione è quella semplice, $d = P_t/P_{t-n} - 1$, in dollari e in euro."
        )

        # ------------------------------------------------------------------
        self._sezione("3. Area di Lévy: chi anticipa chi")
        st.markdown(
            "Si guarda il cammino nel piano formato dai punti $(x_k, y_k)$, prezzo e agitazione. L'**area di Lévy** "
            "(eq. 6 del paper) è l'area con segno racchiusa fra il cammino e la corda che ne unisce gli estremi:"
        )
        st.latex(r"A = \frac12 \int \big[(x - x_0)\,dy - (y - y_0)\,dx\big]")
        st.markdown(
            "Per un cammino fatto di segmenti (`CamminoPiano.area_levy`) l'integrale si calcola esattamente. "
            "*Passaggio:* sul segmento $k$ si scrive $x = x_{k-1} + s\\,\\Delta x_k$, $y = y_{k-1} + s\\,\\Delta y_k$ "
            "con $s \\in [0,1]$, quindi $dx = \\Delta x_k\\,ds$ e $dy = \\Delta y_k\\,ds$:"
        )
        st.latex(r"\frac12\int_0^1 \big[(x_{k-1}-x_0 + s\,\Delta x_k)\,\Delta y_k - (y_{k-1}-y_0 + s\,\Delta y_k)\,"
                 r"\Delta x_k\big]\,ds")
        st.latex(r"= \frac12\big[(x_{k-1}-x_0)\,\Delta y_k - (y_{k-1}-y_0)\,\Delta x_k\big] "
                 r"+ \frac14\big(\Delta x_k\Delta y_k - \Delta y_k \Delta x_k\big)")
        st.markdown("L'ultimo termine vale zero, e sommando su tutti i segmenti:")
        st.latex(r"A = \frac12 \sum_{k=1}^{K} \big[(x_{k-1}-x_0)\,\Delta y_k - (y_{k-1}-y_0)\,\Delta x_k\big]")
        st.markdown(
            "**Proprietà.** (a) Non cambia se si sposta tutto il cammino, perché compaiono solo differenze. "
            "(b) Cambia segno scambiando $x$ e $y$. (c) È zero se $y$ è funzione affine di $x$: se $y = a + b\\,x$ "
            "allora $\\Delta y_k = b\\,\\Delta x_k$ e $y_{k-1}-y_0 = b\\,(x_{k-1}-x_0)$, e i due termini si annullano. "
            "Quindi $A$ misura solo lo *sfasamento* fra i due canali, non il loro muoversi insieme."
        )
        st.markdown(
            "**Segno.** $A > 0$ se il cammino gira in senso antiorario, cioè se **il prezzo si muove prima e "
            "l'agitazione dopo**; $A < 0$ se è l'agitazione ad anticipare il prezzo. Esempio: se il prezzo sale "
            "(passo a destra) e solo dopo sale l'agitazione (passo in alto), il cammino va a destra e poi in alto, "
            "e la corda chiude un giro antiorario."
        )
        st.markdown(
            "**Normalizzazione** (`CamminoPiano.area_levy_mobile`). Su una finestra di $w$ periodi (cioè $w+1$ punti, $w$ "
            "incrementi) l'area si divide per le scale dei due canali, come nel coefficiente di correlazione di Pearson:"
        )
        st.latex(r"\tilde A_t = \frac{A\big(x_{t-w..t},\ y_{t-w..t}\big)}{w\; s_{\Delta x}\; s_{\Delta y}}")
        st.markdown(
            "dove $s_{\\Delta x}$ e $s_{\\Delta y}$ sono le deviazioni standard campionarie (con $w-1$ al denominatore) "
            "degli incrementi nella finestra. Così $\\tilde A$ non dipende dall'unità di misura e periodi calmi e "
            "agitati sono confrontabili. È l'«indice di anticipo» della scheda «Andamento»."
        )
        st.markdown(
            "**Legame con la firma del cammino.** I termini di secondo ordine della firma, "
            "$S^{ij} = \\int\\!\\!\\int_{s<u} dX^i_s\\,dX^j_u$, si dividono in una parte simmetrica, "
            "$\\tfrac12(S^{xy}+S^{yx}) = \\tfrac12\\,\\Delta x\\,\\Delta y$, che dipende solo dagli incrementi totali, "
            "e una antisimmetrica, $\\tfrac12(S^{xy}-S^{yx}) = A$. Per questo nella prova di previsione compaiono "
            "insieme gli incrementi $(\\Delta x, \\Delta y)$ (primo ordine), la correlazione (legame simmetrico) e "
            "l'area di Lévy (legame antisimmetrico, l'ordine temporale)."
        )

        # ------------------------------------------------------------------
        self._sezione("4. Temperatura rispetto al normale (`AnomaliaStagionale`)")
        st.markdown(
            "La temperatura del giorno $T_d$ è la media della temperatura media giornaliera di Berlino, Parigi, "
            "Londra, Milano e Madrid (serve il dato di almeno 3 città su 5). Per ogni giorno si calcola il giorno "
            "dell'anno $j(d) \\in \\{1,\\dots,365\\}$; negli anni bisestili dal 1° marzo in poi si toglie 1, così il "
            "29 febbraio conta come il 28 e le date coincidono fra anni diversi."
        )
        st.latex(r"C(j) = \operatorname{media}\{T_d : j(d) = j\} \qquad\text{(media dello stesso giorno su tutti gli anni)}")
        st.latex(r"\bar C(j) = \frac{1}{31}\sum_{i=-15}^{15} C\big((j+i-1 \bmod 365) + 1\big)")
        st.markdown(
            "La media mobile su 31 giorni è *circolare*: per il 1° gennaio usa anche gli ultimi giorni di dicembre. "
            "Smussa il rumore dovuto ai pochi anni disponibili per ogni singolo giorno. L'anomalia è"
        )
        st.latex(r"a_d = T_d - \bar C\big(j(d)\big)")
        st.markdown(
            "positiva se fa più caldo del normale. Come dato di previsione si usa la media dell'anomalia sugli "
            "ultimi $w$ periodi, $m_t = \\frac{1}{w}\\sum_{i=0}^{w-1} a_{t-i}$, solo se almeno metà dei valori c'è."
        )

        # ------------------------------------------------------------------
        self._sezione("5. Prova di previsione del rialzo")
        st.markdown(
            "**Domanda.** Con orizzonte $H$ periodi e soglia $\\theta$ (il «rialzo minimo», come frazione), il "
            "bersaglio è"
        )
        st.latex(r"Y_t = \mathbf 1\big[\,x_{t+H} - x_t > \theta\,\big] = \mathbf 1\!\left[\ln\frac{P_{t+H}}{P_t} > \theta\right]")
        st.markdown("cioè 1 se il prezzo sale oltre la soglia nei prossimi $H$ periodi, 0 altrimenti.")
        st.markdown(
            "**Predittori** (`PrevisioneRialzo.features`), calcolati sulla finestra degli ultimi $w$ periodi "
            "$[t-w,\\,t]$, con incrementi $\\Delta x_i, \\Delta y_i$:"
        )
        st.latex(r"\begin{aligned}"
                 r"\texttt{dx} &= x_t - x_{t-w}, \qquad \texttt{dy} = y_t - y_{t-w}\\"
                 r"\texttt{cos} &= \operatorname{corr}(\Delta x, \Delta y)"
                 r"= \frac{\sum_i (\Delta x_i-\overline{\Delta x})(\Delta y_i-\overline{\Delta y})}"
                 r"{\sqrt{\sum_i (\Delta x_i-\overline{\Delta x})^2\ \sum_i (\Delta y_i-\overline{\Delta y})^2}}\\"
                 r"\texttt{levy} &= \tilde A_t \quad(\S 3)\\"
                 r"\texttt{sigma} &= \ln s_{\Delta x}\\"
                 r"\texttt{mad} &= \ln \max\!\Big(\operatorname{mediana}_i\big|\Delta x_i - \operatorname{mediana}(\Delta x)\big|,"
                 r"\ 10^{-4} s_{\Delta x}\Big)\\"
                 r"\texttt{meteo} &= m_t, \qquad \texttt{ovx} = o_t, \qquad \texttt{gpr} = g_t"
                 r"\end{aligned}")
        st.markdown(
            "*Sigma* è la deviazione standard degli incrementi del prezzo nella finestra; la *MAD* (deviazione "
            "assoluta mediana) misura la stessa cosa con le mediane, quindi un singolo salto enorme non la sposta. "
            "Entrambe sono in logaritmo perché la volatilità è asimmetrica: molti periodi calmi e pochi molto agitati. "
            "Il nome «coseno» viene dal fatto che la correlazione è il coseno dell'angolo fra i due vettori di "
            "incrementi centrati."
        )
        st.markdown(
            "**Modello: regressione logistica con penalità ridge** (`RegressioneLogistica`). Ogni predittore è prima "
            "standardizzato con media e deviazione standard del solo periodo di addestramento, "
            "$z_j = (X_j - \\mu_j)/\\sigma_j$. La probabilità di rialzo è"
        )
        st.latex(r"p_t = \operatorname{sig}\!\Big(\beta_0 + \sum_j \beta_j z_{tj}\Big), \qquad "
                 r"\operatorname{sig}(u) = \frac{1}{1+e^{-u}}")
        st.markdown("I coefficienti massimizzano la verosimiglianza penalizzata (con $\\lambda = 1$, intercetta non penalizzata):")
        st.latex(r"\ell(\beta) = \sum_t \big[Y_t \ln p_t + (1-Y_t)\ln(1-p_t)\big] - \frac{\lambda}{2}\sum_{j\ge 1}\beta_j^2")
        st.markdown(
            "*Passaggi.* Poiché $\\operatorname{sig}'(u) = \\operatorname{sig}(u)(1-\\operatorname{sig}(u))$, "
            "gradiente e matrice hessiana (cambiata di segno) sono, con $Z$ la matrice dei predittori con una "
            "colonna di 1 e $R = \\lambda\\,\\mathrm{diag}(0,1,\\dots,1)$:"
        )
        st.latex(r"\nabla \ell = Z^\top (Y - p) - R\beta, \qquad "
                 r"\mathcal H = Z^\top W Z + R, \quad W = \mathrm{diag}\big(p_t(1-p_t)\big)")
        st.markdown("Si parte da $\\beta = 0$ e si applica il metodo di Newton (IRLS):")
        st.latex(r"\beta \leftarrow \beta + \mathcal H^{-1}\,\nabla\ell")
        st.markdown(
            "fino a quando nessun coefficiente cambia più di $10^{-8}$ (al massimo 100 iterazioni). $\\ell$ è concava, "
            "quindi il massimo è unico; la penalità ridge tiene i coefficienti piccoli e stabili anche con predittori "
            "correlati fra loro."
        )
        st.markdown(
            "**Prova a finestre scorrevoli** (`FinestreScorrevoli`, `PrevisioneRialzo.valida`). Con $n$ casi ordinati nel tempo, i primi $\\lfloor 0{,}4\\,n "
            "\\rfloor$ servono solo per imparare. Poi a blocchi di $p$ casi ($p = 21$ giorni o 4 settimane, circa un "
            "mese) si riaddestra il modello e si prevede il blocco $[a, a+p)$. L'insieme di addestramento è"
        )
        st.latex(r"\mathcal T_a = \{\, i : t_i + H \le t_a \,\}")
        st.markdown(
            "cioè solo i casi il cui esito era già noto all'inizio del blocco: il bersaglio guarda $H$ periodi avanti, "
            "e senza questa esclusione il modello userebbe prezzi futuri. I blocchi con meno di 30 casi di "
            "addestramento si saltano."
        )
        st.markdown("**Riferimento**: la frequenza dei rialzi nell'addestramento, sempre uguale dentro il blocco:")
        st.latex(r"p^{0}_t = \frac{1}{|\mathcal T_a|}\sum_{i\in\mathcal T_a} Y_i")
        st.markdown("**Errore medio** (punteggio di Brier) e **miglioramento** (skill), su tutti gli $N$ casi di verifica:")
        st.latex(r"B = \frac1N\sum_t (p_t - Y_t)^2, \qquad \text{Skill} = 1 - \frac{B_{\text{modello}}}{B_{\text{riferimento}}}")
        st.markdown(
            "Skill $> 0$ vuol dire che il modello sbaglia meno del riferimento. Il Brier è la versione per "
            "probabilità dell'errore quadratico: prevedere 0,9 quando poi non succede costa $0{,}81$."
        )
        st.markdown("**Capacità di distinguere** (AUC), con $n_1$ rialzi, $n_0$ non-rialzi e $R_1$ la somma dei ranghi delle "
                    "probabilità previste per i casi con rialzo:")
        st.latex(r"\text{AUC} = \frac{R_1 - n_1(n_1+1)/2}{n_1\,n_0}")
        st.markdown(
            "*Passaggio:* il numeratore è la statistica $U$ di Mann-Whitney, che conta le coppie (rialzo, non-rialzo) "
            "in cui il rialzo ha ricevuto la probabilità più alta. Diviso per il numero di coppie $n_1 n_0$ è la "
            "probabilità che il modello ordini correttamente una coppia presa a caso: 0,5 = a caso, 1 = sempre giusto."
        )
        st.markdown(
            "**Margine dovuto al caso.** Sotto l'ipotesi che il modello non sappia nulla, l'AUC ha deviazione standard "
            "$\\sqrt{(n_1+n_0+1)/(12\\,n_1 n_0)}$. Poiché i bersagli di periodi vicini si sovrappongono (il rialzo dei "
            "prossimi $H$ giorni è quasi lo stesso per oggi e per domani), si usano i casi *effettivi* "
            "$n^e = n/H$:"
        )
        st.latex(r"\mathrm{SE}_{\text{AUC}} = \sqrt{\frac{n^e_1 + n^e_0 + 1}{12\, n^e_1\, n^e_0}}")
        st.markdown(
            "Il risultato è giudicato più che fortuna se $\\text{AUC} - 0{,}5 > 2\\,\\mathrm{SE}$ **e** il modello ha "
            "un Brier più basso del riferimento in più di metà degli anni del periodo di verifica."
        )

        # ------------------------------------------------------------------
        self._sezione("6. Oscillazione attesa")
        st.markdown(
            "Qui non si prevede la direzione ma *quanto* si muoverà il prezzo. Con $r_t = x_t - x_{t-1}$, il "
            "**bersaglio** (`PrevisioneOscillazione.features`) è l'oscillazione realizzata nei prossimi $H$ periodi:"
        )
        st.latex(r"\texttt{bersaglio}_t = \ln \sqrt{\frac1H\sum_{j=1}^{H} r_{t+j}^2}")
        st.markdown(
            "Si usa la media dei quadrati senza togliere la media perché su pochi giorni la media dei rendimenti è "
            "praticamente zero e stimarla aggiunge solo rumore. **Predittori**, in stile HAR (una scala breve e una "
            "lunga), con $b = 5$:"
        )
        st.latex(r"\begin{aligned}"
                 r"\texttt{s\_breve} &= \ln \sqrt{\tfrac1b \textstyle\sum_{i=0}^{b-1} r_{t-i}^2}, \qquad"
                 r"\texttt{s\_lungo} = \ln \sqrt{\tfrac1w \textstyle\sum_{i=0}^{w-1} r_{t-i}^2}\\"
                 r"\texttt{mad} &= \ln \operatorname{mediana}_{i<w}\big|r_{t-i} - \operatorname{mediana}(r)\big|, \qquad"
                 r"\texttt{agit} = \tfrac1b \textstyle\sum_{i=0}^{b-1} y_{t-i}\\"
                 r"\texttt{meteo} &= m_t, \qquad \texttt{ovx} = o_t, \qquad \texttt{gpr} = g_t"
                 r"\end{aligned}")
        st.markdown(
            "Ogni radice o MAD è portata almeno a $10^{-6}$ prima del logaritmo, per evitare $\\ln 0$. L'idea: i "
            "periodi agitati tendono a durare (*volatility clustering*), quindi l'oscillazione recente su più scale "
            "predice quella futura; l'escursione fra massimo e minimo ne è una misura meno rumorosa; l'OVX è "
            "l'opinione del mercato delle opzioni."
        )
        st.markdown(
            "**Modello: regressione ridge** (`RegressioneRidge`). Con $Z = [\\mathbf 1,\\ \\text{predittori standardizzati}]$ "
            "e $R = \\lambda\\,\\mathrm{diag}(0,1,\\dots,1)$, $\\lambda = 1$, si minimizza "
            "$\\|v - Z\\beta\\|^2 + \\beta^\\top R\\beta$, dove $v$ è il bersaglio. Imponendo gradiente nullo, "
            "$-2Z^\\top(v - Z\\beta) + 2R\\beta = 0$, si ottiene"
        )
        st.latex(r"\hat\beta = (Z^\top Z + R)^{-1} Z^\top v, \qquad "
                 r"\hat v = Z\hat\beta, \qquad s^2 = \operatorname{var}(v - \hat v)")
        st.markdown(
            "**Ritorno alla scala normale** (`RegressioneRidge.prevedi_esponenziale`). Il modello prevede il *logaritmo* "
            "dell'oscillazione. Se $\\ln\\sigma \\sim \\mathcal N(\\mu, s^2)$, allora"
        )
        st.latex(r"\mathbb E[\sigma] = \mathbb E\big[e^{\ln\sigma}\big] = e^{\mu + s^2/2}")
        st.markdown(
            "(media della distribuzione lognormale). Quindi $e^{\\hat v}$ da solo darebbe la *mediana* e "
            "sottostimerebbe sistematicamente; la previsione usata è"
        )
        st.latex(r"\hat\sigma = \exp\!\big(\hat v + s^2/2\big)")
        st.markdown(
            "**Movimento probabile in $H$ periodi.** Con incrementi indipendenti di deviazione standard $\\hat\\sigma$, "
            "la somma di $H$ incrementi ha varianza $H\\hat\\sigma^2$:"
        )
        st.latex(r"\text{escursione} = \hat\sigma\,\sqrt H, \qquad \text{in euro} \approx P_t\cdot\hat\sigma\sqrt H")
        st.markdown(
            "Il «normale» mostrato accanto è $e^{\\operatorname{mediana}(\\texttt{bersaglio})}$ su tutto lo storico."
        )
        st.markdown(
            "**Prova** (`PrevisioneOscillazione.valida`): stesse finestre scorrevoli del §5 (con il modello riaddestrato ogni "
            "blocco anche per le previsioni passate, `PrevisioneOscillazione.scorrevole`). Riferimenti: «come appena passato» "
            "$e^{\\texttt{s\\_lungo}_t}$; «OVX così com'è» $e^{o_t}$; «media storica» $e^{\\bar v + \\operatorname{var}(v)/2}$ "
            "sull'addestramento. Con errore in punti percentuali $e_t = 100(\\hat\\sigma_t - \\sigma_t)$, dove "
            "$\\sigma_t = e^{\\texttt{bersaglio}_t}$:"
        )
        st.latex(r"\text{Bias} = \bar e, \qquad \text{MAD} = \frac1N\sum_t |e_t|, \qquad "
                 r"\text{Sigma} = \sqrt{\frac1N\sum_t (e_t - \bar e)^2}, \qquad "
                 r"\text{Miglioramento} = 1 - \frac{\frac1N\sum_t e_t^2}{\frac1N\sum_t e_{t,\text{rif}}^2}")
        st.markdown("con «come appena passato» come riferimento. Qui MAD è l'errore assoluto *medio*, da non confondere con la "
                    "deviazione assoluta mediana usata come predittore.")

        # ------------------------------------------------------------------
        self._sezione("7. Prossimi 5 giorni")
        st.markdown(
            "Sempre su dati giornalieri, con finestra $w = 20$ e $H = 5$. Si assume che il logaritmo del prezzo sia "
            "una passeggiata casuale senza direzione prevedibile, con oscillazione giornaliera $\\hat\\sigma$ (modello "
            "«+ agitazione e OVX», o «+ agitazione» senza OVX):"
        )
        st.latex(r"\ln P_{t+k} - \ln P_t \sim \mathcal N\big(0,\ k\,\hat\sigma^2\big), \qquad k = 1,\dots,5")
        st.markdown("Allora la previsione centrale resta $P_t$ e le fasce sono")
        st.latex(r"\Big[\,P_t\, e^{-z\hat\sigma\sqrt k},\ \ P_t\, e^{+z\hat\sigma\sqrt k}\,\Big], \qquad "
                 r"z = 1\ \ (\approx 68\%,\ \text{2 casi su 3}), \quad z = 1{,}96\ \ (95\%,\ \text{19 casi su 20})")
        st.markdown(
            "*Passaggio:* per una normale $\\Pr(|Z| \\le 1) \\approx 0{,}683$ e $\\Pr(|Z| \\le 1{,}96) \\approx 0{,}95$; "
            "applicando l'esponenziale ai due estremi dell'intervallo per $\\ln P_{t+k}$ si ottiene l'intervallo per "
            "$P_{t+k}$. La fascia si allarga come $\\sqrt k$ ed è asimmetrica in euro (più spazio verso l'alto), "
            "perché simmetrica in logaritmo."
        )

        # ------------------------------------------------------------------
        self._sezione("8. Score rifornimento (`ScoreRifornimento`)")
        st.markdown("È un adattamento dello SCORE 4.0, con la logica «la pompa segue il Brent con ritardo».")
        st.latex(r"S_t = \underbrace{\frac{\ln\left(P_t/\bar P_{30,t}\right)}{\sigma_t\sqrt{5}}}_{\text{scarto normalizzato}}"
                 r"\cdot \underbrace{e^{-\alpha\,\max\left(0,\ \sigma_t/\sigma_{\text{norm},t}-1\right)}}_{\text{stabilità}}")
        st.markdown("**Gli ingredienti, uno per uno.**")
        st.latex(r"\bar P_{30,t} = \operatorname{media}\{P_s : t - 30\ \text{giorni} < s \le t\}")
        st.markdown(
            "è la media dei prezzi in euro negli ultimi 30 giorni di *calendario* (servono almeno 15 giorni di borsa). "
            "Lo **scarto** $\\delta_t = \\ln(P_t/\\bar P_{30,t})$ è di quanto il Brent di oggi è sopra (+) o sotto (−) la "
            "media, in termini relativi."
        )
        st.markdown(
            "$\\sigma_t$ è l'oscillazione attesa al giorno del §6, calcolata per ogni giorno passato con il modello "
            "riaddestrato ogni 21 giorni sui soli dati disponibili allora (nessun uso del futuro); per oggi è quella "
            "del modello addestrato su tutto lo storico. Poiché in 5 giorni l'oscillazione è $\\sigma_t\\sqrt5$ (§6), "
            "il primo fattore è un **punteggio z**: dice di quanti «movimenti normali in 5 giorni» il prezzo è lontano "
            "dalla media. Uno scarto del 3% pesa molto in un mercato calmo e poco in uno agitato."
        )
        st.latex(r"\sigma_{\text{norm},t} = \operatorname{mediana}\big\{ e^{\texttt{s\_lungo}_s} : s \le t \big\}")
        st.markdown(
            "è l'oscillazione tipica osservata fino a quel giorno (oscillazione degli ultimi 20 giorni, mediana su "
            "tutto il passato). La **stabilità**"
        )
        st.latex(r"\text{stab}_t = \exp\!\big(-\alpha\,\max(0,\ \sigma_t/\sigma_{\text{norm},t} - 1)\big) \in (0, 1]")
        st.markdown(
            "vale 1 quando l'oscillazione attesa non supera quella normale, e scende verso 0 quando la supera: se "
            "$\\sigma_t$ è il doppio del normale e $\\alpha = 1$, vale $e^{-1} \\approx 0{,}37$. Così, nei mercati "
            "turbolenti, lo score viene avvicinato a zero, perché lo scarto dalla media potrebbe essere solo rumore."
        )
        st.markdown("**Esito**, con soglia $\\theta$ (predefinita 1):")
        st.latex(r"\text{esito}_t = \begin{cases} +1 \ \text{(rifornisci)} & S_t \ge \theta\\ "
                 r"\ \ 0 \ \text{(neutro)} & -\theta < S_t < \theta\\ -1\ \text{(aspetta)} & S_t \le -\theta \end{cases}")
        st.markdown(
            "Con $\\theta = 1$ e mercato calmo, +1 vuol dire che il Brent è sopra la media di più di un movimento "
            "normale di 5 giorni: la pompa, che lo segue con ritardo, tenderà a salire, quindi conviene il pieno subito."
        )
        st.markdown("**Verifica sul Brent** (`ScoreRifornimento.verifica`): per ogni esito si guarda")
        st.latex(r"\ln\frac{P_{t+5}}{P_t}")
        st.markdown(
            "(5 giorni di borsa dopo): la media (in %) e la quota di casi in cui è positivo, confrontate con quelle "
            "di tutti i giorni."
        )

        # ------------------------------------------------------------------
        self._sezione("9. Prezzi alla pompa")
        st.markdown("Il Brent in euro al litro, allineato al lunedì di ogni listino settimanale (1 barile = 158,987 litri):")
        st.latex(r"B_w = \frac{P_w}{158{,}987}")
        st.markdown(
            "**Ritardo** (`AnalisiPompa.ritardo`). Con $\\Delta B_w = B_w - B_{w-1}$ e $\\Delta Q_w = Q_w - Q_{w-1}$ le "
            "variazioni settimanali di Brent e pompa (benzina o gasolio), per ogni ritardo $k = 0,\\dots,4$ settimane:"
        )
        st.latex(r"\rho_k = \operatorname{corr}\big(\Delta B_w,\ \Delta Q_{w+k}\big), \qquad "
                 r"\beta_k = \frac{\operatorname{cov}(\Delta B_w,\ \Delta Q_{w+k})}{\operatorname{var}(\Delta B_w)}")
        st.markdown(
            "$\\beta_k$ è la pendenza della retta dei minimi quadrati di $\\Delta Q_{w+k}$ su $\\Delta B_w$: quanti "
            "centesimi alla pompa seguono, dopo $k$ settimane, ogni centesimo di Brent. *Passaggio:* minimizzando "
            "$\\sum (\\Delta Q - a - \\beta\\,\\Delta B)^2$ e annullando le derivate rispetto ad $a$ e $\\beta$ si ottiene "
            "proprio covarianza su varianza. La settimana di reazione principale è quella con $\\rho_k$ più alto e la "
            "quota trasferita in tutto è $\\sum_k \\max(0, \\beta_k)$. Servono almeno 30 settimane."
        )
        st.markdown(
            "**Verifica dello score** (`AnalisiPompa.verifica_score`). L'esito della settimana $c_w$ è quello del lunedì del "
            "listino (o dell'ultimo giorno di borsa prima). Per ogni esito si mostra la variazione media della pompa "
            "dopo $h = 1, 2$ settimane, $100\\,(Q_{w+h} - Q_w)$ in centesimi al litro. Il **risparmio per pieno** da "
            "$L = 50$ litri, nelle settimane con $c_w \\ne 0$, è"
        )
        st.latex(r"G_w = L\cdot c_w\cdot\big(Q_{w+h} - Q_w\big)")
        st.markdown(
            "*Perché:* con $c_w = +1$ si fa il pieno subito invece che dopo $h$ settimane, e si risparmia "
            "$Q_{w+h} - Q_w$ al litro (positivo se poi il prezzo è salito); con $c_w = -1$ si aspetta, e si risparmia "
            "$Q_w - Q_{w+h} = -(Q_{w+h} - Q_w)$. In tabella ci sono la media di $G_w$ e la quota di settimane con "
            "$G_w > 0$."
        )
        # ------------------------------------------------------------------
        self._sezione("10. Capacità dello score (`brent.capacita`)")
        st.markdown(
            "Lo score $S_t$, portato dentro $[\\mathrm{LSL}, \\mathrm{USL}] = [-\\theta, +\\theta]$, si divide in "
            "finestre di 5 giorni di borsa con passo 1. Su ognuna (`FinestreCapacita`), con $\\mu$ la media e "
            "$\\sigma$ la deviazione standard campionaria (mai sotto 0,01):"
        )
        st.latex(r"C_p = \frac{\mathrm{USL} - \mathrm{LSL}}{6\sigma}, \qquad "
                 r"C_{pk} = \frac{\min(\mathrm{USL} - \mu,\ \mu - \mathrm{LSL})}{3\sigma}, \qquad 0 \le C_{pk} \le C_p \le 10")
        st.markdown("**Area di Lévy** del cammino $(S, \\dot S)$, con la differenza centrale "
                    "$\\dot S_t = (S_{t+1} - S_{t-1})/2$ sui 3 giorni interni, con la formula della sezione 3. Anche "
                    "per una passeggiata casuale con incrementi di varianza $s^2$ la media non è 0:")
        st.latex(r"\mathbb E[A] = -\frac{s^2}{2}")
        st.markdown(
            "*Passaggio:* con incrementi $e_1,\\dots,e_4$ resta un solo termine, "
            "$A = \\tfrac14\\big[e_2(e_3+e_4-e_1-e_2) - (e_3-e_1)(e_2+e_3)\\big]$, e con incrementi indipendenti "
            "$\\mathbb E[A] = \\tfrac14(-s^2 - s^2)$. Per questo l'area si confronta con le passeggiate casuali "
            "fatte con gli stessi incrementi rimescolati (`AreaLevyRiepilogo`)."
        )
        st.markdown(
            "**Rete neurale** (`ReteNeurale`): ingresso $u$ = $(\\mu, \\sigma, C_p, C_{pk}, A)$ delle finestre $k$ e "
            "$k-1$, standardizzato; uscita = $(C_p, C_{pk})$ della finestra $k+1$, standardizzati."
        )
        st.latex(r"h = \tanh(u W_1 + b_1), \qquad \hat y = h W_2 + b_2, \qquad "
                 r"L = \frac1N\sum_i \lVert \hat y_i - y_i\rVert^2 + \frac{\lambda}{2}\big(\lVert W_1\rVert^2 + \lVert W_2\rVert^2\big)")
        st.markdown("*Back propagation:* con $\\delta = 2(\\hat Y - Y)/N$,")
        st.latex(r"\frac{\partial L}{\partial W_2} = h^\top\delta + \lambda W_2, \qquad "
                 r"\frac{\partial L}{\partial W_1} = U^\top\big[(\delta W_2^\top)\odot(1 - h^2)\big] + \lambda W_1")
        st.markdown(
            "perché $\\tanh' = 1 - \\tanh^2$. 16 neuroni, 3000 passi di discesa del gradiente con passo 0,01 e "
            "$\\lambda = 10^{-4}$. La prova è a finestre scorrevoli (come nella sezione 5, con $H = 1$ finestra) e "
            "il riferimento è $\\hat C_{p,k+1} = C_{p,k}$, $\\hat C_{pk,k+1} = C_{pk,k}$."
        )
        st.caption("Le formule descrivono il codice del pacchetto brent. L'app ha scopo di analisi e non è "
                   "un consiglio di investimento.")
