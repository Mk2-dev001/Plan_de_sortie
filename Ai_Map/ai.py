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
import pandas # Ajouté pour st.dataframe

# --- CONFIGURATION DE LA PAGE (DOIT ÊTRE LA PREMIÈRE COMMANDE STREAMLIT) ---
st.set_page_config(layout="wide", page_title="Assistant Cinéma MK2", page_icon="🗺️") # Utilise toute la largeur, ajoute un titre/icône d'onglet

# --- Configuration (Variables globales) ---
# Nom du fichier JSON contenant les cinémas AVEC leurs coordonnées pré-calculées
GEOCATED_CINEMAS_FILE = "cinemas_geocoded.json"
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
        "Tu es un assistant expert pour des programmateurs de cinéma. "
        "L'utilisateur décrit un projet de projection ou d'exploitation d'un film en France. "
        "Ton rôle est d'extraire les intentions de diffusion de sa demande. "
        "Pour chaque lieu géographique distinct mentionné (ville, région spécifique), tu dois déduire un nombre cible de spectateurs pour ce lieu. "
        "Si aucun nombre précis n'est donné pour un lieu, propose une estimation réaliste basée sur le contexte (par exemple, 'petit public' = 100, 'séance test' = 50, 'gros cinéma' = 400, 'lancement majeur' = 1000). "
        "Interprète les régions larges en choisissant une ville représentative (ex: 'sud' -> 'Marseille', 'Bretagne' -> 'Rennes', 'région parisienne' -> 'Paris'). "
        "Le résultat DOIT être UNIQUEMENT une liste JSON valide. Ne retourne RIEN d'autre (pas de texte avant, pas de texte après, pas d'explication). "
        "Le format attendu est une liste de dictionnaires, chaque dictionnaire ayant les clés 'localisation' (str, nom de la ville ou lieu précis) et 'nombre' (int, nombre de spectateurs). "
        "Exemple de sortie attendue : [{'localisation': 'Marseille', 'nombre': 200}, {'localisation': 'Paris', 'nombre': 500}] "
        "Si la requête est trop vague ou ne mentionne aucun lieu/objectif, retourne une liste JSON vide []."
    )

    try:
        # Appel à l'API OpenAI ChatCompletion
        response = client.chat.completions.create(
            model="gpt-4o", # Utilise le modèle spécifié
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            response_format={"type": "json_object"} # Demande une réponse JSON directement si possible avec le modèle
        )

        # Récupère le contenu de la réponse
        text_response = response.choices[0].message.content.strip()

        # Affiche la réponse brute de l'IA pour le débogage (dans un bloc de code)
        st.sidebar.write("Réponse brute de l'IA :")
        st.sidebar.code(text_response, language="json")

        # Tente de parser la réponse JSON
        # GPT peut parfois retourner le JSON dans une structure plus large, on essaie de l'extraire.
        # Le format attendu est une liste, mais avec response_format="json_object",
        # il pourrait l'envelopper dans un objet, ex: {"result": [...]}. On cherche la liste.
        try:
            # Essai direct
            data = json.loads(text_response)
            # Si la réponse est un dictionnaire contenant une clé évidente pour la liste (ex: 'resultats', 'projections', 'locations')
            if isinstance(data, dict):
                 potential_keys = ['resultats', 'projections', 'locations', 'intentions', 'data', 'result']
                 for key in potential_keys:
                     if key in data and isinstance(data[key], list):
                         extracted_list = data[key]
                         # Vérifie si les éléments de la liste ont le bon format
                         if all(isinstance(item, dict) and 'localisation' in item and 'nombre' in item for item in extracted_list):
                              return extracted_list
                 # Si aucune clé ne correspond ou si le format interne est incorrect, on retourne vide
                 st.warning("L'IA a retourné un objet JSON, mais la structure attendue (liste de localisations/nombres) n'a pas été trouvée.")
                 return []
            # Si la réponse est directement une liste
            elif isinstance(data, list):
                 # Vérifie si les éléments de la liste ont le bon format
                 if all(isinstance(item, dict) and 'localisation' in item and 'nombre' in item for item in data):
                      return data
                 else:
                      st.warning("L'IA a retourné une liste JSON, mais les éléments n'ont pas le format attendu ({'localisation': ..., 'nombre': ...}).")
                      return []
            # Si ce n'est ni un dict ni une liste valide
            else:
                st.warning("La réponse JSON de l'IA n'est ni un objet contenant la liste attendue, ni la liste elle-même.")
                return []

        except json.JSONDecodeError:
            # Si le parsing JSON direct échoue, essaie d'extraire manuellement la partie liste
            # (utile si l'IA ajoute du texte autour du JSON malgré les instructions)
            st.warning("La réponse de l'IA n'était pas un JSON valide, tentative d'extraction manuelle...")
            try:
                json_part = text_response[text_response.find("["):text_response.rfind("]") + 1]
                extracted_list = json.loads(json_part)
                # Vérifie le format interne après extraction manuelle
                if all(isinstance(item, dict) and 'localisation' in item and 'nombre' in item for item in extracted_list):
                     return extracted_list
                else:
                     st.warning("La liste JSON extraite manuellement n'a pas le format attendu.")
                     return []
            except Exception:
                st.error("Impossible d'extraire ou de parser une liste JSON valide depuis la réponse de l'IA.")
                return [] # Retourne une liste vide en cas d'échec total

    except openai.APIError as e:
        st.error(f"Erreur de l'API OpenAI : {e}")
        return []
    except Exception as e:
        st.error(f"Erreur inattendue lors de l'appel à l'IA : {e}")
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
def trouver_cinemas_proches(localisation_cible: str, spectateurs_voulus: int, rayon_km: int = 50):
    """
    Trouve les cinémas dans un rayon donné autour d'un point central
    qui ont une capacité suffisante.
    Utilise les coordonnées pré-calculées du fichier JSON.

    Args:
        localisation_cible (str): Le nom du lieu demandé par l'utilisateur (ex: "Paris", "Lyon").
        spectateurs_voulus (int): La capacité minimale requise pour le cinéma.
        rayon_km (int): Le rayon de recherche maximum autour du point central (par défaut 50km).

    Returns:
        list: Une liste de dictionnaires, chaque dictionnaire représentant un cinéma trouvé.
              Retourne une liste vide si le point central ne peut être géocodé ou si aucun cinéma ne correspond.
    """
    # Étape 1: Géocoder le point central de la recherche (la localisation demandée)
    point_central_coords = geo_localisation(localisation_cible)

    # Si le point central n'a pas pu être trouvé, on ne peut pas chercher de cinémas
    if not point_central_coords:
        st.warning(f"Impossible de trouver des cinémas car la localisation centrale '{localisation_cible}' n'a pas pu être géocodée.")
        return []

    resultats = []
    # Étape 2: Parcourir les cinémas pré-géocodés
    for cinema in cinemas_data:
        # Récupérer les coordonnées et la capacité du cinéma courant
        lat = cinema.get('lat')
        lon = cinema.get('lon')
        capacite_str = cinema.get("capacite") # La capacité peut être une chaîne ou un nombre

        # Vérifier si le cinéma a des coordonnées valides
        if lat is not None and lon is not None:
            cinema_coords = (lat, lon)

            # Vérifier et convertir la capacité
            try:
                 # Gère les cas où la capacité est None, une chaîne vide, ou non numérique
                 capacite = int(capacite_str) if capacite_str is not None and str(capacite_str).isdigit() else 0
            except (ValueError, TypeError):
                 capacite = 0 # Met 0 si la conversion échoue

            # Étape 3: Vérifier si la capacité est suffisante
            if capacite >= spectateurs_voulus:
                # Étape 4: Calculer la distance entre le point central et le cinéma
                try:
                    distance = geodesic(point_central_coords, cinema_coords).km
                except ValueError as e:
                    # Gère les erreurs potentielles de calcul de distance (coordonnées invalides?)
                    st.sidebar.warning(f"Impossible de calculer la distance pour {cinema.get('cinema', 'Inconnu')} : {e}")
                    continue # Passe au cinéma suivant

                # Étape 5: Vérifier si le cinéma est dans le rayon de recherche
                if distance <= rayon_km:
                    # Ajoute les informations du cinéma trouvé à la liste des résultats
                    resultats.append({
                        "nom": cinema.get('cinema', 'Nom inconnu'),
                        "adresse": cinema.get('adresse', 'Adresse inconnue'),
                        "lat": lat,
                        "lon": lon,
                        "distance_km": round(distance, 2), # Arrondit la distance pour l'affichage
                        "capacite": capacite,
                        "source_localisation": localisation_cible # Garde une trace de quelle requête a trouvé ce ciné
                    })

    # Étape 6: Trier les résultats par distance (du plus proche au plus lointain)
    resultats.sort(key=lambda x: x["distance_km"])

    return resultats

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
    # Ajuste le zoom initial en fonction du nombre de groupes ? (Optionnel)
    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=6, tiles="CartoDB positron")

    # Définit une palette de couleurs pour distinguer les groupes de recherche
    couleurs = ["blue", "green", "red", "purple", "orange", "darkred", "lightred", "beige", "darkblue", "darkgreen", "cadetblue", "lightgray", "black"]

    # Ajoute des marqueurs pour chaque cinéma sur la carte
    for idx, groupe in enumerate(groupes_de_cinemas):
        couleur = couleurs[idx % len(couleurs)] # Cycle à travers les couleurs
        localisation_origine = groupe.get("localisation", "Inconnue")
        resultats_groupe = groupe.get("resultats", [])

        # Crée un groupe de fonctionnalités pour chaque requête (permettra de les afficher/masquer plus tard si besoin)
        feature_group = folium.FeatureGroup(name=f"{localisation_origine} ({len(resultats_groupe)} cinémas)")

        for cinema in resultats_groupe:
            # Crée le texte du popup pour chaque marqueur
            popup_html = f"""
            <b>{cinema['nom']}</b><br>
            <i>{cinema['adresse']}</i><br>
            Capacité : {cinema['capacite']} places<br>
            Distance ({localisation_origine}) : {cinema['distance_km']} km
            """
            # Ajoute un marqueur circulaire pour le cinéma
            folium.CircleMarker(
                location=[cinema['lat'], cinema['lon']],
                radius=5, # Taille du marqueur
                color=couleur, # Couleur du contour
                fill=True,
                fill_color=couleur, # Couleur de remplissage
                fill_opacity=0.7,
                popup=folium.Popup(popup_html, max_width=300) # Contenu du popup
            ).add_to(feature_group) # Ajoute au groupe spécifique

        feature_group.add_to(m) # Ajoute le groupe à la carte

    # Ajoute un contrôle des couches pour afficher/masquer les groupes
    folium.LayerControl().add_to(m)

    return m # Retourne l'objet carte Folium

