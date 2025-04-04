# --- ai.py ---
# Application Streamlit pour aider à planifier des projections de films
# [...] (garde les autres commentaires initiaux si tu veux)

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
import pandas # Ajouté pour st.dataframe

# --- CONFIGURATION DE LA PAGE (DOIT ÊTRE LA PREMIÈRE COMMANDE STREAMLIT) ---
st.set_page_config(layout="wide", page_title="Assistant Cinéma MK2", page_icon="🗺️") # Utilise toute la largeur, ajoute un titre/icône d'onglet

# --- Configuration (Variables globales) ---
# Nom du fichier JSON contenant les cinémas AVEC leurs coordonnées pré-calculées
GEOCATED_CINEMAS_FILE = "cinemas_groupedBig.json"
# User agent pour le service de géocodage (utilisé seulement pour les localisations demandées par l'utilisateur)
GEOCODER_USER_AGENT = "CinemaMapApp/1.0 (App)"
# Timeout pour le géocodage des localisations demandées
GEOCODER_TIMEOUT = 10

# --- Initialisation du client OpenAI ---
# Assure-toi que la variable d'environnement OPENAI_API_KEY est définie
try:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    # Test rapide pour voir si la clé est au moins présente (ne valide pas la clé elle-même)
    if not client.api_key:
        # Utilise st.error MAINTENANT que set_page_config est appelée avant
        st.error("La clé API OpenAI n'a pas été trouvée. Veuillez définir la variable d'environnement OPENAI_API_KEY.")
        st.stop() # Arrête l'exécution si la clé manque
except Exception as e:
    st.error(f"Erreur lors de l'initialisation du client OpenAI : {e}")
    st.stop()

# --- Chargement des données des cinémas pré-géocodées ---
try:
    with open(GEOCATED_CINEMAS_FILE, "r", encoding="utf-8") as f:
        cinemas_data = json.load(f)
    # Filtre optionnel : ne garde que les cinémas qui ont des coordonnées valides
    original_count = len(cinemas_data)
    cinemas_data = [c for c in cinemas_data if c.get('lat') is not None and c.get('lon') is not None]
    valid_count = len(cinemas_data)
    if original_count > valid_count:
        st.sidebar.info(f"{original_count - valid_count} cinémas sans coordonnées valides ont été ignorés.")

except FileNotFoundError:
    st.error(f"ERREUR : Le fichier de données '{GEOCATED_CINEMAS_FILE}' est introuvable.")
    st.error("Veuillez exécuter le script 'preprocess_cinemas.py' pour générer ce fichier.")
    st.stop() # Arrête l'exécution de l'application si le fichier de données manque
except json.JSONDecodeError:
    st.error(f"ERREUR : Le fichier de données '{GEOCATED_CINEMAS_FILE}' contient un JSON invalide.")
    st.stop()
except Exception as e:
    st.error(f"Erreur inattendue lors du chargement des données des cinémas : {e}")
    st.stop()

# --- Initialisation du Géocodeur (pour les requêtes utilisateur) ---
geolocator = Nominatim(user_agent=GEOCODER_USER_AGENT, timeout=GEOCODER_TIMEOUT)

# --- Fonctions ---

