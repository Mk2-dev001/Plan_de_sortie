import streamlit as st

# ✅ À appeler en tout premier
st.set_page_config(page_title="IA Critique de Film", layout="centered")

import json
import random
import os
from pathlib import Path
from openai import OpenAI, OpenAIError

# --- CONFIGURATION ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # 🟢 utilise la variable d’environnement
CHEMIN_JSON = Path("export_wordpress_propre.json")

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
    return f"""Tu es un critique de cinéma et tu écris dans le style de {auteur}.

Voici un extrait typique de son style :

\"\"\"{exemple.strip()}\"\"\"

Maintenant, rédige un article sur le film \"{film}\" à la manière de {auteur}, avec la même sensibilité de ton et de style.
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

# --- INTERFACE STREAMLIT ---
st.title("🎬 Générateur d'article critique")
st.markdown("Crée une critique de film à la manière d'un auteur de ton site WordPress.")

film = st.text_input("🎥 Titre du film", placeholder="Ex : Dune 2")
auteur = st.selectbox("✍️ Choisis un auteur", extraire_auteurs(articles))

if st.button("Générer l’article IA"):
    if not film.strip():
        st.warning("Merci d’entrer un titre de film.")
    else:
        with st.spinner("Génération de l'article..."):
            article = generer_article(film.strip(), auteur)
        st.success("Article généré !")
        st.markdown("---")
        st.markdown(article)
