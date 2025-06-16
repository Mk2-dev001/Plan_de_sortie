# --- ai.py ---
# Application Streamlit pour aider à planifier des projections de films
# -*- coding: utf-8 -*-

import streamlit as st
import json
import openai
from openai import OpenAI
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from geopy.distance import geodesic # Utilise geodesic pour des distances plus précises
import folium
from streamlit_folium import st_folium # Pour mieux intégrer Folium dans Streamlit
import os
import pandas as pd
import uuid
import io # Ajouté pour le buffer Excel en mémoire

# --- CONFIGURATION DE LA PAGE (DOIT ÊTRE LA PREMIÈRE COMMANDE STREAMLIT) ---
st.set_page_config(layout="wide", page_title="Assistant Cinéma MK2", page_icon="🗺️")

# --- Configuration (Variables globales) ---
GEOCATED_CINEMAS_FILE = "Ai_Map/cinemas_groupedBig.json"
GEOCODER_USER_AGENT = "CinemaMapApp/1.0 (App)"
GEOCODER_TIMEOUT = 10

# --- Initialisation du client OpenAI ---
try:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    if not client.api_key:
        st.error("La clé API OpenAI n'a pas été trouvée. Veuillez définir la variable d'environnement OPENAI_API_KEY.")
        st.stop()
except Exception as e:
    st.error(f"Erreur lors de l'initialisation du client OpenAI : {e}")
    st.stop()

# --- Chargement des données des cinémas pré-géocodées ---
cinemas_ignored_info = None
try:
    with open(GEOCATED_CINEMAS_FILE, "r", encoding="utf-8") as f:
        cinemas_data = json.load(f)
    original_count = len(cinemas_data)
    cinemas_data = [c for c in cinemas_data if c.get('lat') is not None and c.get('lon') is not None]
    valid_count = len(cinemas_data)
    if original_count > valid_count:
        cinemas_ignored_info = f"{original_count - valid_count} cinémas sans coordonnées valides ont été ignorés lors du chargement."
except FileNotFoundError:
    st.error(f"ERREUR : Le fichier de données '{GEOCATED_CINEMAS_FILE}' est introuvable.")
    st.error("Veuillez exécuter le script 'preprocess_cinemas.py' pour générer ce fichier.")
    st.stop()
except json.JSONDecodeError:
    st.error(f"ERREUR : Le fichier de données '{GEOCATED_CINEMAS_FILE}' contient un JSON invalide.")
    st.stop()
except Exception as e:
    st.error(f"Erreur inattendue lors du chargement des données des cinémas : {e}")
    st.stop()

# --- Initialisation du Géocodeur (pour les requêtes utilisateur) ---
geolocator = Nominatim(user_agent=GEOCODER_USER_AGENT, timeout=GEOCODER_TIMEOUT)

# --- Fonctions ---

@st.cache_data(show_spinner=False)

