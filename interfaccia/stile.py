"""Stile di FuelMode (palette 1a, font Archivo) applicato all'app: CSS globale.

Il CSS viene da style.py di FuelMode (repository test3), senza i blocchi HTML propri di quell'app; i selettori si
agganciano ad attributi interni di Streamlit.
"""
from __future__ import annotations

import streamlit as st


class Palette:
    """Colori di FuelMode e misure fisse dell'interfaccia."""

    # palette
    SKY = "#8ecae6"
    BLUE_GREEN = "#219ebc"
    DEEP = "#023047"
    AMBER = "#ffb703"
    ORANGE = "#fb8500"
    # sfumature ricavate dalla palette
    BG = "#eef6fa"
    N100, N200, N300, N400, N500, N700 = "#f2f8fb", "#e2eef4", "#c9dde7", "#a5c2d1", "#7c9fb2", "#3a5f74"
    A100, A600, A700 = "#fff3e6", "#e07600", "#a65600"
    # esiti dello score (verde = rifornisci, rosso = aspetta), come il cerchio di FuelMode
    VERDE, ROSSO = "#1f9d55", "#d64545"

    BRAND = "🛢️ Prezzo del petrolio"
    SIDEBAR_W = 290  # larghezza fissa della barra laterale (scheda + 20px di margine sinistro)


_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;600;800&display=swap');
:root {{ --radius-lg: 22px; --radius-md: 14px;
  --shadow-soft: 0 1px 2px rgba(2,48,71,.04), 0 10px 30px rgba(2,48,71,.07); }}
html, body, .stApp {{ font-family: 'Archivo', system-ui, sans-serif; }}
.stApp {{ background: {Palette.BG}; color: {Palette.DEEP}; }}
.stApp *:not(svg *) {{ transition: background-color .2s ease, color .2s ease, box-shadow .2s ease, border-color .2s ease; }}
h1, h2, h3, h4, h5, h6 {{ font-weight: 800 !important; letter-spacing: -0.015em; color: {Palette.DEEP}; }}
[data-testid="stHeaderActionElements"] {{ display: none; }}
hr {{ display: none; }}

/* pagina */
header[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stMainBlockContainer"] {{ padding: 20px 20px 40px; max-width: none; }}
[data-testid="stMain"] [data-testid="stVerticalBlock"] {{ gap: 20px; }}

/* barra laterale: scheda bianca a larghezza fissa, alta quanto la finestra, senza scroll interno;
   20px di margine esterno = stesso spazio che separa le schede della pagina centrale */
section[data-testid="stSidebar"] {{ background: transparent; border: 0; }}
section[data-testid="stSidebar"][aria-expanded="true"] {{ width: {Palette.SIDEBAR_W}px !important;
  min-width: {Palette.SIDEBAR_W}px !important; max-width: {Palette.SIDEBAR_W}px !important; }}
section[data-testid="stSidebar"] > div {{ background: transparent; }}
section[data-testid="stSidebar"] div:has(> [data-testid="stSidebarResizeHandle"]) {{ display: none; }}
/* su schermi stretti la barra laterale si apre sopra la pagina: sfondo pieno attorno alla scheda */
@media (max-width: 767.98px) {{
  section[data-testid="stSidebar"][aria-expanded="true"] {{ background: {Palette.BG}; box-shadow: 0 0 40px rgba(2,48,71,.18); }}
}}
section[data-testid="stSidebar"] > [data-testid="stSidebarContent"] {{ background: #fff; border-radius: var(--radius-lg); margin: 20px 0 20px 20px;
  box-shadow: var(--shadow-soft); width: calc(100% - 20px) !important; height: calc(100vh - 40px);
  padding: 0; overflow-x: hidden; overflow-y: auto; position: relative; }}
[data-testid="stSidebarUserContent"] {{ padding: 12px 14px 10px; }}
[data-testid="stSidebarHeader"] {{ position: absolute; top: 12px; right: 12px; z-index: 2; padding: 0;
  height: auto; min-height: 0; width: auto; }}
[data-testid="stSidebarHeader"] [data-testid="stLogoSpacer"] {{ display: none; }}
/* barra laterale compatta: poco spazio tra i campi, campi e pulsanti bassi */
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 6px; }}
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {{ gap: 8px; }}
[data-testid="stSidebar"] [data-baseweb="input"], [data-testid="stSidebar"] [data-testid="stNumberInputContainer"] {{
  height: 32px; }}
