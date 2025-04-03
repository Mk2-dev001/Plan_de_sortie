# --- preprocess_cinemas.py ---
# Ce script lit un fichier JSON de cinémas, géocode les adresses avec Nominatim,
# nettoie les adresses problématiques, et sauvegarde le résultat enrichi en coordonnées GPS.

import json
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import time
import os
import re

# --- Configuration ---
input_filename = "test.json"
output_filename = "cinemas_geocoded.json"
errors_filename = "geocoding_errors.json"
GEOCODER_USER_AGENT = "CinemaMapApp/1.0 (Preprocessing)"
GEOCODER_TIMEOUT = 15
SLEEP_BETWEEN_REQUESTS = 1.1
SLEEP_AFTER_ERROR = 5

# --- Fonction de nettoyage d'adresse ---
def nettoyer_adresse(adresse_brute):
    if not adresse_brute:
        return None

    adresse = adresse_brute.strip()

    # Supprime certains termes inutiles
    adresse = re.sub(r"(?i)\bBP\s*\d+\b", "", adresse)
    adresse = re.sub(r"(?i)\bTéléphone\b.*", "", adresse)
    adresse = re.sub(r"(?i)\bMairie\b", "", adresse)
    adresse = re.sub(r"(?i)\bMaison de la Mer\b", "", adresse)

    # Nettoyage basique
    adresse = adresse.replace(" - ", ", ").replace("–", ", ").replace("  ", " ").strip()

    # Si l'adresse n'inclut pas la ville (code postal), elle est inutilisable
    if not re.search(r"\d{5}", adresse):
        return None

    return adresse

# --- Chargement des données d'entrée ---
try:
    print(f"Chargement du fichier d'entrée : {input_filename}")
    with open(input_filename, "r", encoding="utf-8") as f:
        cinemas_data = json.load(f)
    print(f"Trouvé {len(cinemas_data)} cinémas dans le fichier.")
except FileNotFoundError:
    print(f"ERREUR : Le fichier '{input_filename}' est introuvable.")
    exit(1)
except json.JSONDecodeError:
    print(f"ERREUR : Le fichier '{input_filename}' contient un JSON invalide.")
    exit(1)

# --- Initialisation du géocodeur ---
geolocator = Nominatim(user_agent=GEOCODER_USER_AGENT, timeout=GEOCODER_TIMEOUT)

# --- Géocodage ---
cinemas_geocoded = []
failed_addresses = []

print("\nDébut du géocodage...")

for index, cinema in enumerate(cinemas_data):
    cinema_name = cinema.get('cinema', f'Cinéma #{index+1}')
    adresse_brute = cinema.get('adresse')

    # Skip si coordonnées déjà présentes
    if 'lat' in cinema and 'lon' in cinema and isinstance(cinema['lat'], (int, float)) and isinstance(cinema['lon'], (int, float)):
        print(f"({index+1}/{len(cinemas_data)}) Ignoré (déjà géocodé) : '{cinema_name}'")
        cinemas_geocoded.append(cinema)
        continue

    # Nettoie l’adresse
    adresse = nettoyer_adresse(adresse_brute)

    if not adresse:
        print(f"({index+1}/{len(cinemas_data)}) Ignoré (adresse vide ou invalide après nettoyage) : '{cinema_name}'")
        cinema['lat'] = None
        cinema['lon'] = None
        cinemas_geocoded.append(cinema)
        failed_addresses.append({"cinema": cinema_name, "adresse": adresse_brute})
        continue

    adresse_query = f"{adresse}, France" if not adresse.lower().endswith("france") else adresse
    print(f"({index+1}/{len(cinemas_data)}) Géocodage : '{cinema_name}' -> '{adresse_query}'")

    try:
        location = geolocator.geocode(adresse_query)
        if location:
            cinema['lat'] = location.latitude
            cinema['lon'] = location.longitude
            cinemas_geocoded.append(cinema)
            print(f"  -> OK : ({location.latitude:.5f}, {location.longitude:.5f})")
        else:
            cinema['lat'] = None
            cinema['lon'] = None
            cinemas_geocoded.append(cinema)
            failed_addresses.append({"cinema": cinema_name, "adresse": adresse})
            print("  -> ÉCHEC : Adresse non trouvée.")
        time.sleep(SLEEP_BETWEEN_REQUESTS)

    except (GeocoderTimedOut, GeocoderUnavailable) as e:
        cinema['lat'] = None
        cinema['lon'] = None
        cinemas_geocoded.append(cinema)
        failed_addresses.append({"cinema": cinema_name, "adresse": adresse, "erreur": str(e)})
        print(f"  -> ERREUR (timeout/service) : {e}")
        time.sleep(SLEEP_AFTER_ERROR)
    except Exception as e:
        cinema['lat'] = None
        cinema['lon'] = None
        cinemas_geocoded.append(cinema)
        failed_addresses.append({"cinema": cinema_name, "adresse": adresse, "erreur": str(e)})
        print(f"  -> ERREUR inattendue : {e}")
        time.sleep(SLEEP_BETWEEN_REQUESTS)

# --- Sauvegarde du fichier final ---
try:
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(cinemas_geocoded, f, indent=4, ensure_ascii=False)
    print(f"\n✅ Fichier géocodé sauvegardé : {output_filename}")
except Exception as e:
    print(f"ERREUR : Impossible de sauvegarder '{output_filename}' : {e}")
    exit(1)

# --- Sauvegarde des erreurs ---
if failed_addresses:
    with open(errors_filename, "w", encoding="utf-8") as f:
        json.dump(failed_addresses, f, indent=4, ensure_ascii=False)
    print(f"⚠️ Certaines adresses n'ont pas été géocodées. Voir : {errors_filename}")
else:
    print("✅ Toutes les adresses ont été traitées avec succès.")

print("\nScript terminé.")