def analyser_requete_ia(question: str):
    """
    Interprète la requête de l'utilisateur en utilisant GPT-4o pour extraire
    les localisations et la fourchette de spectateurs cible.
    Retourne un tuple (liste_instructions, reponse_brute_ia) ou ([], "") en cas d'échec.
    """
    system_prompt = (
        "Tu es un expert en distribution de films en salles en France. L'utilisateur te décrit un projet (test, avant-première, tournée, etc.).\n\n"

        "🎯 Ton objectif : retourner une liste JSON valide de villes avec :\n"
        "- \"localisation\" : une ville en France,\n"
        "- \"nombre\" : nombre de spectateurs à atteindre,\n"
        "- \"nombre_seances\" : (optionnel) nombre de séances prévues,\n"
        "- \"priorite_grandes_salles\" : (optionnel) true si l'utilisateur demande explicitement les plus grandes salles.\n\n"

        "🎯 Si l'utilisateur demande les plus grandes salles :\n"
        "- Mets \"priorite_grandes_salles\" à true\n"
        "- Le nombre de spectateurs sera ignoré car on prendra les plus grandes salles disponibles\n\n"

        "🎯 Si l'utilisateur précise un nombre de séances et une fourchette de spectateurs (ex : entre 30 000 et 40 000) :\n"
        "- Choisis un total réaliste dans cette fourchette,\n"
        "- Répartis ce total entre les villes proportionnellement au nombre de séances,\n"
        "- Ne dépasse jamais le maximum, et ne descends jamais en dessous du minimum.\n\n"

        "🎯 Si l'utilisateur précise seulement une fourchette de spectateurs pour une zone :\n"
        "- Choisis un total dans la fourchette,\n"
        "- Répartis les spectateurs équitablement entre les villes de cette zone,\n"
        "- Suppose 1 séance par ville sauf indication contraire.\n\n"

        "🎯 Si plusieurs zones sont mentionnées, génère plusieurs blocs JSON.\n\n"

        "🗺️ Pour les zones vagues, utilise les remplacements suivants :\n"
        "- 'idf', 'île-de-france', 'région parisienne' → ['île-de-france']\n"
        "- 'sud', 'paca', 'sud de la France', 'provence' → ['Marseille', 'Toulouse', 'Nice']\n"
        "- 'nord', 'hauts-de-france' → ['Lille']\n"
        "- 'ouest', 'bretagne', 'normandie' → ['Nantes', 'Rennes', 'Amiens']\n"
        "- 'est', 'grand est', 'alsace' → ['Strasbourg']\n"
        "- 'centre', 'centre-val de loire', 'auvergne' → ['Clermont-Ferrand']\n"
        "- 'France entière', 'toute la France', 'province', 'le territoire', 'le reste du territoire français' → [\n"
        "   'Île-de-france', 'Lille', 'Strasbourg', 'Lyon', 'Marseille', 'Nice',\n"
        "   'Toulouse', 'Montpellier', 'Bordeaux', 'Limoges', 'Nantes', 'Rennes',\n"
        "   'Caen', 'Dijon', 'Clermont-Ferrand', 'Orléans', 'Besançon'\n"
        "]\n\n"

        "💡 Le résultat doit être une **liste JSON strictement valide** :\n"
        "- Format : [{\"localisation\": \"Paris\", \"nombre\": 1000, \"nombre_seances\": 10, \"priorite_grandes_salles\": true}]\n"
        "- Utilise des guillemets doubles,\n"
        "- Mets des virgules entre les paires clé/valeur,\n"
        "- Ne retourne **aucun texte en dehors** du JSON.\n\n"

        "💡 Si aucun lieu ni objectif n'est identifiable, retourne simplement : []\n\n"

        "🔐 Règle obligatoire :\n"
        "- Le **nombre total de séances** (addition des \"nombre_seances\") doit correspondre **exactement** à ce que demande l'utilisateur,\n"
        "- Ne t'arrête pas à une distribution ronde ou facile : ajuste si besoin pour que la somme soit strictement exacte."
        "🔐 Règle stricte sur la fourchette :\n"
        "- Si l'utilisateur donne une fourchette de spectateurs (ex : minimum 30 000, maximum 160 000),\n"
        "- Alors le **nombre total de spectateurs** (toutes zones confondues) doit rester **strictement dans cette fourchette**.\n"
        "- Tu ne dois **pas appliquer cette fourchette à une seule zone**, mais à l'ensemble de la demande.\n"
    )

    raw_response = ""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ]
        )
        raw_response = response.choices[0].message.content.strip()
        try:
            data = json.loads(raw_response)
            if isinstance(data, dict) and "message" in data:
                st.warning(f"⚠️ L'IA a répondu : {data['message']}")
                return [], raw_response
            if isinstance(data, dict) and 'localisation' in data and 'nombre' in data:
                localisation = str(data['localisation']).strip()
                try: nombre = int(data['nombre'])
                except ValueError: nombre = 0
                result = [{"localisation": localisation, "nombre": nombre}]
                if 'nombre_seances' in data:
                    try: result[0]['nombre_seances'] = int(data['nombre_seances'])
                    except (ValueError, TypeError): pass
                if 'priorite_grandes_salles' in data:
                    result[0]['priorite_grandes_salles'] = bool(data['priorite_grandes_salles'])
                return result, raw_response
            elif isinstance(data, list):
                valid_data = []
                all_valid = True
                for item in data:
                    if isinstance(item, dict) and 'localisation' in item:
                        # Si priorite_grandes_salles est true, on peut ignorer le nombre
                        if item.get('priorite_grandes_salles', False):
                            item['nombre'] = 0  # On met 0 car il sera ignoré
                        elif 'nombre' not in item:
                            all_valid = False
                            continue
                        else:
                            try: item['nombre'] = int(item['nombre'])
                            except (ValueError, TypeError): item['nombre'] = 0; all_valid = False
                        
                        if 'nombre_seances' in item:
                            try: item['nombre_seances'] = int(item['nombre_seances'])
                            except (ValueError, TypeError):
                                if 'nombre_seances' in item: del item['nombre_seances']
                        
                        if 'priorite_grandes_salles' in item:
                            item['priorite_grandes_salles'] = bool(item['priorite_grandes_salles'])
                        
                        valid_data.append(item)
                    else:
                        all_valid = False
                if not all_valid:
                     st.warning("Certains éléments retournés par l'IA n'ont pas le format attendu (localisation/nombre).")
                return valid_data, raw_response
            elif isinstance(data, dict):
                potential_keys = ['resultats', 'projections', 'locations', 'intentions', 'data', 'result']
                for key in potential_keys:
                    if key in data and isinstance(data[key], list):
                        extracted = data[key]
                        valid_data = []
                        all_valid = True
                        for item in extracted:
                           if isinstance(item, dict) and 'localisation' in item and 'nombre' in item:
                                try: item['nombre'] = int(item['nombre'])
                                except (ValueError, TypeError): item['nombre'] = 0; all_valid = False
                                if 'nombre_seances' in item:
                                    try: item['nombre_seances'] = int(item['nombre_seances'])
                                    except (ValueError, TypeError):
                                        if 'nombre_seances' in item: del item['nombre_seances']
                                valid_data.append(item)
                           else:
                                all_valid = False
                        if not all_valid:
                             st.warning("Certains éléments (dans un objet) retournés par l'IA n'ont pas le format attendu.")
                        return valid_data, raw_response
                st.warning("L'IA a retourné un objet, mais aucune structure attendue (liste d'intentions) n'a été trouvée.")
                return [], raw_response
            else:
                st.warning("La réponse n'est ni une liste ni un dictionnaire exploitable.")
                return [], raw_response
        except json.JSONDecodeError:
            st.warning("La réponse n'était pas un JSON valide, tentative d'extraction manuelle...")
            try:
                json_part = raw_response[raw_response.find("["):raw_response.rfind("]")+1]
                extracted = json.loads(json_part)
                valid_data = []
                all_valid = True
                for item in extracted:
                   if isinstance(item, dict) and 'localisation' in item and 'nombre' in item:
                        try: item['nombre'] = int(item['nombre'])
                        except (ValueError, TypeError): item['nombre'] = 0; all_valid = False
                        if 'nombre_seances' in item:
                            try: item['nombre_seances'] = int(item['nombre_seances'])
                            except (ValueError, TypeError):
                                if 'nombre_seances' in item: del item['nombre_seances']
                        valid_data.append(item)
                   else:
                        all_valid = False
                if not all_valid:
                     st.warning("Le JSON extrait manuellement n'a pas le bon format pour tous les éléments.")
                return valid_data, raw_response
            except Exception:
                st.error("Impossible d'interpréter la réponse de l'IA.")
                return [], raw_response
    except openai.APIError as e:
        st.error(f"Erreur OpenAI : {e}")
        return [], raw_response
    except Exception as e:
        st.error(f"Erreur inattendue : {e}")
        return [], raw_response

