import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch
from io import BytesIO
import datetime

# ✅ À appeler en tout premier
st.set_page_config(page_title="IA Critique de Film", layout="centered")

import json
import random
import os
from pathlib import Path
from openai import OpenAI, OpenAIError

# --- CONFIGURATION ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # 🟢 utilise la variable d'environnement
CHEMIN_JSON = Path("Redaction_AI/export_wordpress_propre.json")

# --- CHARGER LES DONNÉES ---
@st.cache_data
def charger_articles():
    with open(CHEMIN_JSON, "r", encoding="utf-8") as f:
        articles = json.load(f)
    return articles

articles = charger_articles()

# --- UTILITAIRES ---
def extraire_auteurs(articles):
    return sorted(set(a['author'] for a in articles if a['author']))

def trouver_extrait_par_auteur(nom_auteur):
    textes = [a['content'] for a in articles if a['author'].lower() == nom_auteur.lower() and len(a['content']) > 300]
    if not textes:
        return None
    return random.choice(textes[:5])

def construire_prompt(film, auteur, exemple):
    return f"""Tu es un critique de cinéma professionnel qui écrit pour un grand média de presse, dans le style de {auteur}.

Voici un extrait typique de son style :

\"\"\"{exemple.strip()}\"\"\"

Maintenant, rédige un article critique sur le film \"{film}\" à la manière de {auteur}, en suivant ces consignes :
- Structure ton article comme un article de presse avec un titre accrocheur, un chapô (introduction concise), et des paragraphes bien structurés
- Inclus des informations factuelles sur le film (réalisateur, acteurs principaux, date de sortie)
- Adopte un ton journalistique professionnel tout en gardant la sensibilité de {auteur}
- Utilise des citations ou des extraits de dialogues pertinents si possible
- Conclus avec une analyse personnelle et une recommandation claire
- Garde une longueur appropriée pour un article de presse (environ 800-1000 mots)
"""

def generer_article(film, auteur):
    exemple = trouver_extrait_par_auteur(auteur)
    if not exemple:
        return "❌ Aucun extrait d'article trouvé pour cet auteur."

    prompt = construire_prompt(film, auteur, exemple)

    try:
        response = client.chat.completions.create(
            model="gpt-4",  # ou "gpt-3.5-turbo"
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()

    except OpenAIError as e:
        return f"❌ Erreur OpenAI : {str(e)}"

def generer_pdf(titre_film, auteur, contenu):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Style personnalisé pour le titre
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30
    )
    
    # Style pour le contenu
    content_style = ParagraphStyle(
        'CustomContent',
        parent=styles['Normal'],
        fontSize=12,
        leading=14
    )
    
    # Préparation du contenu
    elements = []
    
    # Titre
    elements.append(Paragraph(f"Critique : {titre_film}", title_style))
    elements.append(Spacer(1, 20))
    
    # Métadonnées
    date = datetime.datetime.now().strftime("%d/%m/%Y")
    elements.append(Paragraph(f"Par {auteur} - {date}", styles['Normal']))
    elements.append(Spacer(1, 30))
    
    # Contenu
    for paragraph in contenu.split('\n\n'):
        if paragraph.strip():
            elements.append(Paragraph(paragraph, content_style))
            elements.append(Spacer(1, 12))
    
    # Génération du PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- INTERFACE STREAMLIT ---
st.title("🎬 Générateur d'article critique")
st.markdown("Crée une critique de film à la manière d'un auteur de ton site WordPress.")

film = st.text_input("🎥 Titre du film", placeholder="Ex : Dune 2")
auteur = st.selectbox("✍️ Choisis un auteur", extraire_auteurs(articles))

if st.button("Générer l'article IA"):
    if not film.strip():
        st.warning("Merci d'entrer un titre de film.")
    else:
        with st.spinner("Génération de l'article..."):
            article = generer_article(film.strip(), auteur)
        st.success("Article généré !")
        st.markdown("---")
        st.markdown(article)
        
        # Bouton de téléchargement PDF
        if article and not article.startswith("❌"):
            pdf_buffer = generer_pdf(film.strip(), auteur, article)
            st.download_button(
                label="📥 Télécharger en PDF",
                data=pdf_buffer,
                file_name=f"critique_{film.lower().replace(' ', '_')}.pdf",
                mime="application/pdf"
            )