# --- Interface Utilisateur Streamlit ---
# st.set_page_config(layout="wide") # Utilise toute la largeur de la page
st.title("🗺️ Assistant de Planification Cinéma MK2")
st.markdown("Décrivez votre projet de diffusion et l'IA identifiera les cinémas pertinents en France.")

# Section d'aide dans un expander
with st.expander("ℹ️ Comment ça marche ?"):
    st.markdown("""
    Cette application vous aide à trouver des cinémas en France correspondant à vos besoins de projection.

    1.  **Décrivez votre besoin** dans la zone de texte ci-dessous en langage naturel. Soyez aussi précis que possible sur les lieux (villes, régions) et le public cible (nombre de spectateurs).
        * *Exemple 1 :* "Je veux tester mon film dans une petite salle à Lyon et faire une avant-première à Paris pour 300 personnes."
        * *Exemple 2 :* "Lancement national : prévoir des salles d'au moins 200 places à Lille, Bordeaux et Marseille."
        * *Exemple 3 :* "Diffusion en Bretagne avec un objectif de 150 spectateurs par ville."
    2.  **L'IA (GPT-4o)** analyse votre demande pour identifier les localisations et les jauges estimées. Les détails de l'interprétation apparaissent dans la barre latérale.
    3.  **Le système recherche** dans la base de données les cinémas (préalablement géocodés) qui correspondent à ces critères (localisation proche, capacité suffisante).
    4.  **Une carte interactive** s'affiche avec les cinémas trouvés. Cliquez sur les marqueurs pour voir les détails. Utilisez le contrôle des couches (en haut à droite de la carte) pour filtrer par requête.
    5.  Vous pouvez **télécharger la carte** au format HTML pour la partager ou l'analyser plus tard.

    *Note : La base de données des cinémas et leurs coordonnées sont issues du fichier `cinemas_geocoded.json`.*
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
        st.info(f"🤖 **IA a compris :** {len(instructions_ia)} zone(s) de recherche pour un objectif total estimé à {total_spectateurs_estimes} spectateurs.")
        st.json(instructions_ia) # Affiche les instructions JSON pour transparence

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
                    # Récupère le rayon de recherche (on peut le rendre configurable plus tard)
                    rayon_recherche = st.sidebar.slider(f"Rayon de recherche autour de {loc} (km)", 5, 200, 50, key=f"rayon_{loc}")

                    # Appel à la fonction de recherche de cinémas
                    resultats_cinemas = trouver_cinemas_proches(loc, num, rayon_km=rayon_recherche)

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
            st.success(f"✅ Recherche terminée ! {cinemas_trouves_total} cinéma(s) pertinent(s) trouvé(s) au total.")
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

                # Affiche la carte interactive dans Streamlit
                # Utilise st_folium pour une meilleure intégration que st.components.v1.html
                st_folium(carte, width='100%', height=600)

                 # Optionnel : Afficher la liste des cinémas sous la carte
                with st.expander("Voir la liste détaillée des cinémas trouvés"):
                     for groupe in liste_groupes_resultats:
                         if groupe["resultats"]:
                             st.subheader(f"Cinémas pour la recherche : {groupe['localisation']}")
                             # Affiche sous forme de dataframe pour une meilleure lisibilité
                             st.dataframe(groupe["resultats"], use_container_width=True)

            else:
                # Ce cas ne devrait pas arriver si cinemas_trouves_total > 0, mais par sécurité
                st.error("Erreur lors de la génération de la carte.")

        else:
            # Aucun cinéma trouvé pour aucune des instructions
            st.error("❌ Aucun cinéma correspondant à votre demande n'a été trouvé dans la base de données selon les critères définis.")

# Message si aucune requête n'est entrée
else:
    st.info("Entrez une description de votre projet dans la zone de texte ci-dessus pour commencer.")