def geo_localisation(adresse: str):
    """
    Tente de trouver les coordonnées (latitude, longitude) pour une adresse donnée
    en utilisant Nominatim. Affiche les erreurs/warnings directement dans Streamlit.
    Retourne un tuple (lat, lon) ou None si introuvable ou en cas d'erreur.
    """
    corrections = {
        "région parisienne": "Paris, France", "idf": "Paris, France", "île-de-france": "Paris, France", "ile de france": "Paris, France",
        "sud": "Marseille, France", "le sud": "Marseille, France", "paca": "Marseille, France", "provence-alpes-côte d'azur": "Marseille, France",
        "nord": "Lille, France", "le nord": "Lille, France", "hauts-de-france": "Lille, France",
        "bretagne": "Rennes, France", "côte d'azur": "Nice, France",
        "rhône-alpes": "Lyon, France", "auvergne-rhône-alpes": "Lyon, France",
        "aquitaine": "Bordeaux, France", "nouvelle-aquitaine": "Bordeaux, France",
        "alsace": "Strasbourg, France", "grand est": "Strasbourg, France",
        "france": "Paris, France", "territoire français": "Paris, France",
        "ouest": "Nantes, France", "normandie": "Rouen, France",
        "centre": "Orléans, France", "centre-val de loire": "Orléans, France",
        "auvergne": "Clermont-Ferrand, France"
    }
    adresse_norm = adresse.lower().strip()
    adresse_corrigee = corrections.get(adresse_norm, adresse)
    if ", france" not in adresse_corrigee.lower():
        adresse_requete = f"{adresse_corrigee}, France"
    else:
        adresse_requete = adresse_corrigee
    try:
        loc = geolocator.geocode(adresse_requete)
        if loc:
            return (loc.latitude, loc.longitude)
        else:
            st.warning(f"⚠️ Adresse '{adresse_requete}' (issue de '{adresse}') non trouvée par le service de géolocalisation.")
            return None
    except (GeocoderTimedOut, GeocoderUnavailable) as e:
        st.error(f"❌ Erreur de géocodage (timeout/indisponible) pour '{adresse_requete}': {e}")
        return None
    except Exception as e:
        st.error(f"❌ Erreur inattendue lors du géocodage de '{adresse_requete}': {e}")
        return None

