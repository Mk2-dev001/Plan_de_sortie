import streamlit as st
import os
import sys
import datetime
import openai

# Configuration de la page
st.set_page_config(
    page_title="Multi-Apps MK2",
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
    
    /* Style pour les boutons de la sidebar */
    .sidebar-btn button {
        width: 100%;
        height: 2.5em;
        margin: 0.4em 0;
        font-size: 0.9em;
        border-radius: 12px;
        transition: all 0.3s ease;
    }
    
    .sidebar-btn button:hover {
        transform: translateY(-2px);
    }
    
    .sidebar-image {
        width: 100%;
        height: 80px !important;
        object-fit: cover;
        border-radius: 12px;
        margin-bottom: 0.2em;
    }
    
    .block-container {
        max-width: 1500px;
        margin: auto;
    }
    
    /* Alignement vertical des avatars et messages dans la chatbox */
    [data-testid="stChatMessage"] {
        display: flex;
        align-items: center;
        gap: 0.8em;
        margin-bottom: 0.5em;
    }
    [data-testid="stChatMessageAvatar"] {
        display: none !important;
    }
    [data-testid="stChatMessageAvatar"] img {
        width: 40px;
        height: 40px;
        object-fit: cover;
        border-radius: 50%;
        display: block;
        margin: 0;
        padding: 0;
    }
    [data-testid="stChatMessageContent"] {
        display: flex;
        align-items: center;
        min-height: 40px;
        margin: 0;
        padding: 0;
    }
    </style>
    <style>
    /* Solution pour masquer complètement l'avatar utilisateur et ne garder que celui du bot */
    [data-testid="stChatMessageAvatar"] {
        display: none !important;
    }

    /* Afficher UNIQUEMENT l'avatar du bot */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageContent"]:has(img[alt="agent.png"])) [data-testid="stChatMessageAvatar"] {
        display: flex !important;
    }

    /* Supprimer l'espace réservé aux avatars pour les messages utilisateur */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageContent"]:not(:has(img[alt="agent.png"]))) {
        padding-left: 0 !important;
    }

    /* Aligner le texte utilisateur à droite pour une meilleure distinction visuelle */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageContent"]:not(:has(img[alt="agent.png"]))) [data-testid="stChatMessageContent"] {
        justify-content: flex-end;
    }

    /* Empêcher les retours à la ligne automatiques dans les messages */
    [data-testid="stChatMessageContent"] p {
        white-space: normal !important;
        word-wrap: break-word !important;
        margin: 0 !important;
    }
    </style>
    <style>
    /* Style pour supprimer toute bordure/ombre sur les images d'apps */
    .stImage img {
        box-shadow: none !important;
        border: none !important;
        background: transparent !important;
    }
    </style>
    <style>
    /* Centrage vertical parfait de l'icône et du texte dans la colonne */
    .app-icon-center {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 140px; /* Ajuste la hauteur minimale selon ton besoin */
        height: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

# Titre principal
st.markdown('<h1 class="title">Multi-Applications MK2</h1>', unsafe_allow_html=True)

# --- Chatbox OpenAI ---
openai_api_key = st.secrets["openai_api_key"] if "openai_api_key" in st.secrets else st.text_input("Entrez votre clé OpenAI API :", type="password")

if openai_api_key:
    st.markdown("<hr>", unsafe_allow_html=True)
    # Affichage des icônes d'applications avec st.columns et st.image
    cols = st.columns(7)
    icons = [
        "assets/plandesortie.png",
        "assets/buissnessplan.png",
        "assets/Analyseurcreateurdecontenu.png",
        "assets/redactionIA.png",
        "assets/archivageIA.png",
        "assets/planning.png",
        "assets/revenucalculator.png"
    ]
    for col, icon in zip(cols, icons):
        with col:
            st.markdown('<div class="app-icon-center">', unsafe_allow_html=True)
            st.image(icon, width=48)
            st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center;'>Assistant IA</h3>", unsafe_allow_html=True)
    
    # Centrage de la chatbox au milieu
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # Display chat messages from history
        for message in st.session_state.messages:
            if message["role"] == "assistant":
                with st.chat_message("assistant", avatar="assets/agent.png"):
                    st.markdown(message["content"])
            else:
                with st.chat_message("user"):
                    st.markdown(message["content"])

        # Chat input
        if prompt := st.chat_input("Posez une question ou décrivez votre besoin :"):
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)

            # System prompt for app suggestions
            system_prompt = (
                "Tu es un assistant IA intelligent et bienveillant qui aide les utilisateurs à choisir l'application la plus adaptée à leurs besoins. "
                "Voici les applications disponibles et leurs fonctionnalités :\n\n"
                "1. **AI Map** : Une application spécialisée dans la planification de sortie de films. "
                "Elle permet de générer automatiquement un plan de sortie sur une carte "
                "en analysant les meilleures stratégies de déploiement géographique en fonction du contexte.\n\n"
                "2. **Business Plan** : Un outil complet pour créer et analyser des business plans, "
                "Rédiger un business plan complet pour n'importe quel projet.\n\n"
                "3. **Créateur de Contenu** : Un outil d'analyse et de vérification des créateurs de contenu. "
                "Il permet d'obtenir des statistiques détaillées et de faire un background check sur n'importe quel créateur "
                "(par exemple : Squeezie). L'application fournit des insights sur leur audience, leur engagement, "
                "et d'autres métriques importantes.\n\n"
                "4. **Rédaction IA** : Un assistant d'écriture intelligent qui aide à rédiger, "
                "rédige des articles à la façon de n'importe quel auteur de Trois Couleurs.\n\n"
                "5. **Archivage** : Un système de gestion documentaire intelligent pour organiser, "
                "classer et retrouver facilement des documents importants.\n\n"
                "6. **Planning** : Une application qui permet d'intégrer automatiquement des plannings générés par l'IA "
                "directement dans Outlook Calendar, facilitant la gestion des emplois du temps et des rendez-vous.\n\n"
                "7. **Revenue Calculator** : Un outil spécialisé pour calculer les revenus potentiels en fonction "
                "d'un fichier Excel contenant les données des salles de cinéma, permettant d'optimiser les projections "
                "financières et l'analyse des performances.\n\n"
                "Pour chaque demande de l'utilisateur :\n"
                "1. Analyse attentivement le besoin exprimé\n"
                "2. Réponds de manière précise et utile à la question\n"
                "3. Suggère l'application la plus pertinente en expliquant pourquoi elle correspond au besoin\n"
                "4. Si aucune application ne correspond parfaitement, explique pourquoi et suggère la meilleure alternative\n"
                "5. Sois toujours poli, professionnel et constructif dans tes réponses\n"
                "6. IMPORTANT : Mets toujours les noms des applications en gras en utilisant la syntaxe markdown **nom de l'app**"
            )

            # Get assistant response using new OpenAI API
            client = openai.OpenAI(api_key=openai_api_key)
            messages = [{"role": "system", "content": system_prompt}] + st.session_state.messages
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages
            )
            assistant_reply = response.choices[0].message.content

            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
            
            # Display assistant response
            with st.chat_message("assistant", avatar="assets/agent.png"):
                st.markdown(assistant_reply)

