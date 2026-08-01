import streamlit as st
import pandas as pd
import numpy as np
import requests
import io

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
    Esegue lo scraping della pagina web ISMEA ed estrae la tabella dati.
    """
    config = ISMEA_SOURCES.get(product_key)
    if not config:
        raise ValueError(f"Nessuna configurazione per {product_key}")

    headers = {
        # Fingerprint di un browser reale per evitare di essere bloccati
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        response = requests.get(config["url"], headers=headers, timeout=15)
        response.raise_for_status()
        
        # pandas.read_html estrae TUTTE le tabelle dalla pagina HTML in una lista di DataFrame.
        # Parametri cruciali per l'Italia: decimal=',' e thousands='.'
        tables = pd.read_html(
            io.StringIO(response.text), 
            decimal=',', 
            thousands='.',
            flavor='bs4' # Usa BeautifulSoup per un parsing più robusto
        )
        
        if not tables:
            st.error("Nessuna tabella HTML trovata nella pagina.")
            return pd.DataFrame()
            
        # Euristica: di solito la tabella con i veri dati di mercato è quella con più righe/colonne
        # Filtriamo le tabelle di layout minuscole
        valid_tables = [t for t in tables if len(t) > 2 and len(t.columns) >= 2]
        
        if not valid_tables:
            return pd.DataFrame()
            
        # Prendiamo la tabella più grande (quella con più celle)
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
        
    # Spesso le tabelle web hanno intestazioni multi-livello o colonne sporche.
    # Appiattiamo le colonne se sono MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ['_'.join(map(str, col)).strip() for col in df.columns.values]
    
    # Rimuoviamo eventuali righe completamente vuote
    df = df.dropna(how='all').copy()
    
    # Poiché non conosciamo a priori il nome esatto delle colonne della pagina 439,
    # convertiamo in stringhe per facilitare la diagnostica.
    df = df.astype(str)
    
    return df

# ---------------------------------------------------------------------------
# 3. Interfaccia Utente
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="ISMEA Web Scraper", layout="wide")
    st.title("Estrattore Prezzi ISMEA (Scraping Diretto)")
    
    with st.sidebar:
        st.header("Selettore Pagina")
        selected_product = st.selectbox(
            "Mercato:",
            options=list(ISMEA_SOURCES.keys())
        )
        run_fetch = st.button("Estrai Tabella da Sito Web", type="primary")

    if run_fetch:
        with st.spinner(f"Scraping della pagina {selected_product} in corso..."):
            raw_data = fetch_html_data(selected_product)
            
            if not raw_data.empty:
                st.success("Tabella estratta con successo!")
                
                cleaned_data = process_scraped_table(raw_data)
                
                # Mostriamo la tabella così come l'ha trovata nella pagina web
                st.markdown("### Dati Grezzi Estratti (Raw Table)")
                st.dataframe(cleaned_data, use_container_width=True)
                
                st.info(
                    "💡 **Prossimo passo:** Osserva i nomi delle colonne nella tabella qui sopra. "
                    "Ora che riusciamo a prelevare i dati reali, dovrai identificare quali colonne "
                    "contengono la **Data** e il **Prezzo**, e mapparle all'interno di `process_scraped_table` "
                    "per poter agganciare il motore di calcolo differenziale."
                )
                
            else:
                st.error("Impossibile estrarre tabelle valide da questo URL.")

if __name__ == "__main__":
    main()
