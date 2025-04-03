# --- preprocess_cinemas.py ---
# Ce script lit le fichier JSON original des cinémas,
# tente de géocoder chaque adresse en utilisant Nominatim (OpenStreetMap),
# et sauvegarde un nouveau fichier JSON incluant les coordonnées (latitude, longitude).
# Il est conçu pour être exécuté une seule fois pour préparer les données
# et éviter de surcharger le service Nominatim lors de l'utilisation de l'application principale.

import json
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import time
import os

# --- Configuration ---
# Nom du fichier JSON d'entrée (doit exister dans le même dossier)
input_filename = "test.json"
# Nom du fichier JSON de sortie (sera créé/écrasé)
output_filename = "cinemas_geocoded.json"
# User agent pour le service de géocodage (important pour Nominatim)
# Remplace "MyApp/1.0" par quelque chose d'identifiable pour ton application
GEOCODER_USER_AGENT = "CinemaMapApp/1.0 (Preprocessing)"
# Timeout pour chaque requête de géocodage (en secondes)
GEOCODER_TIMEOUT = 15
# Pause entre chaque requête de géocodage (en secondes) - TRÈS IMPORTANT pour respecter les limites de Nominatim
SLEEP_BETWEEN_REQUESTS = 1.1
# Pause plus longue après une erreur de géocodage (en secondes)
SLEEP_AFTER_ERROR = 5

# --- Chargement des données d'entrée ---
try:
    print(f"Chargement du fichier d'entrée : {input_filename}")
    with open(input_filename, "r", encoding="utf-8") as f:
        cinemas_data = json.load(f)
    print(f"Trouvé {len(cinemas_data)} cinémas dans le fichier.")
except FileNotFoundError:
    print(f"ERREUR : Le fichier d'entrée '{input_filename}' n'a pas été trouvé.")
    print("Veuillez vous assurer que le fichier existe dans le même dossier que ce script.")
    exit(1) # Arrête le script avec un code d'erreur
except json.JSONDecodeError:
    print(f"ERREUR : Le fichier d'entrée '{input_filename}' contient un JSON invalide.")
    print("Veuillez vérifier la structure du fichier.")
    exit(1) # Arrête le script

# --- Initialisation du géocodeur ---
print(f"Initialisation du géocodeur Nominatim (User Agent: {GEOCODER_USER_AGENT})")
geolocator = Nominatim(user_agent=GEOCODER_USER_AGENT, timeout=GEOCODER_TIMEOUT)

# --- Traitement et Géocodage ---
cinemas_geocoded = [] # Liste pour stocker les cinémas traités (avec ou sans coordonnées)
failed_addresses = [] # Liste pour suivre les adresses qui n'ont pas pu être géocodées

print("\nDébut du processus de géocodage...")
print(f"Une pause de {SLEEP_BETWEEN_REQUESTS} sec sera effectuée entre chaque requête.")