def trouver_cinemas_proches(localisation_cible: str, spectateurs_voulus: int, nombre_de_salles_voulues: int, rayon_km: int = 50, priorite_grandes_salles: bool = False):
    """
    Trouve des cinémas proches d'une localisation cible, pour un nombre EXACT de salles.
    Affiche les warnings/infos directement dans Streamlit.
    Retourne list: Liste des salles sélectionnées.
    """
    point_central_coords = geo_localisation(localisation_cible)
    if not point_central_coords:
        return []

    salles_eligibles = []
    for cinema in cinemas_data:
        lat, lon = cinema.get('lat'), cinema.get('lon')
        if lat is None or lon is None: continue
        try:
            distance = geodesic(point_central_coords, (lat, lon)).km
        except Exception as e:
            st.warning(f"⚠️ Erreur calcul distance pour {cinema.get('cinema', 'Inconnu')} : {e}")
            continue
        if distance > rayon_km: continue
        salles = cinema.get("salles", [])
        # Ne garder que les meilleures salles (par capacité décroissante)
        salles_valides = []
        for s in salles:
            try:
                capacite = int(s.get("capacite", 0))
                if capacite > 0:
                    s["capacite"] = capacite
                    salles_valides.append(s)
            except (ValueError, TypeError):
                continue

        # Tri et limitation à 1 salle max par cinéma
        salles = sorted(salles_valides, key=lambda s: s["capacite"], reverse=True)[:1]
        for salle in salles:
            try: capacite = int(salle.get("capacite", 0))
            except (ValueError, TypeError): continue
            if capacite <= 0: continue # Ignore salles capacité nulle
            salles_eligibles.append({
                "cinema": cinema.get("cinema"), "salle": salle.get("salle"),
                "adresse": cinema.get("adresse"), "lat": lat, "lon": lon,
                "capacite": capacite, "distance_km": round(distance, 2),
                "contact": cinema.get("contact", {}),
                "source_localisation": localisation_cible
            })

    if not salles_eligibles:
        st.warning(f"Aucune salle trouvée pour '{localisation_cible}' dans un rayon de {rayon_km} km.")
        return []

    # Si priorité aux grandes salles, on trie uniquement par capacité
    if priorite_grandes_salles:
        salles_eligibles.sort(key=lambda x: -x["capacite"])
    else:
        # Sinon on trie par distance puis capacité
        salles_eligibles.sort(key=lambda x: (x["distance_km"], -x["capacite"]))

    if len(salles_eligibles) < nombre_de_salles_voulues:
         st.warning(f"⚠️ Seulement {len(salles_eligibles)} salle(s) trouvée(s) pour '{localisation_cible}' (au lieu de {nombre_de_salles_voulues} demandées).")
         resultats = salles_eligibles
    else:
        resultats = salles_eligibles[:nombre_de_salles_voulues]

    return resultats

