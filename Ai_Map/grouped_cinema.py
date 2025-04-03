# --- regrouper_cinemas.py ---
# Ce script lit un fichier de salles de cinéma et regroupe les données par cinéma,
# en intégrant toutes les salles de chaque cinéma dans une liste.

import json
from collections import defaultdict

input_file = "cinemas_geocoded.json"
output_file = "cinemas_grouped.json"

# Chargement des données
with open(input_file, "r", encoding="utf-8") as f:
    salles = json.load(f)

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

for salle in salles:
    # Clé unique par combinaison cinéma + adresse
    cle = (salle["cinema"], salle["adresse"])

    bloc = cinemas_groupes[cle]

    bloc["cinema"] = salle["cinema"]
    bloc["adresse"] = salle["adresse"]
    bloc["lat"] = salle.get("lat")
    bloc["lon"] = salle.get("lon")
    bloc["contact"]["nom"] = salle.get("nom_contact", "")
    bloc["contact"]["email"] = salle.get("email", "")
    bloc["contact"]["telephone"] = salle.get("telephone", "")

    bloc["salles"].append({
        "salle": salle.get("salle"),
        "cnc": salle.get("cnc"),
        "capacite": salle.get("capacite"),
        "equipement": salle.get("equipement"),
        "format_projection": salle.get("format_projection")
    })

# Conversion en liste finale
cinemas_final = list(cinemas_groupes.values())

# Sauvegarde
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(cinemas_final, f, indent=4, ensure_ascii=False)

print(f"✅ Cinémas regroupés enregistrés dans : {output_file}")