# Fonction pour analyser la requête utilisateur avec OpenAI (GPT-4o)
# Utilise le cache de Streamlit pour éviter de refaire les appels API pour la même requête
@st.cache_data(show_spinner=False) # show_spinner=False car on a notre propre spinner
def analyser_requete_ia(question: str):
    """
    Interprète la requête de l'utilisateur en utilisant GPT-4o pour extraire
    les localisations et le nombre de spectateurs cible.
    Retourne une liste de dictionnaires ou une liste vide en cas d'échec.
    """
    # Prompt système détaillé pour guider l'IA
    system_prompt = (
        "Tu es un expert en distribution cinématographique en France. "
        "L'utilisateur te confie un projet de diffusion en salle (test, avant-première, lancement, tournée, etc.). "
        "Ta mission est de transformer ce besoin en une liste JSON claire de villes cibles et de jauges spectateurs, pour construire un plan de sortie réaliste. "

        "Voici les règles à suivre :\n\n"

        "1️⃣ Chaque intention doit devenir un dictionnaire JSON avec deux clés :\n"
        "   - 'localisation' : une ville (pas une région, sauf cas particulier),\n"
        "   - 'nombre' : un nombre entier de spectateurs à atteindre.\n\n"
        "   - 'nombre_seances' : quand l'utilisateur spécifie un nombre de séances ou salles souhaité.\n\n"

        "2️⃣ Si l'utilisateur parle de régions vagues (région, zone géographique, tout le pays...), tu dois automatiquement les convertir en **villes représentatives**, selon ce mapping :\n"
        "   - 'région parisienne', 'idf', 'île-de-france' → ['Paris']\n"
        "   - 'sud', 'sud de la France', 'paca', 'provence' → ['Marseille', 'Toulouse', 'Nice']\n"
        "   - 'nord', 'hauts-de-france' → ['Lille']\n"
        "   - 'ouest', 'bretagne', 'normandie' → ['Nantes', 'Rennes']\n"
        "   - 'est', 'grand est', 'alsace' → ['Strasbourg']\n"
        "   - 'centre', 'centre-val de loire', 'auvergne' → ['Clermont-Ferrand']\n"
        "   - 'France entière', 'toute la France', 'province', 'le territoire', 'le reste du territoire français' → ['Lyon', 'Marseille', 'Lille', 'Bordeaux', 'Strasbourg']\n\n"

        "3️⃣ Si une **quantité globale** est donnée pour une zone, répartis-la équitablement entre les salles de cinéma (ATTENTION 1 salle = 1 séance !) de cette Zone dont la capacité total sera égale a la quantité global\n"
        "   Par exemple : '3000 spectateurs dans le reste du territoire' → 3000 spéctateur au total repartis dans chaque ville choisie (5 villes) le plus équitablement possible.\n"
        "   Tu peux ajuster légèrement les répartitions si le total n'est pas divisible parfaitement.\n\n"
        "   ATTENTION : Jamais plus de 500 séances"
        
        "8️⃣ Nouvelle règle IMPORTANTE: Si l'utilisateur précise un nombre de séances ou de salles (ex: '15 séances dans toute la France'), tu dois extraire cette information dans le champ 'nombre_seances' pour chaque localisation. Tu dois distribuer ce nombre entre les localisations si elles sont multiples. Par exemple, pour '15 séances pour un total de 8000 personnes dans toute la France', tu dois répartir les 15 séances entre les villes représentatives de la France et les 8000 personnes entre ces séances."

        "4️⃣ Si un lieu est donné **sans nombre précis**, déduis une estimation raisonnable en fonction du contexte :\n"
        "   - 'petite salle', 'séance test' → 50 à 100\n"
        "   - 'avant-première' → 200 à 400\n"
        "   - 'grande salle', 'grande ville' → 500 à 1000\n"
        "   - 'province' → 100 à 300\n"
        "   - 'cinéma art et essai' → 100 à 150\n\n"

        "5️⃣ Si le texte contient plusieurs zones ou intentions, tu dois retourner une liste de toutes les intentions séparées.\n"
        "   Exemple : '300 à Paris, 100 à Lyon et test en Bretagne' → ['Paris', 300], ['Lyon', 100], ['Rennes', 100]\n\n"

        "6️⃣ Le résultat DOIT être une **liste JSON pure**, sans explication, sans texte avant ou après. "
        "Juste : [ {{...}}, {{...}} ]\n\n"

        "7️⃣ Si aucun lieu ni objectif n’est identifiable, retourne simplement : []"
    )

    try:
        # Appel à l'API OpenAI ChatCompletion (sans forcer le format JSON strict)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ]
        )

        # Récupère la réponse textuelle brute
        text_response = response.choices[0].message.content.strip()

        # Affiche dans la sidebar pour débogage
        st.sidebar.write("Réponse brute de l'IA :")
        st.sidebar.code(text_response, language="json")

        # Tente de parser la réponse en JSON (souple)
        try:
            data = json.loads(text_response)

            # Si la réponse contient un message d’erreur (ex : JSON forcé)
            if isinstance(data, dict) and "message" in data:
                st.warning(f"⚠️ L'IA a répondu : {data['message']}")
                return []

            # ✅ Cas spécial : un seul objet, on l'encapsule
            if isinstance(data, dict) and 'localisation' in data and 'nombre' in data:
                localisation = str(data['localisation']).strip()
                try:
                    nombre = int(data['nombre'])
                except ValueError:
                    nombre = 0
                return [{"localisation": localisation, "nombre": nombre}]

            # ✅ Cas classique : une liste d’intentions
            elif isinstance(data, list):
                if all(isinstance(item, dict) and 'localisation' in item and 'nombre' in item for item in data):
                    return data
                else:
                    st.warning("L'IA a retourné une liste JSON, mais les éléments n'ont pas le bon format.")
                    return []

            # ✅ Cas enveloppé dans un objet avec des clés
            elif isinstance(data, dict):
                potential_keys = ['resultats', 'projections', 'locations', 'intentions', 'data', 'result']
                for key in potential_keys:
                    if key in data and isinstance(data[key], list):
                        extracted = data[key]
                        if all(isinstance(item, dict) and 'localisation' in item and 'nombre' in item for item in extracted):
                            return extracted
                st.warning("L'IA a retourné un objet, mais aucune structure attendue n'a été trouvée.")
                return []

            else:
                st.warning("La réponse n'est ni une liste ni un dictionnaire exploitable.")
                return []

        except json.JSONDecodeError:
            st.warning("La réponse n'était pas un JSON valide, tentative d'extraction manuelle...")
            try:
                json_part = text_response[text_response.find("["):text_response.rfind("]")+1]
                extracted = json.loads(json_part)
                if all(isinstance(item, dict) and 'localisation' in item and 'nombre' in item for item in extracted):
                    return extracted
                else:
                    st.warning("Le JSON extrait manuellement n’a pas le bon format.")
                    return []
            except Exception:
                st.error("Impossible d’interpréter la réponse de l’IA.")
                return []

    except openai.APIError as e:
        st.error(f"Erreur OpenAI : {e}")
        return []
    except Exception as e:
        st.error(f"Erreur inattendue : {e}")
        return []