# Sidebar : Applications et historique
with st.sidebar:
    with st.expander("📱 Applications", expanded=True):
        # AI Map
        st.image("assets/plandesortie.png", use_container_width=True)
        st.markdown('<div class="sidebar-btn">', unsafe_allow_html=True)
        if st.button("🚀 AI Map", key="ai_map"):
            os.system("streamlit run Ai_Map/ai.py")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Business Plan
        st.image("assets/buissnessplan.png", use_container_width=True)
        st.markdown('<div class="sidebar-btn">', unsafe_allow_html=True)
        if st.button("📊 Business Plan", key="business_plan"):
            os.system("streamlit run BuissnessPlan/business_plan_questionnaire.py")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Créateur de Contenu
        st.image("assets/Analyseurcreateurdecontenu.png", use_container_width=True)
        st.markdown('<div class="sidebar-btn">', unsafe_allow_html=True)
        if st.button("🎨 Créateur de Contenu", key="content_creator"):
            os.system("streamlit run CreateurContenue/app.py")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Rédaction IA
        st.image("assets/redactionIA.png", use_container_width=True)
        st.markdown('<div class="sidebar-btn">', unsafe_allow_html=True)
        if st.button("✍️ Rédaction IA", key="redaction_ia"):
            os.system("streamlit run Redaction_AI/app.py")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Archivage
        st.image("assets/archivageIA.png", use_container_width=True)
        st.markdown('<div class="sidebar-btn">', unsafe_allow_html=True)
        if st.button("📁 Archivage", key="archive"):
            os.system("streamlit run Archivage/archive.py")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Planning
        st.image("assets/planning.png", use_container_width=True)
        st.markdown('<div class="sidebar-btn">', unsafe_allow_html=True)
        if st.button("📅 Planning", key="planning"):
            os.system("streamlit run Planning/app.py")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Revenue Calculator
        st.image("assets/revenucalculator.png", use_container_width=True)
        st.markdown('<div class="sidebar-btn">', unsafe_allow_html=True)
        if st.button("💰 Revenue Calculator", key="revenue_calculator"):
            os.system("streamlit run RevenueCalculator/app.py")
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Historique des fichiers
    with st.expander("📂 Historique des fichiers", expanded=True):
        historique_dir = "historique_file"
        if os.path.exists(historique_dir):
            fichiers = os.listdir(historique_dir)
            if fichiers:
                for fichier in fichiers:
                    chemin = os.path.join(historique_dir, fichier)
                    if os.path.isfile(chemin):
                        mod_time = os.path.getmtime(chemin)
                        date_str = datetime.datetime.fromtimestamp(mod_time).strftime('%d/%m/%Y %H:%M')
                        st.write(f"📄 {fichier}  ", f"*{date_str}*")
            else:
                st.write("Aucun fichier téléchargé.")
        else:
            st.write("Dossier non trouvé.") 