def generer_carte_folium(groupes_de_cinemas: list):
    """
    Crée une carte Folium affichant les cinémas trouvés, regroupés par couleur.
    Retourne folium.Map or None.
    """
    tous_les_cinemas = [cinema for groupe in groupes_de_cinemas for cinema in groupe.get("resultats", [])]
    if not tous_les_cinemas: return None

    avg_lat = sum(c['lat'] for c in tous_les_cinemas) / len(tous_les_cinemas)
    avg_lon = sum(c['lon'] for c in tous_les_cinemas) / len(tous_les_cinemas)
    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=6, tiles="CartoDB positron")
    couleurs = ["blue", "green", "red", "purple", "orange", "darkred", "lightred", "beige", "darkblue", "darkgreen", "cadetblue", "lightgray", "black"]

    for idx, groupe in enumerate(groupes_de_cinemas):
        couleur = couleurs[idx % len(couleurs)]
        localisation_origine = groupe.get("localisation", "Inconnue")
        resultats_groupe = groupe.get("resultats", [])
        if resultats_groupe:
            feature_group = folium.FeatureGroup(name=f"{localisation_origine} ({len(resultats_groupe)} salles)")
            for cinema in resultats_groupe:
                contact = cinema.get("contact", {})
                contact_nom, contact_email = contact.get("nom", "N/A"), contact.get("email", "N/A")
                cinema["contact_nom"], cinema["contact_email"] = contact_nom, contact_email # Pour table
                popup_html = (f"<b>{cinema.get('cinema', 'N/A')} - Salle {cinema.get('salle', 'N/A')}</b><br>"
                              f"<i>{cinema.get('adresse', 'N/A')}</i><br>"
                              f"Capacité : {cinema.get('capacite', 'N/A')} places<br>"
                              f"Distance ({localisation_origine}) : {cinema.get('distance_km', 'N/A')} km<br>"
                              f"Contact : <b>{contact_nom}</b><br>📧 {contact_email}")
                folium.CircleMarker(
                    location=[cinema['lat'], cinema['lon']], radius=5, color=couleur,
                    fill=True, fill_color=couleur, fill_opacity=0.7,
                    popup=folium.Popup(popup_html, max_width=300)
                ).add_to(feature_group)
            feature_group.add_to(m)
    folium.LayerControl().add_to(m)
    return m

def analyser_contexte_geographique(description_projet: str):
    """
    Analyse le contexte du projet pour suggérer les régions les plus pertinentes
    en fonction du public cible, du thème du film, etc.
    Retourne un dictionnaire avec les régions suggérées et leur justification.
    """
    system_prompt = (
        "Tu es un expert en distribution cinématographique et en analyse démographique en France.\n\n"
        "🎯 Ton objectif : analyser le contexte d'un projet cinématographique pour suggérer les régions les plus pertinentes.\n\n"
        "Considère les facteurs suivants :\n"
        "1. Public cible (âge, centres d'intérêt)\n"
        "2. Thème du film\n"
        "3. Type d'événement (avant-première, test, etc.)\n"
        "4. Contexte local (activités, industries, centres d'intérêt)\n\n"
        "Tu DOIS retourner un JSON valide avec EXACTEMENT cette structure :\n"
        "{\n"
        '  "regions": ["région1", "région2", ...],\n'
        '  "justification": "explication détaillée",\n'
        '  "public_cible": "description du public",\n'
        '  "facteurs_cles": ["facteur1", "facteur2", ...]\n'
        "}\n\n"
        "⚠️ IMPORTANT :\n"
        "- Utilise UNIQUEMENT des guillemets doubles pour les chaînes\n"
        "- Ne mets AUCUN texte avant ou après le JSON\n"
        "- Assure-toi que le JSON est valide et complet\n"
        "- Inclus TOUS les champs demandés\n"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": description_projet}
            ],
            response_format={"type": "json_object"}  # Force la réponse en JSON
        )
        
        # Récupérer la réponse et s'assurer qu'elle est un JSON valide
        raw_response = response.choices[0].message.content.strip()
        
        try:
            data = json.loads(raw_response)
            
            # Vérifier que tous les champs requis sont présents
            required_fields = ["regions", "justification", "public_cible", "facteurs_cles"]
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                st.error(f"La réponse de l'IA manque des champs requis : {', '.join(missing_fields)}")
                return None
                
            # Vérifier que les types sont corrects
            if not isinstance(data["regions"], list):
                data["regions"] = [data["regions"]]
            if not isinstance(data["facteurs_cles"], list):
                data["facteurs_cles"] = [data["facteurs_cles"]]
                
            return data
            
        except json.JSONDecodeError as e:
            st.error(f"La réponse de l'IA n'est pas un JSON valide : {str(e)}")
            st.error(f"Réponse brute : {raw_response}")
            return None
            
    except Exception as e:
        st.error(f"Erreur lors de l'analyse du contexte : {str(e)}")
        return None