# Fonction pour géocoder une adresse (utilisée pour la localisation CIBLE de l'utilisateur)
def geo_localisation(adresse: str):
    """
    Tente de trouver les coordonnées (latitude, longitude) pour une adresse donnée
    en utilisant Nominatim. Gère quelques corrections courantes pour les régions françaises.
    Retourne un tuple (lat, lon) ou None si introuvable ou en cas d'erreur.
    """
    # Dictionnaire de corrections pour les termes vagues ou régionaux
    # On les mappe vers des villes spécifiques pour le géocodage
    corrections = {
        "région parisienne": "Paris, France",
        "idf": "Paris, France",
        "île-de-france": "Paris, France",
        "ile de france": "Paris, France",
        "sud": "Marseille, France",
        "le sud": "Marseille, France",
        "paca": "Marseille, France",
        "provence-alpes-côte d'azur": "Marseille, France",
        "nord": "Lille, France",
        "le nord": "Lille, France",
        "hauts-de-france": "Lille, France",
        "bretagne": "Rennes, France",
        "côte d'azur": "Nice, France",
        "rhône-alpes": "Lyon, France",
        "auvergne-rhône-alpes": "Lyon, France",
        "aquitaine": "Bordeaux, France",
        "nouvelle-aquitaine": "Bordeaux, France",
        "alsace": "Strasbourg, France",
        "grand est": "Strasbourg, France",
        # On peut considérer "France entière" comme Paris par défaut
        "france": "Paris, France",
        "territoire français": "Paris, France",
    }

    # Normalise l'adresse (minuscules, sans espaces superflus)
    adresse_norm = adresse.lower().strip()
    # Applique une correction si l'adresse normalisée est dans le dictionnaire
    adresse_corrigee = corrections.get(adresse_norm, adresse) # Utilise l'adresse originale si pas de correction

    # S'assure que ", France" est ajouté pour aider Nominatim, sauf si c'est déjà là
    if ", france" not in adresse_corrigee.lower():
        adresse_requete = f"{adresse_corrigee}, France"
    else:
        adresse_requete = adresse_corrigee

    # Affiche l'adresse utilisée pour le géocodage (utile pour le débogage)
    st.sidebar.write(f"Géocodage du point central pour '{adresse}' -> Requête: '{adresse_requete}'")

    try:
        # Appel au service Nominatim
        loc = geolocator.geocode(adresse_requete) # Utilise le timeout défini lors de l'initialisation
        if loc:
            st.sidebar.write(f"  -> Coordonnées trouvées : ({loc.latitude:.4f}, {loc.longitude:.4f})")
            return (loc.latitude, loc.longitude)
        else:
            st.sidebar.warning(f"  -> Adresse '{adresse_requete}' non trouvée par Nominatim.")
            return None
    except (GeocoderTimedOut, GeocoderUnavailable) as e:
        # Gère les erreurs spécifiques de Geopy
        st.sidebar.error(f"Erreur de géocodage pour '{adresse_requete}': {e}")
        return None
    except Exception as e:
        # Gère les autres erreurs potentielles
        st.sidebar.error(f"Erreur inattendue lors du géocodage de '{adresse_requete}': {e}")
        return None

