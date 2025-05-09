import streamlit as st
import os
import sys

# Configuration de la page
st.set_page_config(
    page_title="Multi-Apps Navigation MK2",
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
    
    /* Thème sombre par défaut */
    body, .main, .stApp {
        background: linear-gradient(135deg, #f7f7f7 0%, #eaeaea 100%) !important;
        color: #18191A !important;
    }
    
    /* Adaptation automatique selon le thème du système */
    @media (prefers-color-scheme: dark) {
        body, .main, .stApp {
            background: linear-gradient(135deg, #18191A 0%, #232526 100%) !important;
            color: #fff !important;
        }
        .title, .app-title {
            color: #fff !important;
            text-shadow: 0 6px 32px rgba(0,0,0,0.35), 0 1px 0 #fff, 0 0 8px #fff2;
        }
        .stButton>button {
            background: rgba(255,255,255,0.08);
            color: #f5f6fa;
            border: 1px solid rgba(255,255,255,0.15);
            backdrop-filter: blur(10px);
        }
        .stButton>button:hover {
            background: rgba(255,255,255,0.15); 
            color: #fff;
            border: 1px solid rgba(255,255,255,0.25);
            transform: translateY(-2px);
            box-shadow: 0 12px 40px rgba(0,0,0,0.3);
        }
    }
    
    .stButton>button {
        width: 100%;
        height: 3.5em;
        margin: 0.8em 0;
        font-size: 1.1em;
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.15);
        transition: all 0.4s cubic-bezier(0.4,0,0.2,1);
        font-weight: 500;
        position: relative;
        overflow: hidden;
    }
    
    .stButton>button:active {
        transform: translateY(1px) scale(0.98);
    }
    
    .stButton>button::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(
            90deg,
            transparent,
            rgba(255,255,255,0.2),
            transparent
        );
        transition: 0.5s;
    }
    
    .stButton>button:hover::before {
        left: 100%;
    }
    
    .title {
        text-align: center;
        font-size: 3.5em;
        font-weight: 700;
        margin: 0.8em 0 0.4em 0;
        letter-spacing: -2px;
        color: #18191A !important;
        text-shadow: 0 2px 8px rgba(0,0,0,0.10), 0 1px 0 #fff;
        transition: filter 0.3s;
        filter: brightness(1.08) saturate(1.05);
    }
    
    @media (prefers-color-scheme: dark) {
        .title {
            background: linear-gradient(90deg, #ff6b6b 0%, #ff8787 50%, #ffa5a5 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            color: unset !important;
            text-shadow: 0 6px 32px rgba(0,0,0,0.35), 0 1px 0 #fff, 0 0 8px #fff2;
        }
    }
    
    .title:hover {
        filter: brightness(1.15) saturate(1.1) drop-shadow(0 4px 16px rgba(0,0,0,0.10));
    }
    
    .app-title {
        font-size: 1.2em;
        font-weight: 600;
        margin-bottom: 0.8em;
        text-align: center;
        letter-spacing: -0.5px;
        text-shadow: 0 2px 8px rgba(0,0,0,0.18);
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
    }
    
    .app-title:hover {
        transform: scale(1.03);
    }
    
    div[data-testid="stVerticalBlock"] > div:nth-child(1) {
        padding-top: 1.5em;
    }
    
    @keyframes fadeInDown {
        from { opacity: 0; transform: translateY(-20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .stColumn {
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
        padding: 0.8rem;
    }
    
    .stColumn:hover {
        transform: translateY(-5px);
    }
    
    .stAlert {
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.08);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.2);
    }
    
    .stImage, .stContainer {
        border-radius: 24px !important;
        box-shadow: 0 8px 32px rgba(0,0,0,0.07), 0 1.5px 8px rgba(0,0,0,0.03);
        background: rgba(255,255,255,0.82) !important;
        border: 1px solid #ececec;
        transition: box-shadow 0.3s, transform 0.3s;
    }
    
    .stImage:hover, .stContainer:hover {
        box-shadow: 0 16px 48px rgba(0,0,0,0.13), 0 2px 12px rgba(0,0,0,0.06);
        transform: translateY(-3px) scale(1.01);
    }
    
    .app-image {
        width: 100%;
        height: 100px !important;
        object-fit: cover;
        border-radius: 20px;
        margin-bottom: 0.4em;
        box-shadow: 0 8px 32px rgba(0,0,0,0.15);
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
        filter: brightness(0.95);
        position: relative;
        overflow: hidden;
    }
    
    .app-image:hover {
        transform: scale(1.04) rotate(-1deg);
        box-shadow: 0 12px 40px rgba(0,0,0,0.25);
        filter: brightness(1.05) saturate(1.1);
        cursor: pointer;
    }
    
    .app-image::after {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background: linear-gradient(120deg, rgba(255,255,255,0.13) 0%, rgba(255,255,255,0.03) 100%);
        pointer-events: none;
    }
    
    .apple-btn button {
        background: rgba(255,255,255,0.08);
        color: #fff;
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 14px;
        padding: 0.6em 1.8em;
        font-size: 1.1em;
        font-weight: 500;
        margin-top: 0.4em;
        margin-bottom: 1.2em;
        box-shadow: 0 8px 32px rgba(0,0,0,0.15);
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
        cursor: pointer;
        backdrop-filter: blur(10px);
    }
    
    .apple-btn button:hover {
        background: rgba(255,255,255,0.15);
        color: #fff;
        border: 1px solid rgba(255,255,255,0.25);
        transform: translateY(-2px);
        box-shadow: 0 12px 40px rgba(0,0,0,0.25);
    }
    
    /* Effet de brillance sur les boutons */
    .apple-btn button::after {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: linear-gradient(
            45deg,
            transparent,
            rgba(255,255,255,0.1),
            transparent
        );
        transform: rotate(45deg);
        transition: 0.5s;
    }
    
    .apple-btn button:hover::after {
        transform: rotate(45deg) translate(50%, 50%);
    }
    </style>
    """, unsafe_allow_html=True)

# Titre principal
st.markdown('<h1 class="title">Navigation Multi-Applications MK2</h1>', unsafe_allow_html=True)

# Style bouton Apple
st.markdown("""
    <style>
    .apple-btn button {
        background: rgba(255,255,255,0.10);
        color: #fff;
        border: 1.5px solid rgba(255,255,255,0.18);
        border-radius: 18px;
        padding: 0.7em 2em;
        font-size: 1.15em;
        font-weight: 500;
        margin-top: 0.5em;
        margin-bottom: 1.5em;
        box-shadow: 0 8px 32px rgba(0,0,0,0.18);
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
        cursor: pointer;
    }
    .apple-btn button:hover {
        background: rgba(255,255,255,0.18);
        color: #fff;
        border: 1.5px solid rgba(255,255,255,0.28);
        transform: scale(1.04);
    }
    </style>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    st.image("assets/plandesortie.png", use_container_width=True)
    with st.container():
        st.markdown('<div class="apple-btn">', unsafe_allow_html=True)
        if st.button("Lancer AI Map", key="ai_map"):
            os.system("streamlit run Ai_Map/ai.py")
        st.markdown('</div>', unsafe_allow_html=True)
with col2:
    st.image("assets/buissnessplan.png", use_container_width=True)
    with st.container():
        st.markdown('<div class="apple-btn">', unsafe_allow_html=True)
        if st.button("Lancer Business Plan", key="business_plan"):
            os.system("streamlit run BuissnessPlan/business_plan_questionnaire.py")
        st.markdown('</div>', unsafe_allow_html=True)
with col3:
    st.image("assets/Analyseurcreateurdecontenu.png", use_container_width=True)
    with st.container():
        st.markdown('<div class="apple-btn">', unsafe_allow_html=True)
        if st.button("Lancer Créateur de Contenu", key="content_creator"):
            os.system("streamlit run CreateurContenue/app.py")
        st.markdown('</div>', unsafe_allow_html=True)
col4, col5 = st.columns(2)
with col4:
    st.image("assets/redactionIA.png", use_container_width=True)
    with st.container():
        st.markdown('<div class="apple-btn">', unsafe_allow_html=True)
        if st.button("Lancer Rédaction IA", key="redaction_ia"):
            os.system("streamlit run Redaction_AI/app.py")
        st.markdown('</div>', unsafe_allow_html=True)
with col5:
    st.image("assets/archivageIA.png", use_container_width=True)
    with st.container():
        st.markdown('<div class="apple-btn">', unsafe_allow_html=True)
        if st.button("Lancer Archive", key="archive"):
            os.system("streamlit run Archivage/archive.py")
        st.markdown('</div>', unsafe_allow_html=True) 