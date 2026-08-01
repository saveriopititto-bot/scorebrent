import streamlit as st
import pandas as pd
import requests
import io
import urllib3

# Disabilita gli avvisi visivi per le chiamate HTTPS non verificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# 1. Configurazione Endpoint ISMEA (Pagine Web HTML)
# ---------------------------------------------------------------------------
ISMEA_SOURCES = {
    "Cereali (Pagina 439)": {
        "url": "https://www.ismeamercati.it/flex/cm/pages/ServeBLOB.php/L/IT/IDPagina/439",
        "format": "html"
    }
    # Puoi aggiungere altre pagine ISMEA copiando l'URL e cambiando l'IDPagina
}

# ---------------------------------------------------------------------------
# 2. Motore di Scraping HTML
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def fetch_html_data(product_key: str) -> pd.DataFrame:
    """
    Esegue lo scraping della pagina web ISMEA ignorando la verifica del certificato SSL.
    """
    config = ISMEA_SOURCES.get(product_key)
    if not config:
        raise ValueError(f"Nessuna configurazione per {product_key}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        # Aggiunto verify=False per superare l'errore SSL: CERTIFICATE_VERIFY_FAILED
        response = requests.get(config["url"], headers=headers, timeout=15, verify=False)
        response.raise_for_status()
        
        # pandas.read_html estrae TUTTE le tabelle dalla pagina HTML in una lista di DataFrame
        tables = pd.read_html(
            io.StringIO(response.text), 
            decimal=',', 
            thousands='.',
            flavor='bs4'
        )
        
        if not tables:
            return pd.DataFrame()
            
        # Euristica: le tabelle coi dati veri hanno almeno 3 righe e 2 colonne
        valid_tables = [t for t in tables if len(t) > 2 and len(t.columns) >= 2]
        
        if not valid_tables:
            return pd.DataFrame()
            
        # Prendiamo la tabella più grande
        best_table = max(valid_tables, key=lambda t: t.size)
        return best_table

    except Exception as e:
        st.error(f"Errore durante lo scraping HTML: {e}")
        return pd.DataFrame()

def process_scraped_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pulisce la tabella HTML grezza scaricata da ISMEA.
    """
    if df.empty:
        return df
        
    # Appiattiamo le colonne se sono MultiIndex (comune nelle tabelle web complesse)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ['_'.join(map(str, col)).strip() for col in df.columns.values]
    
    # Rimuoviamo eventuali righe completamente vuote
    df = df.dropna(how='all').copy()
    
    # Per evitare problemi di rendering iniziale sui tipi misti, forziamo le stringhe
    df = df.astype(str)
    
    return df

# ---------------------------------------------------------------------------
# 3. Interfaccia Utente
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="ISMEA Web Scraper", layout="wide")
    st.title("Estrattore Prezzi ISMEA (Scraping Diretto)")
    
    # Il menu di selezione della pagina/mercato è nascosto: si usa sempre l'unica fonte configurata.
    selected_market = next(iter(ISMEA_SOURCES.keys()))

    with st.sidebar:
        st.header("Scegli il bene")
        # Il selettore del bene verrà popolato dinamicamente una volta scaricati i dati
        cereal_placeholder = st.empty()

    # L'estrazione avviene automaticamente. @st.cache_data impedisce
    # al server di fare continue richieste HTTP a ogni interazione.
    with st.spinner(f"Scraping della pagina {selected_market} in corso..."):
        raw_data = fetch_html_data(selected_market)
        
        if not raw_data.empty:
            cleaned_data = process_scraped_table(raw_data)
            
            # La prima colonna solitamente contiene il nome del prodotto agricolo
            product_col = cleaned_data.columns[0]
            
            # Ricaviamo i beni unici (escludendo eventuali stringhe 'nan' o 'None')
            lista_beni = [x for x in cleaned_data[product_col].unique() if x not in ('nan', 'None')]

            opzioni_filtro = ["Tutti i prodotti"] + lista_beni

            # Popoliamo il menu a tendina nello spazio vuoto della sidebar (cereal_placeholder)
            selected_bene = cereal_placeholder.selectbox(
                "Seleziona un bene specifico:",
                options=opzioni_filtro
            )

            # Applichiamo il filtro sul DataFrame in base alla scelta
            if selected_bene != "Tutti i prodotti":
                filtered_data = cleaned_data[cleaned_data[product_col] == selected_bene]
            else:
                filtered_data = cleaned_data

            # Mostriamo i risultati
            st.success(f"Dati estratti con successo! Righe visualizzate: {len(filtered_data)}")

            st.markdown(f"### Tabella Prezzi: {selected_bene}")
            st.dataframe(filtered_data, use_container_width=True)
            
        else:
            st.error("Impossibile estrarre tabelle valide da questo URL. Controlla i log o l'URL.")

if __name__ == "__main__":
    main()