# Fonction pour trouver les cinémas proches et ayant une capacité suffisante
# Utilise maintenant les coordonnées pré-calculées des cinémas
def trouver_cinemas_proches(localisation_cible: str, spectateurs_voulus: int, nombre_de_salles_voulues: int, rayon_km: int = 50):
    """
    Trouve des cinémas proches d'une localisation cible, avec une capacité adaptée au nombre de spectateurs voulus.
    Respecte strictement le nombre de salles demandées, quitte à élargir les critères.
    
    Args:
        localisation_cible (str): Ville ou région où chercher
        spectateurs_voulus (int): Nombre total de spectateurs cible
        nombre_de_salles_voulues (int): Nombre EXACT de salles à trouver
        rayon_km (int): Rayon de recherche en kilomètres
        
    Returns:
        list: Liste des salles sélectionnées
    """
    point_central_coords = geo_localisation(localisation_cible)
    if not point_central_coords:
        st.warning(f"Impossible de trouver des cinémas car la localisation centrale '{localisation_cible}' n'a pas pu être géocodée.")
        return []

    resultats = []
    capacite_cumulee = 0
    
    # Liste temporaire de toutes les salles avec leurs infos
    salles_eligibles = []

    for cinema in cinemas_data:
        lat = cinema.get('lat')
        lon = cinema.get('lon')
        if lat is None or lon is None:
            continue

        try:
            distance = geodesic(point_central_coords, (lat, lon)).km
        except Exception as e:
            st.sidebar.warning(f"Erreur de distance pour {cinema.get('cinema')} : {e}")
            continue

        if distance > rayon_km:
            continue

        for salle in cinema.get("salles", []):
            try:
                capacite = int(salle.get("capacite", 0))
            except (ValueError, TypeError):
                continue

            if capacite <= 0 or capacite < 66:  # On ignore les salles trop petites
                continue

            salles_eligibles.append({
                "cinema": cinema.get("cinema"),
                "salle": salle.get("salle"),
                "adresse": cinema.get("adresse"),
                "lat": lat,
                "lon": lon,
                "capacite": capacite,
                "distance_km": round(distance, 2),
                "contact": cinema.get("contact", {}),
                "source_localisation": localisation_cible
            })

    # Si aucune salle n'est trouvée, retourner liste vide
    if not salles_eligibles:
        st.sidebar.warning(f"Aucune salle éligible trouvée pour {localisation_cible} dans un rayon de {rayon_km} km.")
        return []
        
    # Trie les salles par distance ET capacité (priorité à la distance)
    salles_eligibles.sort(key=lambda x: (x["distance_km"], -x["capacite"]))
    
    # PHASE 1 : Essayer d'obtenir exactement le nombre de salles demandées avec la meilleure capacité
    capacite_moyenne_cible = spectateurs_voulus / nombre_de_salles_voulues if nombre_de_salles_voulues > 0 else 0
    
    # Première tentative : prendre les salles les plus proches respectant la capacité moyenne
    for salle in salles_eligibles:
        if len(resultats) < nombre_de_salles_voulues and capacite_cumulee + salle["capacite"] <= spectateurs_voulus:
            resultats.append(salle)
            capacite_cumulee += salle["capacite"]
    
    # PHASE 2 : Si nous n'avons pas assez de salles, relâcher la contrainte de capacité
    if len(resultats) < nombre_de_salles_voulues:
        st.sidebar.info(f"Assouplissement des critères pour {localisation_cible} : seulement {len(resultats)}/{nombre_de_salles_voulues} salles trouvées.")
        
        # Vider la liste des résultats pour recommencer
        resultats = []
        capacite_cumulee = 0
        
        # Prendre les N meilleures salles, même si on dépasse la capacité totale
        for salle in salles_eligibles[:nombre_de_salles_voulues]:
            resultats.append(salle)
            capacite_cumulee += salle["capacite"]
    
    # Si on n'a toujours pas assez de salles, c'est qu'il n'y en a vraiment pas assez dans la base
    if len(resultats) < nombre_de_salles_voulues:
        st.sidebar.warning(f"Impossible de trouver {nombre_de_salles_voulues} salles pour {localisation_cible}. Seulement {len(resultats)} disponibles.")
    
    # Limiter au nombre exact de salles demandées (cas où la phase 2 a pris trop de salles)
    return resultats[:nombre_de_salles_voulues]

