import streamlit as st
import pandas as pd
import numpy as np
import requests
import io

# ---------------------------------------------------------------------------
# 1. Configurazione Endpoint Automatizzati
# ---------------------------------------------------------------------------
# Questa è la "mappa" che lega la UI all'infrastruttura di rete.
# Se ISMEA espone file CSV statici o API interrogabili, inserisci qui gli URL 
# o gli ID dei dataset.
ISMEA_SOURCES = {
    "Grano Duro": {
        # Esempio A: URL diretto a un file aggiornato periodicamente
        "url": "https://www.dati.gov.it/dataset/xxx/grano_duro.csv", 
        "format": "csv",
        "sep": ";"
    },
    "Mais Nazionale": {
        "url": "https://www.dati.gov.it/dataset/yyy/mais.csv",
        "format": "csv",
        "sep": ";"
    },
    "Olio EVO": {
        # Esempio B: Endpoint API REST (es. CKAN) che restituisce JSON
        "url": "https://dati.ismea.it/api/3/action/datastore_search?resource_id=zzz",
        "format": "json",
        "sep": None
    }
}

# ---------------------------------------------------------------------------
# 2. Motore di Estrazione Automatizzato
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def fetch_automated_data(product_key: str) -> pd.DataFrame:
    """
    Recupera i dati automaticamente in base alla configurazione mappata.
    """
    config = ISMEA_SOURCES.get(product_key)
    if not config:
        raise ValueError(f"Nessuna configurazione di rete per {product_key}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/csv"
    }
    
    try:
        response = requests.get(config["url"], headers=headers, timeout=15)
        response.raise_for_status()
        
        if config["format"] == "csv":
            df = pd.read_csv(io.StringIO(response.text), sep=config["sep"])
        elif config["format"] == "json":
            # Per le API CKAN standard, i record sono in result -> records
            json_data = response.json()
            if "result" in json_data and "records" in json_data["result"]:
                df = pd.DataFrame(json_data["result"]["records"])
            else:
                df = pd.DataFrame(json_data) # Fallback generico
        else:
            df = pd.DataFrame()
            
        return df

    except Exception as e:
        st.error(f"Errore durante il prelievo automatizzato: {e}")
        return pd.DataFrame()

def process_ismea_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalizza le colonne. Da calibrare sui nomi reali forniti da ISMEA.
    """
    if df.empty:
        return df
        
    col_mapping = {
        "DATA_RILEVAZIONE": "Data",
        "PREZZO_MEDIO": "Prezzo",
        "PRODOTTO": "Prodotto"
    }
    
    df = df.rename(columns={k: v for k, v in col_mapping.items() if k in df.columns})
    
    if "Data" in df.columns and "Prezzo" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
        # Gestisce i decimali italiani (virgola) se il dato arriva come stringa
        if pd.api.types.is_string_dtype(df["Prezzo"]):
            df["Prezzo"] = df["Prezzo"].str.replace(",", ".")
        df["Prezzo"] = pd.to_numeric(df["Prezzo"], errors="coerce")
        
        df = df.dropna(subset=["Data", "Prezzo"]).sort_values("Data").reset_index(drop=True)
        
    return df

# ---------------------------------------------------------------------------
# 3. Motore di Calcolo Differenziale
# ---------------------------------------------------------------------------
def compute_differentials(df: pd.DataFrame, window: int = 7) -> pd.DataFrame:
    if df.empty or "Prezzo" not in df.columns or len(df) < 2:
        return df
        
    df = df.copy()
    df["Log_Return"] = np.log(df["Prezzo"] / df["Prezzo"].shift(1))
    df["Var_Perc"] = df["Prezzo"].pct_change() * 100
    df["Volatilità_Rolling"] = df["Log_Return"].rolling(window).std() * np.sqrt(252)
    return df

# ---------------------------------------------------------------------------
# 4. Interfaccia Utente
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Listini ISMEA Automatizzati", layout="wide")
    st.title("Analisi Listini ISMEA")
    
    with st.sidebar:
        st.header("Selettore Mercato")
        
        # La UI non mostra più URL, ma solo i nomi logici dei prodotti
        selected_product = st.selectbox(
            "Prodotto Agricolo:",
            options=list(ISMEA_SOURCES.keys())
        )
        
        window_size = st.number_input(
            "Finestra Volatilità Mobile:",
            min_value=3, max_value=30, value=7
        )

    # L'estrazione avviene automaticamente al cambio della selectbox
    with st.spinner(f"Acquisizione dati per {selected_product} in corso..."):
        raw_data = fetch_automated_data(selected_product)
        cleaned_data = process_ismea_dataframe(raw_data)
        processed_data = compute_differentials(cleaned_data, window=window_size)
    
    if not processed_data.empty and "Prezzo" in processed_data.columns:
        st.subheader(f"Dashboard: {selected_product}")
        
        current_price = processed_data["Prezzo"].iloc[-1]
        var_perc = processed_data["Var_Perc"].iloc[-1]
        volatility = processed_data["Volatilità_Rolling"].iloc[-1] * 100
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Ultimo Prezzo", f"{current_price:.2f} €", f"{var_perc:+.2f}%")
        col2.metric("Record Elaborati", len(processed_data))
        col3.metric("Volatilità", f"{volatility:.1f}%" if pd.notna(volatility) else "N/A")
            
        if "Data" in processed_data.columns:
            st.line_chart(processed_data.set_index("Data")["Prezzo"])
            
        with st.expander("Visualizza Tabella Dati Analitica"):
            st.dataframe(processed_data.sort_values(by="Data", ascending=False), use_container_width=True)
    else:
        st.error("I dati estratti non sono validi o gli URL di configurazione necessitano di aggiornamento.")

if __name__ == "__main__":
    main()
