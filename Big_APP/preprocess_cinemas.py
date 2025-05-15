import json
import requests
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import time
import os

# Configuration
GEOCODER_USER_AGENT = "CinemaMapApp/1.0 (App)"
GEOCODER_TIMEOUT = 10
OUTPUT_FILE = "cinemas_groupedBig.json"

def get_mk2_cinemas():
    """
    Récupère la liste des cinémas MK2 depuis leur API
    """
    try:
        # URL de l'API MK2 (à remplacer par l'URL réelle)
        url = "https://api.mk2.com/cinemas"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Erreur lors de la récupération des cinémas MK2 : {e}")
        return []

def geocode_address(address):
    """
    Géocode une adresse pour obtenir les coordonnées
    """
    geolocator = Nominatim(user_agent=GEOCODER_USER_AGENT, timeout=GEOCODER_TIMEOUT)
    try:
        location = geolocator.geocode(f"{address}, France")
        if location:
            return location.latitude, location.longitude
        return None
    except (GeocoderTimedOut, GeocoderUnavailable) as e:
        print(f"Erreur de géocodage pour {address}: {e}")
        return None
    except Exception as e:
        print(f"Erreur inattendue lors du géocodage de {address}: {e}")
        return None

def process_cinemas():
    """
    Traite les données des cinémas et génère le fichier JSON
    """
    cinemas = get_mk2_cinemas()
    processed_cinemas = []

    for cinema in cinemas:
        # Structure de base pour chaque cinéma
        processed_cinema = {
            "cinema": cinema.get("name", "N/A"),
            "adresse": cinema.get("address", "N/A"),
            "contact": {
                "nom": cinema.get("contact_name", "N/A"),
                "email": cinema.get("contact_email", "N/A"),
                "telephone": cinema.get("contact_phone", "N/A")
            },
            "salles": []
        }

        # Géocodage de l'adresse
        coords = geocode_address(processed_cinema["adresse"])
        if coords:
            processed_cinema["lat"] = coords[0]
            processed_cinema["lon"] = coords[1]
        else:
            processed_cinema["lat"] = None
            processed_cinema["lon"] = None

        # Traitement des salles
        for room in cinema.get("rooms", []):
            processed_room = {
                "salle": room.get("name", "N/A"),
                "capacite": room.get("capacity", 0)
            }
            processed_cinema["salles"].append(processed_room)

        processed_cinemas.append(processed_cinema)
        # Pause pour éviter de surcharger le service de géocodage
        time.sleep(1)

    # Sauvegarde des données
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(processed_cinemas, f, ensure_ascii=False, indent=2)

    print(f"Traitement terminé. {len(processed_cinemas)} cinémas traités.")
    print(f"Fichier généré : {OUTPUT_FILE}")

if __name__ == "__main__":
    process_cinemas() 