# Fonction pour générer la carte Folium
def generer_carte_folium(groupes_de_cinemas: list):
    """
    Crée une carte Folium affichant les cinémas trouvés, regroupés par couleur
    selon la localisation de la requête initiale.

    Args:
        groupes_de_cinemas (list): Une liste où chaque élément est un dictionnaire
                                   contenant la localisation demandée et les résultats (cinémas trouvés).
                                   Ex: [{'localisation': 'Paris', 'resultats': [...]}, {'localisation': 'Lyon', 'resultats': [...]}]

    Returns:
        folium.Map or None: Un objet carte Folium si des cinémas ont été trouvés, sinon None.
    """
    # Récupère tous les cinémas de tous les groupes pour trouver le centre de la carte
    tous_les_cinemas = [cinema for groupe in groupes_de_cinemas for cinema in groupe.get("resultats", [])]

    # S'il n'y a aucun cinéma à afficher, retourne None
    if not tous_les_cinemas:
        return None

    # Calcule le centre géographique moyen de tous les points trouvés pour centrer la carte
    avg_lat = sum(c['lat'] for c in tous_les_cinemas) / len(tous_les_cinemas)
    avg_lon = sum(c['lon'] for c in tous_les_cinemas) / len(tous_les_cinemas)

    # Crée l'objet carte Folium
    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=6, tiles="CartoDB positron")

    # Palette de couleurs pour les groupes
    couleurs = [
        "blue", "green", "red", "purple", "orange", "darkred", "lightred",
        "beige", "darkblue", "darkgreen", "cadetblue", "lightgray", "black"
    ]

    # Ajoute chaque groupe de résultats
    for idx, groupe in enumerate(groupes_de_cinemas):
        couleur = couleurs[idx % len(couleurs)]
        localisation_origine = groupe.get("localisation", "Inconnue")
        resultats_groupe = groupe.get("resultats", [])

        feature_group = folium.FeatureGroup(name=f"{localisation_origine} ({len(resultats_groupe)} cinémas)")

        for cinema in resultats_groupe:
            # Ajout manuel des infos contact pour affichage et table
            contact = cinema.get("contact", {})
            contact_nom = contact.get("nom", "N/A")
            contact_email = contact.get("email", "N/A")
            cinema["contact_nom"] = contact_nom
            cinema["contact_email"] = contact_email

            popup_html = f"""
            <b>{cinema.get('cinema', 'Nom inconnu')}</b><br>
            <i>{cinema['adresse']}</i><br>
            Capacité : {cinema['capacite']} places<br>
            Distance ({localisation_origine}) : {cinema['distance_km']} km<br>
            Contact : <b>{contact_nom}</b><br>
            📧 {contact_email}
            """

            folium.CircleMarker(
                location=[cinema['lat'], cinema['lon']],
                radius=5,
                color=couleur,
                fill=True,
                fill_color=couleur,
                fill_opacity=0.7,
                popup=folium.Popup(popup_html, max_width=300)
            ).add_to(feature_group)

        feature_group.add_to(m)

    folium.LayerControl().add_to(m)

    return m