# Boucle sur chaque cinéma dans les données chargées
for index, cinema in enumerate(cinemas_data):
    # Récupère le nom et l'adresse (utilise .get() pour éviter les erreurs si la clé manque)
    cinema_name = cinema.get('cinema', f'Cinéma #{index+1}')
    adresse = cinema.get('adresse')

    # Vérifie si les coordonnées sont déjà présentes et valides dans l'entrée
    # Permet de relancer le script sans refaire le travail déjà effectué
    has_coords = 'lat' in cinema and 'lon' in cinema and \
                 isinstance(cinema['lat'], (int, float)) and \
                 isinstance(cinema['lon'], (int, float))

    # Si l'adresse manque ou si les coordonnées sont déjà valides, on passe au suivant
    if not adresse or has_coords:
        status = "Ignoré (pas d'adresse)" if not adresse else "Ignoré (déjà géocodé)"
        print(f"({index+1}/{len(cinemas_data)}) {status} : '{cinema_name}'")
        cinemas_geocoded.append(cinema) # Ajoute l'entrée originale à la liste de sortie
        continue # Passe au cinéma suivant

    # Prépare l'adresse pour la requête de géocodage
    adresse = adresse.strip() # Enlève les espaces au début/fin
    # Ajoute ", France" si ce n'est pas déjà là (peut améliorer la précision pour Nominatim)
    if not adresse.lower().endswith(", france"):
        adresse_query = f"{adresse}, France"
    else:
        adresse_query = adresse

    print(f"({index+1}/{len(cinemas_data)}) Géocodage : '{cinema_name}' - Adresse: '{adresse}' (Requête: '{adresse_query}')")

    # Tente de géocoder l'adresse
    try:
        # Appel au service Nominatim
        location = geolocator.geocode(adresse_query)

        # Vérifie si une localisation a été trouvée
        if location:
            latitude = location.latitude
            longitude = location.longitude
            # Ajoute les coordonnées trouvées au dictionnaire du cinéma
            cinema['lat'] = latitude
            cinema['lon'] = longitude
            cinemas_geocoded.append(cinema) # Ajoute le cinéma mis à jour
            print(f"  -> SUCCÈS : Latitude={latitude:.6f}, Longitude={longitude:.6f}")
        else:
            # Aucune localisation trouvée pour cette adresse
            print(f"  -> ÉCHEC : Adresse non trouvée par Nominatim.")
            # Ajoute des valeurs nulles pour indiquer l'échec du géocodage
            cinema['lat'] = None
            cinema['lon'] = None
            cinemas_geocoded.append(cinema) # Ajoute le cinéma marqué comme échoué
            failed_addresses.append(f"'{cinema_name}': {adresse}") # Enregistre l'échec

        # --- Pause obligatoire ---
        # Respecte les conditions d'utilisation de Nominatim (max 1 req/sec)
        time.sleep(SLEEP_BETWEEN_REQUESTS)

    # Gestion des erreurs spécifiques au géocodage (timeout, service indisponible)
    except (GeocoderTimedOut, GeocoderUnavailable) as e:
        print(f"  -> ERREUR Géocodeur : {e}. L'adresse n'a pas pu être traitée.")
        cinema['lat'] = None
        cinema['lon'] = None
        cinemas_geocoded.append(cinema)
        failed_addresses.append(f"'{cinema_name}': {adresse} (Erreur: {e})")
        # Pause plus longue après une erreur pour laisser le service récupérer
        print(f"Pause de {SLEEP_AFTER_ERROR} secondes après l'erreur...")
        time.sleep(SLEEP_AFTER_ERROR)

    # Gestion des autres erreurs éventuelles
    except Exception as e:
        print(f"  -> ERREUR Inattendue : {e}. L'adresse n'a pas pu être traitée.")
        cinema['lat'] = None
        cinema['lon'] = None
        cinemas_geocoded.append(cinema)
        failed_addresses.append(f"'{cinema_name}': {adresse} (Erreur: {e})")
        time.sleep(SLEEP_BETWEEN_REQUESTS) # Pause normale même après une erreur inconnue


# --- Sauvegarde des résultats ---
print("\nGéocodage terminé.")
print(f"Sauvegarde des résultats dans le fichier : {output_filename}")

try:
    # Écrit la liste complète (cinémas géocodés + ceux qui ont échoué) dans le fichier de sortie
    with open(output_filename, "w", encoding="utf-8") as f:
        # indent=4 pour une lecture facile du fichier JSON
        # ensure_ascii=False pour correctement sauvegarder les caractères accentués
        json.dump(cinemas_geocoded, f, indent=4, ensure_ascii=False)
    print("Sauvegarde réussie.")
except IOError as e:
    print(f"ERREUR : Impossible d'écrire dans le fichier de sortie '{output_filename}'. Erreur: {e}")
    exit(1)

# --- Affichage des échecs ---
if failed_addresses:
    print("\nATTENTION : Certaines adresses n'ont pas pu être géocodées ou ont généré une erreur :")
    for addr_info in failed_addresses:
        print(f"- {addr_info}")
    print("\nVous devrez peut-être corriger ces adresses manuellement dans le fichier JSON d'origine")
    print("ou accepter qu'elles n'aient pas de coordonnées valides ('lat': null, 'lon': null)")
    print(f"dans '{output_filename}'.")
else:
    print("\nToutes les adresses ont été traitées (certaines peuvent ne pas avoir été trouvées, mais aucune erreur majeure).")

print("\nScript terminé.")