# --- Interface Utilisateur Streamlit ---
st.title("🗺️ Assistant de Planification Cinéma MK2")
st.markdown("Décrivez votre projet de diffusion et l'IA identifiera les cinémas pertinents en France.")

if cinemas_ignored_info:
    st.info(f"ℹ️ {cinemas_ignored_info}")

with st.expander("ℹ️ Comment ça marche ?"):
    st.markdown("""
    Cette application vous aide à planifier des projections de films en identifiant les cinémas les plus adaptés en France.
    ### 📝 1. Décrivez votre projet
    Indiquez votre projet en détail : thème du film, public cible, type d'événement, etc.
    *Exemples :*
    - "Film sur l'automobile par Inoxtag, public jeune"
    - "Documentaire sur l'agriculture bio, public adulte"
    - "Film d'animation pour enfants"
    ### 🎯 2. Analyse du contexte
    L'IA analyse votre projet pour suggérer les régions les plus pertinentes en fonction du public cible et du thème.
    ### 🤖 3. Planification détaillée
    Précisez ensuite votre besoin en langage naturel : lieux, type d'événement et public cible.
    ### 🔍 4. Recherche de cinémas
    Le système cherche les salles adaptées dans les régions suggérées.
    ### 🗺️ 5. Carte interactive
    Une carte Folium affiche les cinémas trouvés.
    ### 📊 6. Liste des Salles et Export
    - Tableau récapitulatif des salles
    - Export Excel disponible
    """)

# Initialisation des variables de session
if 'contexte_analyse' not in st.session_state:
    st.session_state.contexte_analyse = None
if 'description_projet' not in st.session_state:
    st.session_state.description_projet = ""

# Première étape : Analyse du contexte
st.subheader("🎯 Analyse du Contexte")
description_projet = st.text_area(
    "Décrivez votre projet :",
    placeholder="Ex: Film sur l'automobile par Inoxtag, public jeune, avant-première",
    value=st.session_state.description_projet
)

# Mettre à jour la description du projet dans la session
if description_projet != st.session_state.description_projet:
    st.session_state.description_projet = description_projet
    st.session_state.contexte_analyse = None

# Lancer l'analyse uniquement si nécessaire
if description_projet and st.session_state.contexte_analyse is None:
    with st.spinner("🧠 Analyse du contexte par l'IA..."):
        st.session_state.contexte_analyse = analyser_contexte_geographique(description_projet)

# Afficher les résultats de l'analyse si disponibles
if st.session_state.contexte_analyse:
    st.success("✅ Analyse du contexte terminée !")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📊 Public cible identifié :**")
        st.info(st.session_state.contexte_analyse.get("public_cible", "Non spécifié"))
        
        st.markdown("**🎯 Facteurs clés :**")
        for facteur in st.session_state.contexte_analyse.get("facteurs_cles", []):
            st.markdown(f"- {facteur}")
    
    with col2:
        st.markdown("**🗺️ Régions suggérées :**")
        for region in st.session_state.contexte_analyse.get("regions", []):
            st.markdown(f"- {region}")
        
        st.markdown("**💡 Justification :**")
        st.info(st.session_state.contexte_analyse.get("justification", "Non spécifié"))
    
    st.markdown("---")
    st.subheader("📝 Planification détaillée")
    st.info("Maintenant que nous avons identifié les régions pertinentes, détaillez votre plan de diffusion.")

# Deuxième étape : Planification détaillée
query = st.text_input(
    "Votre plan de diffusion :",
    placeholder="Ex: 5 séances à Paris (500 pers.) et 2 séances test à Rennes (100 pers.)"
)