# --- Interface Utilisateur Streamlit ---
# st.set_page_config(layout="wide") # Utilise toute la largeur de la page
st.title("🗺️ Assistant de Planification Cinéma MK2")
st.markdown("Décrivez votre projet de diffusion et l'IA identifiera les cinémas pertinents en France.")

# Section d'aide dans un expander
with st.expander("ℹ️ Comment ça marche ?"):
    st.markdown("""
    Cette application vous aide à planifier des projections de films en identifiant les cinémas les plus adaptés en France.

    ### 📝 1. Décrivez votre plan
    Dans la zone de texte ci-dessous, indiquez votre besoin en langage naturel : lieux (villes ou régions), type d'événement (test, avant-première, lancement) et public cible (nombre de spectateurs, nombre de séances, etc.).

    *Exemples :*
    - "Je veux tester mon film dans une petite salle à Lyon et faire une avant-première à Paris pour 300 personnes."
    - "15 séances dans toute la France pour atteindre 8000 spectateurs."
    - "Diffusion en Bretagne avec un objectif de 150 spectateurs par ville."

    ### 🤖 2. Analyse par l’IA (GPT-4o)
    L’intelligence artificielle interprète votre demande pour en extraire les localisations cibles, les jauges de spectateurs et les contraintes de séances éventuelles.

    ### 🔍 3. Recherche automatique de cinémas
    Le système explore une base de données de cinémas géolocalisés en France, à la recherche de salles adaptées à votre besoin (proximité, capacité, disponibilité).

    ### 🗺️ 4. Carte interactive
    Une carte Folium affiche les cinémas trouvés. Cliquez sur les points pour voir les détails (adresse, capacité, contact). Vous pouvez filtrer les résultats par zone via le menu en haut à droite de la carte.

    ### 💾 5. Téléchargements disponibles
    - **📍 Carte HTML** : téléchargez une version interactive de la carte pour l’ouvrir ou la partager facilement.  
      👉 *Double-cliquez simplement sur le fichier téléchargé (`carte_cinemas.html`) pour l’ouvrir dans votre navigateur, même sans connexion internet.*

    - **📊 Tableaux Excel ou CSV** : pour chaque zone, vous pouvez exporter la liste des cinémas sélectionnés avec leurs coordonnées, capacités et contacts.
    """)

# Zone de saisie pour la requête utilisateur
query = st.text_input(
    "Votre demande :",
    placeholder="Ex: Lancement à Paris (grand public) et test à Rennes (100 pers.)"
)

