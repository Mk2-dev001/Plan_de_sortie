import json
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import time
import re
from collections import defaultdict

# --- Configuration ---
input_filename = "test.json"
geocoded_filename = "cinemas_geocoded.json"
grouped_filename = "cinemas_grouped.json"
errors_filename = "geocoding_errors.json"
GEOCODER_USER_AGENT = "CinemaMapApp/1.0 (Preprocessing)"
GEOCODER_TIMEOUT = 15
SLEEP_BETWEEN_REQUESTS = 1.1
SLEEP_AFTER_ERROR = 5
MAX_RETRIES = 3  # Maximum number of retries in case of a timeout

# --- Fonction de nettoyage d'adresse améliorée ---
def nettoyer_adresse(adresse_brute):
    if not adresse_brute:
        return None

    adresse = adresse_brute.strip()

    # Supprime uniquement certains termes spécifiques inutiles pour le géocodage
    adresse = re.sub(r"(?i)\bBP\s*\d+\b", "", adresse)
    adresse = re.sub(r"(?i)\bTéléphone\b.*", "", adresse)
    # Ne supprime plus "Mairie" ni "Maison de la Mer" car ils peuvent être utiles pour la localisation
    
    # Remplace des séparateurs par des virgules pour améliorer le géocodage
    adresse = adresse.replace(" - ", ", ").replace("–", ", ").replace("  ", " ").strip()
    
    # Si l'adresse ne contient pas de code postal, tentons d'extraire la ville
    if not re.search(r"\d{5}", adresse):
        # Cherchons si on a au moins une ville identifiable
        villes = re.search(r"(?:, )(\w+)(?:,|$)", adresse)
        if villes:
            # On a trouvé une ville, on ne rejette pas l'adresse
            pass
        else:
            # Si l'adresse contient "France" sans code postal, essayons quand même
            if "France" not in adresse:
                return None

    # Ajouter le pays si nécessaire
    if not adresse.lower().endswith("france"):
        adresse += ", France"

    return adresse

# --- Fonction pour identifier les cinémas uniques (pour le géocodage) ---
def identifier_cinemas_uniques(salles):
    # Utiliser un dictionnaire pour stocker un seul exemplaire de chaque cinéma par adresse
    cinemas_uniques = {}
    
    for salle in salles:
        # Clé unique par combinaison cinéma + adresse
        cle = (salle.get("cinema", ""), salle.get("adresse", ""))
        
        # Si cette clé n'existe pas encore, ajouter le cinéma à la liste
        if cle not in cinemas_uniques:
            cinemas_uniques[cle] = {
                "cinema": salle.get("cinema", ""),
                "adresse": salle.get("adresse", ""),
                # Copier les autres champs qui ne sont pas spécifiques à la salle
                "nom_contact": salle.get("nom_contact", ""),
                "email": salle.get("email", ""),
                "telephone": salle.get("telephone", "")
            }
    
    return list(cinemas_uniques.values())

# --- Fonction pour regrouper les cinémas par nom et adresse ---
def regrouper_cinemas(cinemas_geocodes, salles_originales):
    # Créer un dictionnaire de lookup pour les coordonnées géocodées
    coords_lookup = {}
    for cinema in cinemas_geocodes:
        cle = (cinema.get("cinema", ""), cinema.get("adresse", ""))
        coords_lookup[cle] = {
            "lat": cinema.get("lat"),
            "lon": cinema.get("lon")
        }
    
    # Regroupement par nom + adresse (clé unique)
    cinemas_groupes = defaultdict(lambda: {
        "cinema": "",
        "adresse": "",
        "lat": None,
        "lon": None,
        "contact": {
            "nom": "",
            "email": "",
            "telephone": ""
        },
        "salles": []
    })

    for salle in salles_originales:
        # Clé unique par combinaison cinéma + adresse
        cle = (salle.get("cinema", ""), salle.get("adresse", ""))

        bloc = cinemas_groupes[cle]

        # Informations de base du cinéma
        bloc["cinema"] = salle.get("cinema", "")
        bloc["adresse"] = salle.get("adresse", "")
        
        # Récupérer les coordonnées depuis notre lookup
        if cle in coords_lookup:
            bloc["lat"] = coords_lookup[cle]["lat"]
            bloc["lon"] = coords_lookup[cle]["lon"]
        
        # Informations de contact
        bloc["contact"]["nom"] = salle.get("nom_contact", "")
        bloc["contact"]["email"] = salle.get("email", "")
        bloc["contact"]["telephone"] = salle.get("telephone", "")

        # Ajouter cette salle à la liste des salles
        bloc["salles"].append({
            "salle": salle.get("salle", ""),
            "cnc": salle.get("cnc", ""),
            "capacite": salle.get("capacite", ""),
            "equipement": salle.get("equipement", ""),
            "format_projection": salle.get("format_projection", "")
        })

    # Conversion en liste finale
    return list(cinemas_groupes.values())

# --- Chargement des données d'entrée ---
try:
    print(f"Chargement du fichier d'entrée : {input_filename}")
    with open(input_filename, "r", encoding="utf-8") as f:
        salles_data = json.load(f)
    print(f"Trouvé {len(salles_data)} salles dans le fichier.")
    
    # Identifier les cinémas uniques pour le géocodage
    cinemas_uniques = identifier_cinemas_uniques(salles_data)
    print(f"Identifié {len(cinemas_uniques)} cinémas uniques à géocoder.")
    
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