[data-testid="stSidebar"] [data-baseweb="select"] > div {{ min-height: 32px; }}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] {{ min-height: 0; margin-bottom: 0; }}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] {{ gap: 0 12px; }}
[data-testid="stSidebar"] .stSlider {{ margin-top: -6px; margin-bottom: -8px; }}
[data-testid="stSidebar"] .stButton button, [data-testid="stSidebar"] .stDownloadButton button {{
  min-height: 32px; padding: 4px 14px; }}
[data-testid="stSidebar"] .stButton button p {{ font-size: 13px; }}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {{ padding: 8px 12px; }}
[data-testid="stSidebar"] [data-testid="stExpanderDetails"] {{ padding: 4px 12px 12px; }}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {{ padding: 6px 8px; }}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] {{ display: none; }}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{ font-size: 12px; color: {Palette.N700}; }}
[data-testid="stSidebar"] .stRadio [data-testid="stWidgetLabel"] p {{ font-size: 12px; font-weight: 800;
  letter-spacing: .08em; text-transform: uppercase; color: {Palette.N700}; }}
[data-testid="stSidebar"] .stRadio label p {{ font-size: 13px; color: {Palette.DEEP}; }}
[data-testid="stRadioOption"]:not([data-selected="true"]) > div > div:first-child {{
  background: #fff; border: 1.5px solid {Palette.N500}; }}
[data-testid="stRadioOption"]:not([data-selected="true"]):hover > div > div:first-child {{ border-color: {Palette.ORANGE}; }}

/* campi */
[data-baseweb="input"], [data-baseweb="base-input"], [data-testid="stNumberInputContainer"] {{
  background: {Palette.N100} !important; border: 1px solid transparent !important; border-radius: var(--radius-md) !important; }}
[data-baseweb="input"]:hover, [data-testid="stNumberInputContainer"]:hover {{ border-color: {Palette.N300} !important; }}
[data-baseweb="input"]:focus-within, [data-testid="stNumberInputContainer"]:focus-within {{
  border-color: {Palette.BLUE_GREEN} !important; background: #fff !important; }}
[data-baseweb="input"] input {{ background: transparent; color: {Palette.DEEP}; }}
[data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"] {{ background: transparent; border-radius: 10px; }}
[data-testid="stSlider"] [role="slider"] {{ box-shadow: 0 2px 6px rgba(2,48,71,.2); }}
[data-testid="stSliderThumbValue"] {{ color: {Palette.DEEP}; font-weight: 800; }}
[data-testid="stSlider"] [data-baseweb="slider"] > div > div:first-child {{ border-radius: 999px; }}
[data-testid="stTooltipIcon"] svg {{ stroke: {Palette.N500}; }}

/* tab come barra di navigazione (selettori per Streamlit < 1.6x e >= 1.6x) */
.stTabs [data-baseweb="tab-list"], .stTabs [role="tablist"] {{ gap: 4px; align-items: center; flex-wrap: wrap;
  row-gap: 10px; background: #fff; border: 0; box-shadow: var(--shadow-soft); padding: 12px 12px 12px 24px;
  border-radius: var(--radius-lg); overflow: visible; }}
.stTabs [data-baseweb="tab-list"]::before, .stTabs [role="tablist"]::before {{ content: "{Palette.BRAND}";
  margin-right: auto; padding-right: 16px; font-size: 18px; font-weight: 800; letter-spacing: -0.015em; color: {Palette.DEEP}; }}
.stTabs [data-baseweb="tab"], .stTabs [role="tab"] {{ height: auto; padding: 8px 10px; margin: 0; border: 0;
  border-radius: 999px; background: transparent; cursor: pointer; }}
.stTabs [role="tab"] p {{ font-size: 14px; font-weight: 600; color: {Palette.DEEP}; }}
.stTabs [role="tab"]:hover p {{ color: {Palette.ORANGE}; }}
.stTabs [role="tab"][aria-selected="true"] {{ background: {Palette.DEEP}; }}
.stTabs [role="tab"][aria-selected="true"] p {{ color: #fff; }}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"],
.stTabs .react-aria-SelectionIndicator, .stTabs [role="tablist"]::after {{ display: none; }}
/* il contenuto di ogni scheda è una scheda bianca */
.stTabs [role="tabpanel"] {{ margin-top: 20px; padding: 24px; background: #fff; border-radius: var(--radius-lg);
  box-shadow: var(--shadow-soft); }}

/* schede */
[class*="st-key-card"] {{ position: relative; background: #fff; border: 1px solid transparent; border-radius: var(--radius-lg);
  box-shadow: var(--shadow-soft); padding: 24px; gap: 12px !important; }}
.x-title {{ margin: 0; font-size: 20px; line-height: 1.25; font-weight: 800; letter-spacing: -0.015em; color: {Palette.DEEP}; }}
[class*="st-key-card"] p {{ font-size: 14px; }}
[class*="st-key-card"] [data-testid="stCaptionContainer"] p {{ font-size: 13px; color: {Palette.N700}; }}
[class*="st-key-card"] [data-testid="stDeckGlJsonChart"], [class*="st-key-card"] [data-testid="stDataFrame"] {{
  border-radius: var(--radius-md); overflow: hidden; }}

/* bottoni */
.stButton button, .stDownloadButton button {{ border-radius: 999px; border: 0; padding: 10px 18px;
  font-weight: 800; min-height: 40px; }}
.stButton button p, .stDownloadButton button p {{ font-weight: 800; font-size: 14px; }}
.stButton button[kind="primary"] {{ background: {Palette.ORANGE}; color: {Palette.DEEP}; }}
.stButton button[kind="primary"]:hover {{ background: {Palette.A600}; color: {Palette.DEEP}; }}
.stButton button[kind="secondary"], .stDownloadButton button {{ background: {Palette.N200}; color: {Palette.DEEP}; }}
.stButton button[kind="secondary"]:hover, .stDownloadButton button:hover {{ background: {Palette.N300}; color: {Palette.DEEP}; }}

/* metriche di st.metric: riquadri tenui */
div[data-testid="stMetric"] {{ background: {Palette.N100}; border-radius: var(--radius-md); padding: 16px 20px; }}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {{ text-transform: uppercase !important; letter-spacing: .08em; font-size: 11px; color: {Palette.N700}; }}
div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] * {{ font-weight: 800; font-size: 26px; font-variant-numeric: tabular-nums; }}
[data-testid="stAlert"] {{ border-radius: var(--radius-md); border: 0; }}
[data-testid="stExpander"] details {{ border: 0; background: {Palette.N100}; border-radius: var(--radius-md); }}

</style>
"""


class Stile:
    """Aspetto dell'app: CSS globale e, per la versione incorporata in FuelMode, niente cornice."""

    @staticmethod
    def applica() -> None:
        """CSS globale; va chiamata subito dopo st.set_page_config. I grafici prendono colori e font dal tema in
        .streamlit/config.toml."""
        st.markdown(_CSS, unsafe_allow_html=True)

    @staticmethod
    def senza_cornice() -> None:
        """Niente barra laterale, intestazione e margini: la scheda riempie il riquadro di FuelMode."""
        st.markdown("<style>[data-testid='stSidebar'], [data-testid='stSidebarCollapsedControl'], "
                    "[data-testid='stExpandSidebarButton'], header[data-testid='stHeader'] {display: none;} "
                    "[data-testid='stMainBlockContainer'] {padding: 0 !important;} "
                    "[data-testid='stMain'] [data-testid='stElementContainer']:has(style) {display: none;}</style>",
                    unsafe_allow_html=True)