# Traitement seulement si l'utilisateur a entré une requête
if query:
    # Affichage d'un message pendant l'analyse par l'IA
    with st.spinner("🧠 Interprétation de votre requête par l'IA..."):
        # Appel à la fonction d'analyse (mise en cache)
        instructions_ia = analyser_requete_ia(query)

    # Vérifie si l'IA a pu extraire des instructions valides
    if not instructions_ia:
        st.warning("L'IA n'a pas pu interpréter votre demande ou n'a trouvé aucune intention de localisation/jauge valide. Essayez de reformuler.")
    else:
        # Affiche un résumé de ce que l'IA a compris
        total_spectateurs_estimes = sum(i.get('nombre', 0) for i in instructions_ia)
        total_seances_voulues = sum(i.get("nombre_seances", 0) for i in instructions_ia)
        with st.expander("🤖 Résumé de la compréhension de l'IA"):
            st.info(f"**IA a compris :** {len(instructions_ia)} zone(s) pour un objectif total de {total_spectateurs_estimes} spectateurs et {total_seances_voulues} séance(s).")
            st.json(instructions_ia)

        # Prépare la liste pour stocker les résultats par groupe de recherche
        liste_groupes_resultats = []
        cinemas_trouves_total = 0

        # Affichage d'un message pendant la recherche des cinémas
        with st.spinner(f"🔍 Recherche des cinémas correspondants..."):
            # Boucle sur chaque instruction (localisation/jauge) retournée par l'IA
            for instruction in instructions_ia:
                loc = instruction.get('localisation')
                num = instruction.get('nombre')

                # Vérifie si l'instruction est valide avant de chercher
                if loc and isinstance(num, int) and num > 0:
                    st.write(f"--- Recherche pour : **{loc}** (capacité min: {num}) ---")
                    # Logique pour adapter automatiquement le rayon si on détecte une région large
                    corrections_regionales = [
                        "nord", "le nord", "hauts-de-france",
                        "sud", "le sud", "paca", "provence-alpes-côte d'azur",
                        "bretagne",
                        "région parisienne", "idf", "île-de-france", "ile de france",
                        "aquitaine", "nouvelle-aquitaine",
                        "alsace", "grand est"
                    ]

                    # Si la localisation est une région large, on élargit automatiquement le rayon
                    if loc.lower() in corrections_regionales:
                        rayon_recherche = 120
                        st.sidebar.info(f"🔁 Localisation régionale détectée ('{loc}'). Rayon élargi automatiquement à {rayon_recherche} km.")
                    else:
                        rayon_recherche = st.sidebar.slider(f"Rayon de recherche autour de {loc} (km)", 5, 200, 50, key=f"rayon_{loc}_{hash(str(instruction))}")

                    # Appel à la fonction de recherche de cinémas
                    if "nombre_seances" in instruction:
                        # Si l'IA a explicitement extrait un nombre de séances demandé
                        nombre_seances = instruction.get("nombre_seances")
                    else:
                        # Sinon, estimation par défaut (comme avant)
                        if "nombre_seances" in instruction and instruction["nombre_seances"]:
                            nombre_seances = int(instruction["nombre_seances"])
                            st.sidebar.info(f"Nombre de séances explicitement demandé : {nombre_seances}")
                        else:
                            nombre_seances = max(1, round(num / 66))
                            st.sidebar.info(f"Nombre de séances calculé automatiquement : {nombre_seances}")

                        # Et plus bas, ajoutez une information explicite dans l'interface :
                        total_seances_voulues = sum(int(i.get('nombre_seances', 0)) for i in instructions_ia if 'nombre_seances' in i)
                        if total_seances_voulues > 0:
                            st.info(f"🤖 **IA a compris :** {len(instructions_ia)} zone(s) de recherche pour un objectif total estimé à {total_spectateurs_estimes} spectateurs et {total_seances_voulues} séances.")
                        else:
                            st.info(f"🤖 **IA a compris :** {len(instructions_ia)} zone(s) de recherche pour un objectif total estimé à {total_spectateurs_estimes} spectateurs.")

                        # Et enfin, lors de l'affichage du résultat final, ajoutez cette vérification
                        total_seances_trouvees = sum(len(groupe["resultats"]) for groupe in liste_groupes_resultats)
                        seances_manquantes = total_seances_voulues - total_seances_trouvees if total_seances_voulues > 0 else 0

                        if cinemas_trouves_total > 0:
                            if seances_manquantes > 0:
                                st.warning(f"⚠️ Attention : {seances_manquantes} séances n'ont pas pu être trouvées sur les {total_seances_voulues} demandées.")
                            else:
                                st.success(f"✅ Recherche terminée ! {cinemas_trouves_total} salles pertinente(s) trouvées au total, correspondant exactement aux {total_seances_voulues} séances demandées.")
                        else:
                            st.error("❌ Aucun cinéma correspondant à votre demande n'a été trouvé dans la base de données selon les critères définis.")

                    st.sidebar.info(f"Recherche de {nombre_seances} salle(s) pour {num} spectateurs à {loc}")
                    resultats_cinemas = trouver_cinemas_proches(
                        loc, 
                        spectateurs_voulus=num, 
                        rayon_km=rayon_recherche, 
                        nombre_de_salles_voulues=nombre_seances
                    )    
                    resultats_cinemas = trouver_cinemas_proches(loc, num, rayon_km=rayon_recherche, nombre_de_salles_voulues=nombre_seances)

                    # Affiche le nombre de cinémas trouvés pour cette instruction
                    if resultats_cinemas:
                        st.write(f"-> Trouvé {len(resultats_cinemas)} cinéma(s) correspondant(s).")
                        # Ajoute les résultats au groupe
                        liste_groupes_resultats.append({
                            "localisation": loc,
                            "resultats": resultats_cinemas
                        })
                        cinemas_trouves_total += len(resultats_cinemas)
                    else:
                        st.write(f"-> Aucun cinéma trouvé pour '{loc}' avec une capacité d'au moins {num} places dans un rayon de {rayon_recherche} km.")
                        # Ajoute un groupe vide pour que la légende de la carte mentionne la recherche
                        liste_groupes_resultats.append({
                            "localisation": loc,
                            "resultats": []
                        })
                else:
                    st.warning(f"Instruction IA ignorée (format invalide) : {instruction}")

        # Génération et affichage de la carte si des cinémas ont été trouvés
        if cinemas_trouves_total > 0:
            st.success(f"✅ Recherche terminée ! {cinemas_trouves_total} salles pertinente(s) trouvé(s) au total.")
            # Génère la carte Folium
            carte = generer_carte_folium(liste_groupes_resultats)

            if carte:
                # Sauvegarde temporaire de la carte en HTML pour le téléchargement
                map_html_path = "map_output.html"
                carte.save(map_html_path)

                # Bouton pour télécharger la carte HTML
                with open(map_html_path, "rb") as f:
                    st.download_button(
                        label="📥 Télécharger la Carte (HTML)",
                        data=f,
                        file_name="carte_cinemas.html",
                        mime="text/html"
                    )
                with st.expander("💡 Comment utiliser ce fichier ?"):
                    st.markdown("""
                    - Double-cliquez sur le fichier téléchargé `carte_cinemas.html` pour l’ouvrir dans votre navigateur.
                    - Vous n’avez pas besoin de connexion internet ou de logiciel spécial.
                    - Vous pouvez le partager par email ou l’intégrer dans une présentation.
                    """)

                # Affiche la carte interactive dans Streamlit
                # Utilise st_folium pour une meilleure intégration que st.components.v1.html
                st_folium(carte, width='100%', height=600)

                 # Optionnel : Afficher la liste des cinémas sous la carte
                with st.expander("Voir la liste détaillée des cinémas trouvés"):
                     for groupe in liste_groupes_resultats:
                         if groupe["resultats"]:
                             st.subheader(f"Cinémas pour la recherche : {groupe['localisation']}")
                             # Affiche sous forme de dataframe pour une meilleure lisibilité
                             df = pd.DataFrame(groupe["resultats"])
                             colonnes_a_masquer = ["lat", "lon", "contact"]
                             colonnes_a_afficher = [col for col in df.columns if col not in colonnes_a_masquer]

                             st.dataframe(df[colonnes_a_afficher], use_container_width=True)
                
                # Sauvegarde Excel par groupe
                nom_fichier = f"cinemas_{groupe['localisation'].replace(' ', '_')}.xlsx"
                df[colonnes_a_afficher].to_excel(nom_fichier, index=False)

                # Ajoute un bouton de téléchargement pour chaque fichier Excel
                with open(nom_fichier, "rb") as f:
                    st.download_button(
                        label=f"📥 Télécharger Excel pour {groupe['localisation']}",
                        data=f,
                        file_name=nom_fichier,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

            else:
                # Ce cas ne devrait pas arriver si cinemas_trouves_total > 0, mais par sécurité
                st.error("Erreur lors de la génération de la carte.")

        else:
            # Aucun cinéma trouvé pour aucune des instructions
            st.error("❌ Aucun cinéma correspondant à votre demande n'a été trouvé dans la base de données selon les critères définis.")

# Message si aucune requête n'est entrée
else:
    st.info("Entrez une description de votre projet dans la zone de texte ci-dessus pour commencer.")