if query:
    with st.spinner("🧠 Interprétation de votre requête par l'IA..."):
        instructions_ia, reponse_brute_ia = analyser_requete_ia(query)

    if not instructions_ia:
        st.warning("L'IA n'a pas pu interpréter votre demande ou n'a trouvé aucune intention valide. Essayez de reformuler.")
        if reponse_brute_ia:
             with st.expander("Réponse brute de l'IA (pour débogage)"):
                 st.code(reponse_brute_ia, language="text")
    else:
        total_spectateurs_estimes = sum(i.get('nombre', 0) for i in instructions_ia)
        total_seances_demandees_ia = sum(i.get("nombre_seances", 0) for i in instructions_ia if "nombre_seances" in i)
        nb_zones = len(instructions_ia)

        # Modifié ici : expanded=False pour que l'expander soit fermé par défaut
        with st.expander("🤖 Résumé de la compréhension de l'IA", expanded=False):
            resume_text = f"**IA a compris :** {nb_zones} zone(s) de recherche"
            if total_spectateurs_estimes > 0: resume_text += f" pour un objectif total d'environ {total_spectateurs_estimes} spectateurs"
            if total_seances_demandees_ia > 0: resume_text += f" et un total de {total_seances_demandees_ia} séance(s) explicitement demandée(s)."
            else: resume_text += "."; st.caption("(Aucun nombre de séances spécifique n'a été détecté, une estimation sera faite.)")
            st.info(resume_text)
            st.json(instructions_ia)
            if reponse_brute_ia:
                with st.popover("Voir réponse brute de l'IA"):
                    st.code(reponse_brute_ia, language="text")

        liste_groupes_resultats = []
        cinemas_trouves_total = 0
        total_seances_estimees_ou_demandees = 0
        rayons_par_loc = {}

        st.sidebar.header("⚙️ Options de Recherche")
        for idx, instruction in enumerate(instructions_ia):
            loc = instruction.get('localisation')
            if loc:
                 corrections_regionales = ["paris", "lille", "marseille", "toulouse", "nice", "nantes", "rennes", "strasbourg", "clermont-ferrand", "lyon", "bordeaux", "rouen", "orléans"]
                 is_large_area_target = loc.lower() in ["marseille", "toulouse", "nice", "lille", "nantes", "rennes", "strasbourg", "clermont-ferrand", "lyon", "bordeaux"] or loc.lower() in ["paris"] and len(instructions_ia) > 1
                 default_rayon = 100 if is_large_area_target else 50
                 rayon_key = f"rayon_{idx}_{loc}"
                 if is_large_area_target: st.sidebar.caption(f"'{loc}' peut couvrir une zone large, rayon par défaut ajusté.")
                 rayons_par_loc[loc] = st.sidebar.slider(f"Rayon autour de '{loc}' (km)", 5, 250, default_rayon, 5, key=rayon_key)

        st.markdown("---")
        st.subheader("🔍 Recherche des cinémas...")
        dataframes_to_export = {}
        with st.spinner(f"Recherche en cours pour {nb_zones} zone(s)..."):
            for instruction in instructions_ia:
                loc = instruction.get('localisation')
                num_spectateurs = instruction.get('nombre')
                priorite_grandes_salles = instruction.get('priorite_grandes_salles', False)
                if loc and isinstance(num_spectateurs, int) and num_spectateurs >= 0:
                    st.write(f"**Recherche pour : {loc}**")
                    rayon_recherche = rayons_par_loc.get(loc, 50)
                    if "nombre_seances" in instruction and isinstance(instruction["nombre_seances"], int) and instruction["nombre_seances"] > 0:
                        nombre_salles_a_trouver = instruction["nombre_seances"]
                        if priorite_grandes_salles:
                            st.info(f"   -> Objectif : trouver les {nombre_salles_a_trouver} plus grandes salles dans {rayon_recherche} km.")
                        else:
                            st.info(f"   -> Objectif : trouver {nombre_salles_a_trouver} salle(s) dans {rayon_recherche} km (cible: {num_spectateurs} spect.).")
                    else:
                        nombre_salles_a_trouver = 1
                        if priorite_grandes_salles:
                            st.info(f"   -> Objectif : trouver la plus grande salle dans {rayon_recherche} km.")
                        else:
                            st.info(f"   -> Objectif : trouver {nombre_salles_a_trouver} salle (défaut) dans {rayon_recherche} km (cible: {num_spectateurs} spect.).")
                    total_seances_estimees_ou_demandees += nombre_salles_a_trouver
                    resultats_cinemas = trouver_cinemas_proches(loc, num_spectateurs, nombre_salles_a_trouver, rayon_recherche, priorite_grandes_salles)
                    groupe_actuel = {"localisation": loc, "resultats": resultats_cinemas, "nombre_salles_demandees": nombre_salles_a_trouver}
                    liste_groupes_resultats.append(groupe_actuel)
                    if resultats_cinemas:
                        capacite_trouvee = sum(c['capacite'] for c in resultats_cinemas)
                        st.write(f"   -> Trouvé {len(resultats_cinemas)} salle(s) (Capacité totale: {capacite_trouvee}).")
                        cinemas_trouves_total += len(resultats_cinemas)
                        data_for_df = []
                        for cinema in resultats_cinemas:
                            contact = cinema.get("contact", {})
                            data_for_df.append({
                                "Cinéma": cinema.get("cinema", "N/A"), 
                                "Salle": cinema.get("salle", "N/A"),
                                "Adresse": cinema.get("adresse", "N/A"), 
                                "Capacité": cinema.get("capacite", 0),
                                "Distance (km)": cinema.get("distance_km", 0), 
                                # Remplacer les deux colonnes par une seule avec les informations combinées
                                "Contact": " / ".join(filter(None, [
                                    contact.get("nom", ""), 
                                    contact.get("email", ""), 
                                    contact.get("telephone", "")
                                ])),
                                "Latitude": cinema.get("lat", 0.0),
                                "Longitude": cinema.get("lon", 0.0) 
                            })
                        df = pd.DataFrame(data_for_df)
                        if not df.empty: dataframes_to_export[loc] = df
                    else: st.write(f"   -> Aucune salle trouvée pour '{loc}' correspondant aux critères.")
                else: st.warning(f"Instruction IA ignorée (format invalide) : {instruction}")

        st.markdown("---")
        st.subheader("📊 Résultats de la Recherche")
        salles_manquantes = total_seances_estimees_ou_demandees - cinemas_trouves_total
        if cinemas_trouves_total > 0:
            if salles_manquantes > 0: st.warning(f"⚠️ Recherche terminée. {cinemas_trouves_total} salle(s) trouvée(s), mais il en manque {salles_manquantes} sur les {total_seances_estimees_ou_demandees} visée(s).")
            else: st.success(f"✅ Recherche terminée ! {cinemas_trouves_total} salle(s) trouvée(s), correspondant aux {total_seances_estimees_ou_demandees} séance(s) visée(s).")

            st.subheader("🗺️ Carte des Cinémas Trouvés")
            carte = generer_carte_folium(liste_groupes_resultats)
            if carte:
                map_html_path = "map_output.html"
                carte.save(map_html_path)
                st_folium(carte, width='100%', height=500)
                with open(map_html_path, "rb") as f:
                    st.download_button("📥 Télécharger la Carte Interactive (HTML)", f, "carte_cinemas.html", "text/html", use_container_width=True)
                with st.expander("💡 Comment utiliser le fichier HTML ?"):
                      st.markdown("- Double-cliquez sur `carte_cinemas.html`.\n- S'ouvre dans votre navigateur.\n- Carte interactive: zoom, déplacement, clic sur points.\n- Contrôle des couches pour filtrer par zone.\n- Fonctionne hors ligne.")
            else: st.info("Génération de la carte annulée.")

            st.markdown("---")
            st.subheader("📋 Liste des Salles et Export")

            if dataframes_to_export:
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                    for loc, df_to_write in dataframes_to_export.items():
                        safe_sheet_name = "".join(c for c in loc if c.isalnum() or c in (' ', '_')).rstrip()[:31]
                        df_to_write.to_excel(writer, sheet_name=safe_sheet_name, index=False)
                st.download_button(
                    label="💾 Télécharger Tous les Résultats (Excel)",
                    data=excel_buffer.getvalue(),
                    file_name=f"resultats_cinemas_{uuid.uuid4()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True, key="download_all_excel" )

            for groupe in liste_groupes_resultats:
                loc = groupe["localisation"]
                nb_demandes = groupe["nombre_salles_demandees"]
                nb_trouves = len(groupe["resultats"])
                st.markdown(f"**Zone : {loc}** ({nb_trouves}/{nb_demandes} salles trouvées)")
                if loc in dataframes_to_export:
                    df_display = dataframes_to_export[loc]
                    st.dataframe(df_display[["Cinéma", "Salle", "Capacité", "Distance (km)", "Contact"]], use_container_width=True, hide_index=True)
                elif nb_trouves == 0 : st.caption("Aucune salle trouvée pour cette zone.")
                st.divider()
        else:
             st.error("❌ Aucun cinéma correspondant à votre demande n'a été trouvé.")
             if salles_manquantes > 0: st.info(f"(L'objectif était de trouver {total_seances_estimees_ou_demandees} salle(s).)")

# --- Fin de l'application ---