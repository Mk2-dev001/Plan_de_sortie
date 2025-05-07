import streamlit as st
import os
import sys

# Configuration de la page
st.set_page_config(
    page_title="Multi-Apps Navigation",
    page_icon="🚀",
    layout="wide"
)

# Style CSS personnalisé
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@300;400;500;600;700&display=swap');
    
    * {
        font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    .main {
        padding: 2rem;
        background: linear-gradient(135deg, #18191A 0%, #232526 100%);
        min-height: 100vh;
    }
    
    .stButton>button {
        width: 100%;
        height: 4.5em;
        margin: 1em 0;
        font-size: 1.2em;
        background: rgba(255,255,255,0.10);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1.5px solid rgba(255,255,255,0.18);
        border-radius: 20px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.18);
        transition: all 0.5s cubic-bezier(0.4,0,0.2,1);
        color: #f5f6fa;
        font-weight: 500;
        position: relative;
        overflow: hidden;
    }
    
    .stButton>button:hover {
        transform: translateY(-4px) scale(1.02);
        box-shadow: 0 12px 40px rgba(0,0,0,0.22);
        background: rgba(255,255,255,0.18);
        border: 1.5px solid rgba(255,255,255,0.28);
        color: #fff;
    }
    
    .stButton>button:active {
        transform: translateY(-2px) scale(0.98);
    }
    
    .stButton>button::after {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: linear-gradient(45deg, transparent, rgba(255,255,255,0.10), transparent);
        transform: translateX(-100%);
        transition: 0.8s;
    }
    
    .stButton>button:hover::after {
        transform: translateX(100%);
    }
    
    .title {
        text-align: center;
        color: #fff;
        font-size: 4em;
        font-weight: 700;
        margin: 1em 0 0.5em 0;
        letter-spacing: -2px;
        text-shadow: 0 6px 32px rgba(0,0,0,0.35), 0 1px 0 #fff, 0 0 8px #fff2;
        animation: fadeInDown 1.2s cubic-bezier(0.4,0,0.2,1);
    }
    
    .app-title {
        font-size: 1.25em;
        color: #eaeaea;
        font-weight: 600;
        margin-bottom: 1em;
        text-align: center;
        letter-spacing: -0.5px;
        text-shadow: 0 2px 8px rgba(0,0,0,0.18);
        transition: all 0.4s cubic-bezier(0.4,0,0.2,1);
    }
    
    .app-title:hover {
        transform: scale(1.05);
        color: #fff;
    }
    
    div[data-testid="stVerticalBlock"] > div:nth-child(1) {
        padding-top: 2em;
    }
    
    @keyframes fadeInDown {
        from { opacity: 0; transform: translateY(-30px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .stColumn {
        transition: all 0.4s cubic-bezier(0.4,0,0.2,1);
        padding: 1rem;
    }
    
    .stColumn:hover {
        transform: translateY(-8px);
    }
    
    .stAlert {
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.08);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.2);
    }
    </style>
    """, unsafe_allow_html=True)

# Titre principal
st.markdown('<h1 class="title">Navigation Multi-Applications</h1>', unsafe_allow_html=True)

# Création de trois colonnes pour les boutons
col1, col2, col3 = st.columns(3)

# Fonction pour lancer une application
def launch_app(app_path):
    if os.path.exists(app_path):
        os.system(f"streamlit run {app_path}")
    else:
        st.error(f"L'application n'a pas été trouvée dans {app_path}")

# Boutons de navigation
with col1:
    st.markdown('<p class="app-title">AI Map</p>', unsafe_allow_html=True)
    if st.button("Lancer AI Map", key="ai_map"):
        launch_app("Ai_Map/ai.py")

with col2:
    st.markdown('<p class="app-title">Business Plan</p>', unsafe_allow_html=True)
    if st.button("Lancer Business Plan", key="business_plan"):
        launch_app("BuissnessPlan/business_plan_questionnaire.py")

with col3:
    st.markdown('<p class="app-title">Créateur de Contenu</p>', unsafe_allow_html=True)
    if st.button("Lancer Créateur de Contenu", key="content_creator"):
        launch_app("CreateurContenue/app.py")

# Nouvelle ligne de colonnes pour Rédaction IA et Archive
col4, col5 = st.columns(2)

with col4:
    st.markdown('<p class="app-title">Rédaction IA</p>', unsafe_allow_html=True)
    if st.button("Lancer Rédaction IA", key="redaction_ia"):
        launch_app("Redaction_AI/app.py")

with col5:
    st.markdown('<p class="app-title">Archive</p>', unsafe_allow_html=True)
    if st.button("Lancer Archive", key="archive"):
        launch_app("Archivage/archive.py") 