for index, cinema in enumerate(cinemas_uniques):
    cinema_name = cinema.get('cinema', f'Cinéma #{index+1}')
    adresse_brute = cinema.get('adresse')

    # Skip si coordonnées déjà présentes
    if 'lat' in cinema and 'lon' in cinema and isinstance(cinema['lat'], (int, float)) and isinstance(cinema['lon'], (int, float)):
        print(f"({index+1}/{len(cinemas_uniques)}) Ignoré (déjà géocodé) : '{cinema_name}'")
        cinemas_geocoded.append(cinema)
        continue

    # Nettoie l'adresse
    adresse = nettoyer_adresse(adresse_brute)

    if not adresse:
        print(f"({index+1}/{len(cinemas_uniques)}) Ignoré (adresse vide ou invalide après nettoyage) : '{cinema_name}'")
        cinema['lat'] = None
        cinema['lon'] = None
        cinemas_geocoded.append(cinema)
        failed_addresses.append({"cinema": cinema_name, "adresse": adresse_brute})
        continue

    # Essayer d'abord avec le nom du cinéma dans la requête pour plus de précision
    adresse_query = f"{cinema_name}, {adresse}"  
    print(f"({index+1}/{len(cinemas_uniques)}) Géocodage : '{cinema_name}' -> '{adresse_query}'")

    retries = 0
    location = None
    
    while retries < MAX_RETRIES and not location:
        try:
            # Premier essai avec le nom du cinéma inclus
            location = geolocator.geocode(adresse_query)
            
            # Si ça échoue, essayer sans le nom du cinéma
            if not location and retries == 0:
                print(f"  -> Tentative sans le nom du cinéma")
                adresse_query = adresse
                location = geolocator.geocode(adresse_query)
            
            # Si toujours pas de résultat et qu'on a un code postal, essayer juste avec ville et code postal
            if not location and retries == 1:
                code_postal = re.search(r"\d{5}", adresse)
                if code_postal:
                    cp = code_postal.group(0)
                    ville_match = re.search(rf"{cp}\s+([^,]+)", adresse)
                    if ville_match:
                        ville = ville_match.group(1)
                        adresse_query = f"{ville}, {cp}, France"
                        print(f"  -> Tentative simplifiée : '{adresse_query}'")
                        location = geolocator.geocode(adresse_query)
            
            if location:
                cinema['lat'] = location.latitude
                cinema['lon'] = location.longitude
                cinemas_geocoded.append(cinema)
                print(f"  -> OK : ({location.latitude:.5f}, {location.longitude:.5f})")
                break
            else:
                retries += 1
                if retries >= MAX_RETRIES:
                    cinema['lat'] = None
                    cinema['lon'] = None
                    cinemas_geocoded.append(cinema)
                    failed_addresses.append({"cinema": cinema_name, "adresse": adresse_brute})
                    print("  -> ÉCHEC : Adresse non trouvée après plusieurs tentatives.")
                else:
                    print(f"  -> Tentative {retries}/{MAX_RETRIES} échouée, nouvel essai...")
                    time.sleep(SLEEP_BETWEEN_REQUESTS)
                
        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            retries += 1
            print(f"  -> ERREUR (timeout/service) : {e} - tentative {retries}/{MAX_RETRIES}")
            time.sleep(SLEEP_AFTER_ERROR)
        except Exception as e:
            retries += 1
            print(f"  -> ERREUR inattendue : {e} - tentative {retries}/{MAX_RETRIES}")
            if retries >= MAX_RETRIES:
                cinema['lat'] = None
                cinema['lon'] = None
                cinemas_geocoded.append(cinema)
                failed_addresses.append({"cinema": cinema_name, "adresse": adresse_brute, "erreur": str(e)})
            time.sleep(SLEEP_BETWEEN_REQUESTS)
    
    time.sleep(SLEEP_BETWEEN_REQUESTS)  # Pause entre chaque requête

# --- Sauvegarde du fichier géocodé ---
try:
    with open(geocoded_filename, "w", encoding="utf-8") as f:
        json.dump(cinemas_geocoded, f, indent=4, ensure_ascii=False)
    print(f"\n✅ Fichier géocodé sauvegardé : {geocoded_filename}")
except Exception as e:
    print(f"ERREUR : Impossible de sauvegarder '{geocoded_filename}' : {e}")
    exit(1)

# --- Sauvegarde des erreurs ---
if failed_addresses:
    with open(errors_filename, "w", encoding="utf-8") as f:
        json.dump(failed_addresses, f, indent=4, ensure_ascii=False)
    print(f"⚠️ {len(failed_addresses)} adresses n'ont pas été géocodées. Voir : {errors_filename}")
else:
    print("✅ Toutes les adresses ont été traitées avec succès.")

# --- Partie 2: Regroupement des cinémas ---
print("\nDébut du regroupement des cinémas...")

# Regrouper les cinémas en utilisant les données originales et les coordonnées géocodées
cinemas_grouped = regrouper_cinemas(cinemas_geocoded, salles_data)

# Sauvegarde du fichier regroupé
try:
    with open(grouped_filename, "w", encoding="utf-8") as f:
        json.dump(cinemas_grouped, f, indent=4, ensure_ascii=False)
    print(f"✅ Cinémas regroupés enregistrés dans : {grouped_filename}")
except Exception as e:
    print(f"ERREUR : Impossible de sauvegarder '{grouped_filename}' : {e}")
    exit(1)

print("\nTraitement terminé avec succès.")
print(f"- {len(cinemas_geocoded)} cinémas uniques géocodés")
print(f"- {len(failed_addresses)} adresses en échec")
print(f"- {len(cinemas_grouped)} cinémas regroupés contenant {sum(len(c['salles']) for c in cinemas_grouped)} salles au total")