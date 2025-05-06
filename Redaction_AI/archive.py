import streamlit as st

# Doit être en tout premier
st.set_page_config(page_title="Recherche WordPress", layout="centered")

import json
import os
from pathlib import Path
from datetime import datetime

# CONFIG
CHEMIN_JSON = Path("export_wordpress_propre.json")

@st.cache_data
def charger_articles():
    with open(CHEMIN_JSON, "r", encoding="utf-8") as f:
        articles = json.load(f)
    return articles

articles = charger_articles()

# Interface
st.title("🔍 Recherche dans tes archives WordPress")
requete = st.text_input("Tape un mot-clé (film, auteur, thème...)")

if requete:
    requete_lower = requete.lower()
    matches = []

    for article in articles:
        # Match titre / contenu / tags / catégories / auteur
        in_title = requete_lower in (article.get('title') or '').lower()
        in_content = requete_lower in (article.get('content') or '').lower()
        in_tags = any(requete_lower in (tag or '').lower() for tag in article.get('tags', []))
        in_categories = any(requete_lower in (cat or '').lower() for cat in article.get('categories', []))
        is_author = requete_lower == (article.get('author') or '').lower()

        if in_title or in_content or in_tags or in_categories or is_author:
            # Convertir la date si possible
            try:
                date_obj = datetime.strptime(article.get('date', ''), "%Y-%m-%d %H:%M:%S")
            except:
                date_obj = None

            matches.append({
                "title": article.get("title"),
                "author": article.get("author"),
                "date": article.get("date"),
                "link": article.get("link"),
                "date_obj": date_obj,
            })

    # Trier par date décroissante
    matches_sorted = sorted(matches, key=lambda x: x['date_obj'] or datetime.min, reverse=True)

    st.markdown(f"### 🔎 {len(matches_sorted)} article(s) trouvé(s) pour '{requete}'")

    for a in matches_sorted:
        date_str = f"📅 {a['date']}" if a['date'] else ""
        auteur_str = f"✍️ {a['author']}" if a['author'] else ""
        st.markdown(f"**{a['title']}**")
        st.markdown(f"{date_str} — {auteur_str}")
        st.write(f"Lien trouvé : {a['link']}")
        if a['link']:
            st.markdown(f"[🔗 Lire l'article]({a['link']})")
        st.markdown("---")

else:
    st.info("Entrez un nom de film, un auteur ou un mot-clé pour lancer la recherche.")
