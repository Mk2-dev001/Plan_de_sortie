import os
import shutil
import pandas as pd
import matplotlib.pyplot as plt
import re
from pathlib import Path
import asyncio
import time
import json
import csv
import logging
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from openai import AsyncOpenAI

# --- Nouvelles importations ---
try:
    import PyPDF2
except ImportError:
    print("Avertissement: PyPDF2 non trouvé. L'extraction de texte PDF sera désactivée.")
    print("Installez avec: pip install PyPDF2")
    PyPDF2 = None

try:
    import docx # python-docx
except ImportError:
    print("Avertissement: python-docx non trouvé. L'extraction de texte DOCX sera désactivée.")
    print("Installez avec: pip install python-docx")
    docx = None

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
except ImportError:
    print("Avertissement: Pillow non trouvé. L'analyse des métadonnées EXIF sera désactivée.")
    print("Installez avec: pip install Pillow")
    Image = None
    TAGS = {}

try:
    from thefuzz import fuzz, process
except ImportError:
    print("Avertissement: thefuzz non trouvé. Le matching flou sera désactivé.")
    print("Installez avec: pip install thefuzz python-Levenshtein")
    fuzz = None
    process = None
# --- Fin Nouvelles importations ---

# Configuration
SOURCE_DIR = Path("Chaplin")  # Remplacer par le dossier source réel
DESTINATION_DIR = Path("SortedY")
LOG_FILE = "traitement_medias.csv"
MEDIA_LABELS = {'AfficheS': '1', 'Photo HD': '2', 'Dossier de presse': '3', 'Revue de presse': '4'}
# Inclure les autres catégories pour une meilleure correspondance interne
ALL_CATEGORIES = list(MEDIA_LABELS.keys()) + [
    'Documents administratifs', 'Factures', 'Contrats', 'Présentations',
    'Médias (audio/vidéo)', 'Divers'
]

# Extensions de fichiers à traiter
VALID_EXTENSIONS = [
    '.jpg', '.jpeg', '.png', '.gif', '.tif', '.tiff', '.bmp',  # Images
    '.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.txt',  # Documents
    '.mp4', '.mov', '.avi', '.mp3', '.wav',  # Médias
]

# Motifs à ignorer
IGNORE_PATTERNS = [
    '.DS_Store', '._', '.git', '__MACOSX', 'Thumbs.db', '.tmp'
]

# Liste des films Chaplin connus (pour améliorer la détection)
KNOWN_FILMS = [
    "The Kid", "The Gold Rush", "City Lights", "Modern Times",
    "The Great Dictator", "Monsieur Verdoux", "Limelight",
    "A King in New York", "A Woman of Paris", "The Circus"
    # Ajouter d'autres titres ou variations si nécessaire
]

# Seuils pour le matching flou (à ajuster)
FUZZY_MATCH_THRESHOLD_FOLDER = 90 # Pourcentage de similarité pour lier dossier <-> titre excel
FUZZY_MATCH_THRESHOLD_FILE = 95   # Pourcentage de similarité pour lier fichier <-> titre connu

# Initialisation
console = Console()
DESTINATION_DIR.mkdir(parents=True, exist_ok=True)

# Stockage des films détectés et leurs IDs
DETECTED_FILMS = {}  # Sera rempli pendant l'analyse
next_id = 1

# Cache pour les décisions d'IA - nom modifié pour forcer le rechargement
CACHE_FILE = "ai_decisions_cache_v2.json" # Version modifiée
ai_cache = {}

# --- Logger CSV ---
csv_logger = None
csv_writer = None

def setup_csv_logger():
    """Initialise le logger CSV."""
    global csv_logger, csv_writer
    try:
        # Ouvrir en mode 'a' pour ajouter, 'w' pour écraser
        csv_logger = open(LOG_FILE, 'w', newline='', encoding='utf-8')
        fieldnames = ['Timestamp', 'OriginalPath', 'Status', 'DetectedFilmID', 'DetectedFilmName', 'DetectedCategory', 'NewPath', 'Reason']
        csv_writer = csv.DictWriter(csv_logger, fieldnames=fieldnames)
        csv_writer.writeheader()
        console.print(f"[green]Journalisation activée dans '{LOG_FILE}'[/green]")
    except Exception as e:
        console.print(f"[red]Erreur lors de l'initialisation du logger CSV: {e}[/red]")
        csv_logger = None
        csv_writer = None

def log_file_event(original_path, status, film_id=None, film_name=None, category=None, new_path=None, reason=None):
    """Enregistre un événement de fichier dans le CSV."""
    if csv_writer:
        try:
            csv_writer.writerow({
                'Timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'OriginalPath': str(original_path),
                'Status': status, # 'success', 'ignored', 'error', 'moved_to_other'
                'DetectedFilmID': film_id if film_id else '',
                'DetectedFilmName': film_name if film_name else '',
                'DetectedCategory': category if category else '',
                'NewPath': str(new_path) if new_path else '',
                'Reason': reason if reason else ''
            })
            csv_logger.flush() # Forcer l'écriture immédiate
        except Exception as e:
            console.print(f"[red]Erreur d'écriture dans le log CSV: {e}[/red]")

# --- Fin Logger CSV ---


# Charger le cache s'il existe
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            ai_cache = json.load(f)
    except Exception as e:
        console.print(f"[yellow]Impossible de charger le cache d'IA ({e}). Création d'un nouveau cache.[/yellow]")
        ai_cache = {}

# OpenAI API setup
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

openai_api_key = os.getenv("OPENAI_API_KEY")
openai_client = None
if openai_api_key:
    openai_client = AsyncOpenAI(api_key=openai_api_key)
    console.print("[green]API OpenAI configurée avec succès[/green]")
else:
    console.print("[yellow]Clé API OpenAI non trouvée. La détection avancée ne sera pas disponible.[/yellow]")

def create_default_alternatives_file():
    """Crée un fichier de configuration par défaut pour les titres alternatifs s'il n'existe pas"""
    alternatives_file = "film_alternatives.json"
    
    # Vérifier si le fichier existe déjà
    if os.path.exists(alternatives_file):
        return alternatives_file
    
    # Créer un dictionnaire par défaut avec quelques exemples
    default_alternatives = {
        "canine": ["dogtooth", "kynodontas", "canino", "kynodondas"],
        "the kid": ["le kid", "el chico"],
        "modern times": ["les temps modernes", "tempos modernos"],
        # Ajouter d'autres exemples ici
    }
    
    # Écrire le fichier JSON avec un formatage lisible
    try:
        with open(alternatives_file, 'w', encoding='utf-8') as f:
            json.dump(default_alternatives, f, indent=4, ensure_ascii=False)
        console.print(f"[green]Fichier de configuration des titres alternatifs créé: {alternatives_file}[/green]")
    except Exception as e:
        console.print(f"[yellow]Impossible de créer le fichier de configuration: {e}[/yellow]")
    
    return alternatives_file

# 2. Chargement des titres alternatifs depuis le fichier externe

def load_alternative_titles():
    """Charge les titres alternatifs depuis le fichier de configuration"""
    alternatives_file = create_default_alternatives_file()
    alternatives = {}
    
    try:
        with open(alternatives_file, 'r', encoding='utf-8') as f:
            alternatives = json.load(f)
        console.print(f"[green]Titres alternatifs chargés depuis {alternatives_file}[/green]")
        
        # Afficher un aperçu des alternatives chargées
        if alternatives:
            console.print("[grey]Aperçu des titres alternatifs chargés:[/grey]")
            for main_title, alts in list(alternatives.items())[:5]:  # Limiter à 5 pour l'affichage
                console.print(f"[grey]  '{main_title}' → {', '.join(alts)}[/grey]")
            if len(alternatives) > 5:
                console.print(f"[grey]  ... et {len(alternatives) - 5} autres films[/grey]")
    except Exception as e:
        console.print(f"[yellow]Erreur lors du chargement des titres alternatifs: {e}[/yellow]")
        console.print("[yellow]Utilisation des valeurs par défaut[/yellow]")
        # Valeurs par défaut minimales en cas d'erreur
        alternatives = {
            "canine": ["dogtooth", "kynodontas"]
        }
    
    return alternatives

def load_excel_ids():
    """Version améliorée pour charger les IDs avec support des titres alternatifs externes"""
    try:
        # Charger les titres alternatifs depuis le fichier externe
        known_alternatives = load_alternative_titles()
        
        excel_path = "MK2 - Metadatas export.xlsx"
        if not os.path.exists(excel_path):
            console.print("[yellow]Fichier Excel introuvable: Utilisation d'IDs séquentiels[/yellow]")
            return {}
        
        # Lecture de base avec header=None pour traiter les en-têtes manuellement
        console.print(f"[blue]Tentative de lecture du fichier Excel: {excel_path}[/blue]")
        
        try:
            # Première tentative avec openpyxl
            df = pd.read_excel(excel_path, engine='openpyxl', header=None)
            console.print("[green]Lecture réussie avec openpyxl[/green]")
        except Exception as e1:
            console.print(f"[yellow]Erreur avec openpyxl: {e1}[/yellow]")
            try:
                # Deuxième tentative avec xlrd
                df = pd.read_excel(excel_path, engine='xlrd', header=None)
                console.print("[green]Lecture réussie avec xlrd[/green]")
            except Exception as e2:
                console.print(f"[yellow]Erreur avec xlrd: {e2}[/yellow]")
                try:
                    # Dernière tentative avec moteur par défaut
                    df = pd.read_excel(excel_path, header=None)
                    console.print("[green]Lecture réussie avec moteur par défaut[/green]")
                except Exception as e3:
                    console.print(f"[red]Impossible de lire l'Excel: {e3}[/red]")
                    return {}
        
        # Déterminer l'index des colonnes ID et Titre à partir de la deuxième ligne
        id_col = None
        title_col = None
        original_title_col = None
        
        if len(df) > 1:  # Vérifie qu'il y a au moins 2 lignes
            header_row = df.iloc[1]  # Deuxième ligne contenant les vrais en-têtes
            
            # Chercher l'index des colonnes importantes
            for i, val in enumerate(header_row):
                if pd.notnull(val):
                    val_lower = str(val).lower()
                    if val_lower == "id":
                        id_col = i
                    elif "titre" in val_lower and "original" not in val_lower:
                        title_col = i
                    elif "titre original" in val_lower or "original title" in val_lower:
                        original_title_col = i
            
            # Si on n'a pas trouvé "Titre", prendre la colonne suivant "ID"
            if id_col is not None and title_col is None and id_col + 1 < len(header_row):
                title_col = id_col + 1
        
        # Valeurs par défaut si non trouvées
        if id_col is None:
            id_col = 0
            console.print("[yellow]Utilisation de la colonne 1 pour ID par défaut[/yellow]")
        if title_col is None:
            title_col = 1
            console.print("[yellow]Utilisation de la colonne 2 pour Titre par défaut[/yellow]")
        
        console.print(f"[green]Colonnes: ID = {id_col+1}, Titre = {title_col+1}, Titre Original = {original_title_col+1 if original_title_col is not None else 'Non trouvé'}[/green]")
        
        # Construction du dictionnaire de correspondance
        film_ids_dict = {}
        
        # Fonction pour rechercher des titres alternatifs connus
        def find_known_alternatives(main_title, id_val):
            main_title_lower = main_title.lower()
            added_variants = []
            
            # Chercher dans notre base de connaissances externe
            for base_title, alternatives in known_alternatives.items():
                # Si le titre principal correspond à une entrée connue ou à une alternative
                if main_title_lower == base_title or main_title_lower in alternatives:
                    # Ajouter toutes les variantes
                    for alt in alternatives + [base_title]:
                        if alt != main_title_lower and alt not in film_ids_dict:
                            film_ids_dict[alt] = id_val
                            added_variants.append(alt)
            
            return added_variants
        
        # Parcourir toutes les lignes à partir de la 3ème (index 2)
        for i in range(2, len(df)):
            row = df.iloc[i]
            
            # Vérifier que l'ID et le titre sont présents
            if pd.notnull(row[id_col]) and pd.notnull(row[title_col]):
                try:
                    # Extraire et nettoyer l'ID
                    id_val = str(row[id_col])
                    if id_val.replace('.', '', 1).isdigit():  # Si c'est un nombre (entier ou décimal)
                        id_val = str(int(float(id_val)))  # Convertir en entier
                    else:
                        id_val = id_val.strip()
                    
                    # Extraire et nettoyer le titre
                    title = str(row[title_col]).strip()
                    
                    # Extraire le titre original si disponible
                    original_title = None
                    if original_title_col is not None and pd.notnull(row[original_title_col]):
                        original_title = str(row[original_title_col]).strip()
                    
                    # Vérifier si c'est une ligne valide (pas une ligne d'en-tête répétée)
                    if title.lower() not in ["titre", "title"] and id_val.lower() not in ["id"]:
                        # Ajouter le titre principal
                        film_ids_dict[title] = id_val
                        film_ids_dict[title.lower()] = id_val
                        
                        # Ajouter le titre original s'il est différent
                        if original_title and original_title != title:
                            film_ids_dict[original_title] = id_val
                            film_ids_dict[original_title.lower()] = id_val
                        
                        # Traiter les cas avec parenthèses ou crochets (souvent des variantes)
                        for bracket_char in ['(', '[']:
                            if bracket_char in title:
                                base_title = title.split(bracket_char)[0].strip()
                                film_ids_dict[base_title] = id_val
                                film_ids_dict[base_title.lower()] = id_val
                        
                        # Rechercher des variantes connues
                        alternatives = find_known_alternatives(title, id_val)
                        if alternatives and (title.lower() == 'canine' or 'canine' in alternatives):
                            console.print(f"[green]Film CANINE/DOGTOOTH trouvé: ID={id_val}, Titre={title}, Alternatives={alternatives}[/green]")
                except Exception as e:
                    # Ignorer les erreurs de conversion
                    pass
        
        # Afficher un résumé
        unique_ids = len(set(film_ids_dict.values()))
        console.print(f"[green]Chargement réussi de {unique_ids} IDs uniques depuis l'Excel[/green]")
        
        if unique_ids > 0:
            # Afficher quelques exemples pour vérification
            console.print("[grey]Échantillon des correspondances:[/grey]")
            count = 0
            seen_ids = set()
            for title, id_val in film_ids_dict.items():
                if title.lower() == title:  # Skip lowercase variations
                    continue
                if id_val not in seen_ids:
                    console.print(f"[grey]  '{title}' → {id_val}[/grey]")
                    seen_ids.add(id_val)
                    count += 1
                    if count >= 5:
                        break
        
        return film_ids_dict
        
    except Exception as e:
        console.print(f"[red]Erreur critique lors du chargement des IDs Excel: {e}[/red]")
        import traceback
        traceback.print_exc()
        return {}

# Charger les IDs depuis Excel
real_film_ids = load_excel_ids()

# --- Fonctions d'extraction de contenu ---
def extract_text_from_file(file_path, max_chars=500):
    """Extrait le texte débutant d'un fichier PDF, DOCX ou TXT."""
    ext = file_path.suffix.lower()
    text = ""
    try:
        if ext == '.pdf' and PyPDF2:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f, strict=False) # strict=False pour plus de tolérance
                if len(reader.pages) > 0:
                    # Tenter d'extraire de la première page
                    page_text = reader.pages[0].extract_text()
                    if page_text:
                        text = page_text[:max_chars]
        elif ext == '.docx' and docx:
            doc = docx.Document(file_path)
            full_text = "\n".join([p.text for p in doc.paragraphs])
            text = full_text[:max_chars]
        elif ext == '.txt':
             with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                 text = f.read(max_chars)
    except Exception as e:
        # Log l'erreur sans bloquer le script
        # console.print(f"[grey]Impossible d'extraire le texte de {file_path.name}: {e}[/grey]") # Optionnel: pour debug
        pass
    return text.strip() if text else None

def get_image_metadata(file_path):
    """Extrait les métadonnées EXIF d'une image si possible."""
    metadata = {}
    if not Image or not TAGS: # Vérifier si Pillow est chargé
        return metadata
    try:
        img = Image.open(file_path)
        exif_data = img._getexif()
        if exif_data:
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, tag_id)
                # Décode les bytes si nécessaire et gère les types non sérialisables
                if isinstance(value, bytes):
                    try:
                        value = value.decode('utf-8', errors='replace')
                    except:
                        value = str(value) # Fallback
                elif not isinstance(value, (str, int, float, bool, list, dict, tuple)) and value is not None:
                     value = str(value)
                metadata[tag_name] = value
    except Exception as e:
         # console.print(f"[grey]Impossible d'extraire EXIF de {file_path.name}: {e}[/grey]") # Optionnel: pour debug
        pass
    return metadata

# --- Fin Fonctions d'extraction de contenu ---

def is_film_by_pattern(folder_name):
    """Détecte si un dossier est un film basé sur son nom, sans utiliser l'IA"""
    folder_lower = folder_name.lower()

    # Règle 0: Vérifier directement les cas spéciaux
    special_cases = ["canine", "dogtooth", "kynodontas", "the kid", "1 2 3 bruegel", "123 bruegel"]
    if folder_lower in special_cases:
        return True

    # Règle 1: Format "ANNÉE - TITRE" ou variantes
    if re.match(r'(19|20)\d{2}\s*-\s*', folder_name) or re.match(r'.+\(\s*(19|20)\d{2}\s*\)', folder_name):
        return True

    # Règle 2: Contient le nom d'un film connu (match exact ou flou si activé)
    if process:
        # Recherche floue partielle (plus tolérante)
        match, score = process.extractOne(folder_lower, [f.lower() for f in KNOWN_FILMS], scorer=fuzz.partial_ratio)
        if score >= FUZZY_MATCH_THRESHOLD_FOLDER:
            return True
    else:
        for film in KNOWN_FILMS:
            if film.lower() in folder_lower:
                return True
    
    # Règle 3: Dossiers qui contiennent typiquement des médias de films
    film_indicator_folders = [
        'affiche', 'poster', 'dp', 'dossier de presse', 'press kit',
        'photo', 'still', 'captures', 'screenshots', 'trailer',
        'bande-annonce', 'vf', 'vo', 'restauration', 'restoration'
    ]
    
    for indicator in film_indicator_folders:
        if indicator in folder_lower:
            # Vérifier si c'est un sous-dossier typique d'un film
            parent_dir = Path(folder_name).parent.name.lower()
            if parent_dir not in film_indicator_folders:
                return True
    
    # Règle 4: Termes qui indiquent un NON-film (inchangé)
    non_film_indicators = [
        'collection', 'archives', 'bonus', 'resources', 'brochure', 'press',
        'marketing', 'communication', 'inventaire', 'inventory', 'logos',
        'certificates', 'music cue', 'contracts', 'factures', 'invoices',
        'présentations', 'presentations', 'documents', 'administratifs',
        'revue de presse', 'press coverage', 'general', 'divers', 'various'
    ]

    for indicator in non_film_indicators:
        if indicator in folder_lower:
            return False

    # Par défaut, si on ne sait pas
    return None  # Incertain

async def analyze_folder_with_ai(folder_path):
    """Utiliser l'IA pour déterminer si un dossier est un film, avec des règles préalables"""
    folder_name = folder_path.name
    folder_str = str(folder_path)

    # Vérifier le cache
    cache_key = f"folder:{folder_str}"
    if cache_key in ai_cache:
        return ai_cache[cache_key]

    # Utiliser d'abord la détection par motifs
    pattern_result = is_film_by_pattern(folder_name)
    if pattern_result is not None:
        ai_cache[cache_key] = pattern_result
        # Sauvegarder le cache même pour les décisions basées sur les règles
        # await save_ai_cache() # Fonction à créer si besoin de sauvegarde fréquente
        return pattern_result

    # Pas de client OpenAI ou pas de clé, utiliser une méthode heuristique simple
    if not openai_client:
        # Heuristique simple: si ça ressemble à "ANNÉE - TITRE" ou contient un film connu
        is_film = bool(re.match(r'(19|20)\d{2}\s*-', folder_name)) or \
                  any(film.lower() in folder_name.lower() for film in KNOWN_FILMS)
        ai_cache[cache_key] = is_film
        # await save_ai_cache()
        return is_film

    # Si on arrive ici, pattern_result était None et l'IA est dispo
    try:
        # Limiter le contexte envoyé à l'IA
        subdirs = [d.name for d in folder_path.iterdir() if d.is_dir()][:5]
        subdirs_str = ", ".join(subdirs) if subdirs else "Aucun"

        files_sample = [f.name for f in folder_path.iterdir() if f.is_file()][:5]
        files_str = ", ".join(files_sample) if files_sample else "Aucun"

        prompt = f"""
        Analyse ce dossier et détermine s'il représente UN SEUL film spécifique de Charlie Chaplin ou s'il s'agit d'une collection générale, de ressources, d'archives, ou d'un autre type de dossier non spécifique à un film unique.

        Nom du dossier: {folder_name}
        Sous-dossiers (échantillon): {subdirs_str}
        Fichiers (échantillon): {files_str}

        Liste de films connus (pour référence): {', '.join(KNOWN_FILMS[:5])}...

        Réponds IMPÉRATIVEMENT par 'FILM' si c'est un dossier pour un film spécifique, ou 'NON_FILM' dans tous les autres cas (collection, ressources, administration, etc.). Ne donne aucune autre explication.
        """

        response = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo", # Ou un modèle plus performant si nécessaire
            messages=[
                {"role": "system", "content": "Tu es un expert en archivage de films. Tu détermines si un dossier contient les éléments d'un film spécifique ou des ressources diverses/générales. Réponds uniquement 'FILM' ou 'NON_FILM'."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=10,
            temperature=0.1
        )

        result = response.choices[0].message.content.strip().upper()
        is_film = result == 'FILM'

        # Sauvegarder dans le cache
        ai_cache[cache_key] = is_film
        await save_ai_cache() # Sauvegarde après appel IA

        return is_film

    except Exception as e:
        console.print(f"[yellow]Erreur lors de l'analyse IA du dossier {folder_name}: {e}[/yellow]")
        # Fallback à une méthode heuristique si l'IA échoue
        is_film = bool(re.match(r'(19|20)\d{2}\s*-', folder_name)) or \
                  any(film.lower() in folder_name.lower() for film in KNOWN_FILMS)
        ai_cache[cache_key] = is_film
        # await save_ai_cache() # Sauvegarde même en cas d'erreur IA
        return is_film

async def save_ai_cache():
     """Sauvegarde le cache AI dans le fichier JSON."""
     try:
         with open(CACHE_FILE, 'w', encoding='utf-8') as f:
             json.dump(ai_cache, f, indent=2, ensure_ascii=False)
     except Exception as e:
         console.print(f"[yellow]Impossible de sauvegarder le cache d'IA: {e}[/yellow]")
async def detect_film_structure():
    """Analyser la structure des dossiers pour détecter les films dans un grand catalogue"""
    global next_id
    console.print("[blue]Analyse de la structure des dossiers...[/blue]")

    film_folders = []
    film_paths = {}
    title_to_id = {}
    
    # AMÉLIORATION: Détection globale du type de catalogue
    # Analyser les noms des dossiers pour comprendre le style de nommage prédominant
    dossier_patterns = []
    for root, dirs, _ in os.walk(SOURCE_DIR):
        for dir_name in dirs:
            dossier_patterns.append(dir_name)
            if len(dossier_patterns) >= 100:  # Limiter pour performance
                break
        if len(dossier_patterns) >= 100:
            break
    
    # Analyser les motifs prédominants
    year_prefix_count = sum(1 for d in dossier_patterns if re.match(r'^(19|20)\d{2}\s*-\s*.+', d))
    year_suffix_count = sum(1 for d in dossier_patterns if re.match(r'.+\(\s*(19|20)\d{2}\s*\)', d))
    
    console.print(f"[grey]Analyse des motifs: {year_prefix_count} dossiers avec année en préfixe, {year_suffix_count} avec année en suffixe[/grey]")
    
    # Vérifier si le dossier source lui-même pourrait être un film
    source_dir_name = SOURCE_DIR.name.lower()
    source_dir_is_film = False
    source_film_id = None
    
    # Rechercher dans real_film_ids si le dossier source correspond à un film connu
    for title, id_val in real_film_ids.items():
        if isinstance(title, str):  # S'assurer que c'est une chaîne
            title_lower = title.lower()
            # Recherche exacte ou approximative
            if title_lower == source_dir_name or (process and fuzz.ratio(title_lower, source_dir_name) > FUZZY_MATCH_THRESHOLD_FOLDER):
                source_dir_is_film = True
                source_film_id = id_val
                film_name = title
                console.print(f"[green]Dossier source '{SOURCE_DIR.name}' identifié comme le film '{title}' (ID: {id_val})[/green]")
                break
    
    # Si le dossier source est un film, l'ajouter directement
    if source_dir_is_film and source_film_id:
        film_info = {
            'id': source_film_id,
            'name': film_name,
            'path': SOURCE_DIR,
            'match_score': 100,
            'id_source': 'Excel'
        }
        film_folders.append(film_info)
        film_paths[str(SOURCE_DIR)] = source_film_id
        title_to_id[film_name] = source_film_id
        DETECTED_FILMS[source_film_id] = film_name
    
    # Récupérer tous les sous-dossiers
    all_subdirs = []
    for root, dirs, _ in os.walk(SOURCE_DIR):
        for dir_name in dirs:
            dir_path = Path(root) / dir_name
            if not any(ignore in str(dir_path) for ignore in IGNORE_PATTERNS):
                all_subdirs.append(dir_path)
    
    # Trier pour prioriser les dossiers avec années (qui sont souvent des films)
    all_subdirs.sort(key=lambda p: 0 if re.match(r'^(19|20)\d{2}\s*-\s*.+', p.name) else 1)
    
    # AMÉLIORATION: Traitement par lot pour des performances optimales
    with Progress() as progress:
        task = progress.add_task("Traitement TITRES", total=len(all_subdirs))
        
        for folder in all_subdirs:
            folder_name = folder.name
            folder_name_lower = folder_name.lower()
            
            # Si ce dossier est déjà dans un dossier de film identifié, continuer
            parent_is_film = False
            current_path = folder.parent
            while current_path != SOURCE_DIR and current_path != current_path.parent:
                if str(current_path) in film_paths:
                    parent_is_film = True
                    break
                current_path = current_path.parent
            
            # Sauter si le dossier parent est déjà identifié comme un film
            if parent_is_film:
                progress.advance(task)
                continue
            
            # 1. Recherche dans les ID Excel directement par nom
            film_id = None
            film_name = None
            
            for title, id_val in real_film_ids.items():
                if isinstance(title, str) and title.lower() == folder_name_lower:
                    film_id = id_val
                    film_name = title
                    match_method = "correspondance exacte Excel"
                    break
            
            # 2. Si non trouvé, utiliser matching flou avec les titres Excel
            if not film_id and process:
                best_match = None
                best_score = 0
                
                for title, id_val in real_film_ids.items():
                    if not isinstance(title, str):
                        continue
                    
                    score = fuzz.ratio(title.lower(), folder_name_lower)
                    if score > FUZZY_MATCH_THRESHOLD_FOLDER and score > best_score:
                        best_score = score
                        best_match = (title, id_val)
                
                if best_match:
                    film_name, film_id = best_match
                    match_method = f"match flou Excel (score: {best_score})"
            
            # 3. Analyser le contenu du dossier pour indices supplémentaires
            if not film_id:
                try:
                    # Regarder les sous-dossiers et fichiers pour indices
                    subdirs = [d.name for d in folder.iterdir() if d.is_dir()][:5]
                    files = [f.name for f in folder.iterdir() if f.is_file()][:5]
                    
                    # Recherche de mots-clés liés aux films dans les noms
                    media_keywords = [
                        'affiche', 'poster', 'dp', 'dossier de presse', 'photo', 
                        'still', 'trailer', 'bande-annonce', 'press kit'
                    ]
                    
                    # Si le dossier contient plusieurs sous-dossiers typiques d'un film
                    media_folder_count = sum(1 for s in subdirs if any(k in s.lower() for k in media_keywords))
                    
                    if media_folder_count >= 2:
                        # Ce dossier contient probablement un film, chercher par analyse du nom
                        for title, id_val in real_film_ids.items():
                            if not isinstance(title, str):
                                continue
                                
                            # Essayer d'extraire des mots-clés du nom du dossier
                            folder_words = set(re.findall(r'\b\w+\b', folder_name_lower))
                            title_words = set(re.findall(r'\b\w+\b', title.lower()))
                            
                            # Si au moins 50% des mots importants correspondent
                            common_words = folder_words.intersection(title_words)
                            if len(common_words) >= 1 and len(common_words) >= len(title_words) * 0.5:
                                film_id = id_val
                                film_name = title
                                match_method = f"analyse de contenu et correspondance partielle"
                                break
                except Exception:
                    pass  # Ignorer les erreurs d'accès aux sous-dossiers
            
            # 4. MODIFICATION: Ne plus générer d'ID pour les films non répertoriés
            # Nous n'assignons plus d'ID généré aux dossiers qui semblent être des films
            # Les fichiers de ces dossiers iront dans "Inconnu" si on ne peut pas les associer à un ID connu
            
            # Si un film a été identifié (uniquement ceux avec ID Excel), l'ajouter aux structures
            if film_id and film_name:
                console.print(f"[grey]Film détecté: '{folder_name}' → '{film_name}' (ID: {film_id}) via {match_method}[/grey]")
                
                # Éviter les doublons dans title_to_id
                if film_name not in title_to_id:
                    title_to_id[film_name] = film_id
                    DETECTED_FILMS[film_id] = film_name
                
                film_info = {
                    'id': film_id,
                    'name': film_name,
                    'path': folder,
                    'match_score': 100 if "correspondance exacte" in match_method else 90,
                    'id_source': 'Excel' if film_id in real_film_ids.values() else 'Généré'
                }
                
                film_folders.append(film_info)
                film_paths[str(folder)] = film_id
            
            progress.advance(task)
    
    # Afficher un résumé de la détection
    if film_folders:
        unique_films = len(set(f['id'] for f in film_folders))
        console.print(f"[green]Détection de {unique_films} films uniques terminée.[/green]")
        
        # Regrouper les dossiers par film pour un affichage plus compact
        film_id_to_folders = {}
        for film in film_folders:
            if film['id'] not in film_id_to_folders:
                film_id_to_folders[film['id']] = {
                    'name': film['name'],
                    'folders': []
                }
            film_id_to_folders[film['id']]['folders'].append(film['path'].name)
        
        # Afficher les associations de manière plus compacte
        for film_id, info in sorted(film_id_to_folders.items()):
            folders_str = ", ".join(info['folders'][:5])
            if len(info['folders']) > 5:
                folders_str += f", ... ({len(info['folders']) - 5} autres)"
            console.print(f"[grey]{info['name']} (ID: {film_id}) → {folders_str}[/grey]")
    else:
        console.print("[yellow]Attention: Aucun film n'a été détecté. Vérifier les règles de détection.[/yellow]")
    
    return film_folders, film_paths

def should_ignore_file(file_path):
    """Vérifier si un fichier doit être ignoré."""
    file_name = file_path.name
    file_str = str(file_path)

    # Vérifier les motifs à ignorer dans le nom ou chemin complet
    for pattern in IGNORE_PATTERNS:
        if pattern in file_name or pattern in file_str:
            return True, "Pattern ignoré"

    # Vérifier l'extension
    ext = file_path.suffix.lower()
    if not ext: # Fichier sans extension (souvent problématique)
        return True, "Aucune extension"
    if ext not in VALID_EXTENSIONS:
        return True, f"Extension non valide ({ext})"

    # Vérifier si c'est un fichier "fantôme" de macOS (commence par ._)
    if file_name.startswith("._"):
        return True, "Fichier macOS '._'"

    return False, None # Ne pas ignorer
async def determine_film_for_file(file_path, film_paths):
    """Déterminer le film associé à un fichier avec alternatives externes et éviter les mauvaises correspondances"""
    file_str_lower = str(file_path).lower()
    file_name_lower = file_path.name.lower()
    
    # Liste des termes/films à traiter avec une attention particulière
    problematic_matches = {
        "1479": ["amputee", "amputation"],  # ID de "AMPUTEE (THE)"
    }
    
    # Stratégie 1: Le fichier est DANS un dossier de film déjà identifié
    current_path = file_path.parent
    while current_path != SOURCE_DIR and current_path != current_path.parent:
        path_str = str(current_path)
        if path_str in film_paths:
            film_id = film_paths[path_str]
            
            # Vérification supplémentaire pour les cas problématiques
            if film_id in problematic_matches:
                keywords = problematic_matches[film_id]
                
                # Si c'est AMPUTEE (ID 1479) mais que le chemin ou le nom contient "kid" ou "gold rush",
                # ne pas attribuer cet ID
                if film_id == "1479" and any(term in file_str_lower for term in ["kid", "gold rush", "ruée", "or"]):
                    # Chercher si un autre film serait plus approprié
                    for title, id_val in real_film_ids.items():
                        if isinstance(title, str) and len(title) > 3:
                            title_lower = title.lower()
                            if ("kid" in title_lower and "kid" in file_str_lower) or \
                               ("gold" in title_lower and "gold" in file_str_lower) or \
                               ("ruée" in title_lower and "ruée" in file_str_lower):
                                return id_val
                    
                    # Si on n'a pas trouvé de meilleur match, ne pas retourner d'ID
                    return None
                
                # Vérifier si le fichier contient vraiment un mot-clé du film problématique
                if not any(keyword in file_str_lower for keyword in keywords):
                    # Le fichier ne contient aucun mot-clé du film, on n'attribue pas cet ID
                    return None
            
            return film_id
        current_path = current_path.parent
    
    # Stratégie 2: Recherche directe dans tous les titres connus (principaux et alternatifs)
    for title, film_id in real_film_ids.items():
        if isinstance(title, str) and len(title) > 3:  # Ignorer les titres trop courts
            title_lower = title.lower()
            
            # Vérifier si le titre apparaît dans le nom du fichier ou le chemin
            if title_lower in file_name_lower or title_lower in file_str_lower:
                # Vérification supplémentaire pour les cas problématiques
                if film_id in problematic_matches and not any(keyword in file_str_lower for keyword in problematic_matches[film_id]):
                    continue
                
                # Cas spécifiques pour THE KID vs AMPUTEE
                if "kid" in file_str_lower and film_id == "1479":  # ID d'AMPUTEE
                    # Chercher un meilleur match pour "kid"
                    for alt_title, alt_id in real_film_ids.items():
                        if isinstance(alt_title, str) and "kid" in alt_title.lower():
                            return alt_id
                
                return film_id
    
    # Stratégie 3: Matching flou si disponible, avec prudence accrue
    if process:
        # Préparer une liste de titres à comparer
        titles = [t for t in real_film_ids.keys() if isinstance(t, str) and len(t) > 3]
        
        # D'abord essayer avec le nom du fichier
        best_matches = process.extractBests(file_name_lower, titles, scorer=fuzz.partial_ratio, score_cutoff=FUZZY_MATCH_THRESHOLD_FILE)
        if best_matches:
            best_title = best_matches[0][0]
            film_id = real_film_ids[best_title]
            
            # Vérification supplémentaire pour éviter les mauvaises correspondances
            if film_id in problematic_matches:
                # Si c'est THE KID ou GOLD RUSH, ne pas attribuer l'ID d'AMPUTEE (THE)
                if film_id == "1479" and any(term in file_str_lower for term in ["kid", "gold rush", "ruée", "or"]):
                    return None
                
                # Vérifier si le fichier contient vraiment un mot-clé du film problématique
                if not any(keyword in file_str_lower for keyword in problematic_matches[film_id]):
                    # Le fichier ne contient aucun mot-clé du film, on n'attribue pas cet ID
                    return None
            
            return film_id
        
        # Ensuite avec le chemin complet, mais avec une vérification plus stricte
        best_matches = process.extractBests(file_str_lower, titles, scorer=fuzz.partial_ratio, score_cutoff=FUZZY_MATCH_THRESHOLD_FILE)
        if best_matches:
            best_title = best_matches[0][0]
            film_id = real_film_ids[best_title]
            
            # Vérification supplémentaire pour les cas problématiques
            if film_id in problematic_matches:
                # Si c'est AMPUTEE mais que le chemin contient "kid" ou "gold rush", ne pas attribuer cet ID
                if film_id == "1479" and any(term in file_str_lower for term in ["kid", "gold rush", "ruée", "or"]):
                    return None
                
                # Vérifier si le fichier contient vraiment un mot-clé du film problématique
                if not any(keyword in file_str_lower for keyword in problematic_matches[film_id]):
                    # Le fichier ne contient aucun mot-clé du film, on n'attribue pas cet ID
                    return None
            
            return film_id
    
    # Aucun film identifié
    return None

def categorize_file_by_rules(file_path):
    """Catégoriser un fichier selon des règles améliorées basées sur nom/chemin/extension."""
    file_name_lower = file_path.name.lower()
    # Utiliser le chemin relatif pour éviter les faux positifs dus au nom du dossier source
    try:
        relative_path_str = str(file_path.relative_to(SOURCE_DIR)).lower()
    except ValueError: # Si le fichier n'est pas dans SOURCE_DIR
        relative_path_str = str(file_path).lower()

    ext = file_path.suffix.lower()

    # Règles spécifiques prioritaires pour les affiches
    if any(term in file_name_lower or term in relative_path_str for term in [
        'affiche', 'poster', ' aff ', '_aff_', 'movie poster', 'one sheet', 'locandina', 'cartel'
    ]):
        if ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.gif', '.bmp', '.pdf']:
            return 'AfficheS'

    # Règles spécifiques pour dossier de presse - AJOUT DE NOUVELLES RÈGLES
    if any(term in file_name_lower or term in relative_path_str for term in [
        'dossier de presse', 'press kit', 'dp_', 'pressbook', 'press book', 'press release', 
        'communiqué de presse', 'press materials', 'media kit', 'electronic press kit', 'epk',
        'production notes', '/dp/', '/dp_', '_dp_'
    ]):
        # Présence du terme exact "DP" comme mot entier
        if re.search(r'\bdp\b', file_name_lower) or re.search(r'\bdp\b', relative_path_str):
            return 'Dossier de presse'
        
        if ext in ['.pdf', '.doc', '.docx', '.zip', '.rar', '.txt', '.rtf']:
            return 'Dossier de presse'

    # Règles spécifiques pour revue de presse - AJOUT DE NOUVELLES RÈGLES
    if any(term in file_name_lower or term in relative_path_str for term in [
        'revue de presse', 'press review', ' article', 'critique', 'review', 'clipping',
        'presse', 'press coverage', 'news clip', 'newspaper', 'magazine', 'quote', 'citation',
        'quotes', 'citations', 'press quote', 'critics', 'media coverage', 'interview',
        'recension', 'crítica', 'journal', 'publication'
    ]):
        if ext in ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.txt', '.rtf']:
            return 'Revue de presse'

    # Règles spécifiques pour photos
    if any(term in file_name_lower or term in relative_path_str for term in [
        'photo', 'image', 'still', ' hd ', '_hd_', ' highres', ' high res', ' scene ', 
        'screenshot', 'capture', 'frame', 'photo hd', 'promotional', 'promo photo', 
        'publicity', 'photo_', '_photo', ' jpg', '.jpeg'
    ]):
        if ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.gif']:
            return 'Photo HD'

    # Autres catégories moins prioritaires
    if any(term in file_name_lower or term in relative_path_str for term in [
        'facture', 'invoice', 'billing', 'payment', 'receipt', 'financial'
    ]):
        if ext in ['.pdf', '.xlsx', '.xls', '.doc', '.docx', '.csv']:
            return 'Factures'
            
    if any(term in file_name_lower or term in relative_path_str for term in [
        'contrat', 'agreement', 'nda', 'contract', 'legal', 'license', 'rights', 
        'deal memo', 'terms'
    ]):
        if ext in ['.pdf', '.doc', '.docx']:
            return 'Contrats'
            
    if any(term in file_name_lower or term in relative_path_str for term in [
        'présentation', 'presentation', 'slides', 'deck', 'powerpoint', 'keynote'
    ]):
        if ext in ['.pptx', '.ppt', '.pdf', '.key']:
            return 'Présentations'
            
    if any(term in file_name_lower or term in relative_path_str for term in [
        'administratif', 'admin', 'document', 'paperwork', 'form', 'certificate', 
        'certification', 'visa', 'official'
    ]):
        if ext in ['.pdf', '.doc', '.docx', '.txt', '.xls', '.xlsx']:
            return 'Documents administratifs'


    # Catégorisation par défaut basée sur l'extension si aucune règle n'a matché
    if ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.gif']:
        return 'Photo HD' # Par défaut pour les images non identifiées autrement
    if ext in ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.mpg', '.mpeg', '.webm']:
        return 'Médias (audio/vidéo)'
    if ext in ['.mp3', '.wav', '.aac', '.ogg', '.flac', '.m4a']:
        return 'Médias (audio/vidéo)'
    if ext in ['.pdf']:
        return 'Divers' # Laisser l'analyse de contenu/IA décider
    if ext in ['.docx', '.doc']:
        return 'Divers'
    if ext in ['.pptx', '.ppt']:
        return 'Présentations'
    if ext in ['.xlsx', '.xls', '.csv']:
        return 'Divers'
    if ext in ['.txt']:
        return 'Divers'

    # Catégorie par défaut ultime
    return 'Divers'

async def categorize_file(file_path):
    """Déterminer la catégorie d'un fichier avec analyse de contenu améliorée"""
    file_name = file_path.name
    cache_key = f"category:{str(file_path)}" # Utiliser le chemin complet pour le cache

    if cache_key in ai_cache:
        return ai_cache[cache_key]

    # 1. Catégorisation par règles (rapide)
    category = categorize_file_by_rules(file_path)

    # 2. Affinage par contenu textuel pour les documents
    extracted_text = None
    if category == 'Divers' and file_path.suffix.lower() in ['.pdf', '.docx', '.txt', '.doc', '.rtf']:
        extracted_text = extract_text_from_file(file_path, max_chars=1500)  # Plus de contexte
        if extracted_text:
            text_lower = extracted_text.lower()
            
            # Mots-clés plus précis pour les catégories ambiguës
            
            # Vérification pour Dossier de presse
            dp_keywords = [
                'dossier de presse', 'press kit', 'synopsis', 'fiche technique', 
                'biographie du réalisateur', 'directeur de la photographie',
                'cast and crew', 'casting', 'production notes', 'présentation du film',
                'about the film', 'director statement', 'note d\'intention'
            ]
            if any(keyword in text_lower for keyword in dp_keywords):
                category = 'Dossier de presse'
            
            # Vérification pour Revue de presse
            rp_keywords = [
                'critique', 'review', 'article', 'revue de presse', 'paru dans', 
                'published in', 'quotation', 'citation', 'press quote', 'press review',
                'extrait de presse', 'journal', 'magazine', 'newspaper', 'media review'
            ]
            if any(keyword in text_lower for keyword in rp_keywords):
                category = 'Revue de presse'
            
            # Autres catégories
            if 'facture' in text_lower or 'invoice' in text_lower: 
                category = 'Factures'
            elif 'contrat' in text_lower or 'agreement' in text_lower or 'contract' in text_lower: 
                category = 'Contrats'
            elif 'présentation' in text_lower or 'slides' in text_lower: 
                category = 'Présentations'

    # 3. Affinage par métadonnées EXIF (si image)
    extracted_metadata = None
    if category in ['Photo HD', 'Divers'] and Image and file_path.suffix.lower() in ['.jpg', '.jpeg', '.tif', '.tiff']:
        extracted_metadata = get_image_metadata(file_path)
        if extracted_metadata:
            # Chercher des indices dans les métadonnées
            desc = str(extracted_metadata.get('ImageDescription', '')).lower()
            keywords = str(extracted_metadata.get('Keywords', '')).lower()
            if 'affiche' in desc or 'poster' in desc or 'affiche' in keywords or 'poster' in keywords:
                category = 'AfficheS'

    # 4. Utilisation de l'IA (si disponible et catégorie toujours ambiguë)
    should_use_ai = openai_client and (category == 'Divers' or category not in MEDIA_LABELS)

    if should_use_ai:
        try:
            ext = file_path.suffix.lower()
            folder_path_rel = str(file_path.parent.relative_to(SOURCE_DIR))

            # Préparer le contexte pour l'IA
            context_info = f"Extension: {ext}\nNom du fichier: {file_path.name}\nChemin relatif: {folder_path_rel}"
            if extracted_text:
                context_info += f"\nExtrait texte (max 300 chars): {extracted_text[:300]}..."
            if extracted_metadata:
                meta_sample = {k: v for k, v in extracted_metadata.items() if k in ['ImageDescription', 'Keywords', 'Artist']}
                if meta_sample:
                    context_info += f"\nMetadonnées image: {json.dumps(meta_sample, ensure_ascii=False)}"

            # Prompt amélioré pour l'IA avec emphasis sur les cas spéciaux
            prompt = f"""
            Classe ce fichier dans la catégorie la plus appropriée parmi la liste fournie. Analyse le nom, le chemin, l'extension et les extraits de contenu/métadonnées.

            Contexte:
            {context_info}

            RÈGLES IMPORTANTES: 
            - Les termes comme "quotes" et "citation" indiquent une REVUE DE PRESSE
            - Les termes comme "DP", "press kit" ou "dossier de presse" indiquent un DOSSIER DE PRESSE
            - Pour les affiches de film, utilise la catégorie AFFICHES
            - Si le fichier contient des images de film ou des photos promotionnelles, c'est une PHOTO HD

            Choisis UNE SEULE catégorie parmi:
            - AfficheS (Affiches de film, posters promotionnels)
            - Photo HD (Photos de plateau, portraits, images promotionnelles)
            - Dossier de presse (Documents pour la presse: communiqués, synopsis, biographies)
            - Revue de presse (Articles publiés, critiques, interviews, citations)
            - Documents administratifs (Documents internes, formulaires, certificats)
            - Factures (Factures, notes de frais, paiements)
            - Contrats (Contrats, accords légaux, licences)
            - Présentations (Diaporamas, présentations type PowerPoint)
            - Médias (audio/vidéo) (Fichiers vidéo ou audio)
            - Divers (Uniquement si aucune autre catégorie ne correspond)

            Réponds UNIQUEMENT avec le nom exact de la catégorie choisie. Pas d'explication.
            """

            response = await openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"Tu es un archiviste expert. Classifie précisément les fichiers selon les règles données."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=30,
                temperature=0.2
            )

            ai_category = response.choices[0].message.content.strip()

            # Vérifier si la réponse de l'IA est une catégorie valide
            if ai_category in ALL_CATEGORIES:
                category = ai_category
            else:
                # Garder la catégorie précédente si l'IA répond n'importe quoi
                pass

        except Exception as e:
            console.print(f"[yellow]Erreur lors de la catégorisation IA pour {file_name}: {e}[/yellow]")
            # Garder la catégorie déterminée avant l'IA

    # Sauvegarder la décision finale dans le cache
    ai_cache[cache_key] = category
    return category

def sanitize_filename(filename):
    """Nettoyer un nom de fichier pour éviter les caractères invalides."""
    # Caractères généralement problématiques sur différents OS
    invalid_chars = r'[/\\:*\?"<>|]'
    filename = re.sub(invalid_chars, '_', filename)

    # Remplacer les espaces multiples par un seul
    filename = re.sub(r'\s+', ' ', filename).strip()

    # Limiter la longueur totale (nom + extension) - Attention aux limites spécifiques de l'OS/filesystem
    max_len = 240 # Limite prudente
    if len(filename) > max_len:
        name_part, ext_part = os.path.splitext(filename)
        # Couper le nom, pas l'extension
        available_len = max_len - len(ext_part) - 1 # -1 pour le point
        if available_len < 1: # Si l'extension elle-même est trop longue
            filename = filename[:max_len] # Couper brutalement
        else:
            filename = name_part[:available_len] + ext_part

    return filename

def move_file(file_path, category, film_id=None, media_type_label=None):
    """Déplacer et renommer un fichier avec gestion des erreurs et convention de nommage."""
    try:
        # Dossier film = nom du film si connu avec certitude, sinon "Inconnu"
        film_folder = "Inconnu"
        
        # Vérifier explicitement que l'ID existe dans DETECTED_FILMS (films identifiés avec certitude)
        if film_id in DETECTED_FILMS:
            film_folder = sanitize_filename(DETECTED_FILMS[film_id])
        
        base_target_dir = DESTINATION_DIR / film_folder

        # Créer sous-dossier selon type (ex: '1_123')
        if category in MEDIA_LABELS and film_id and media_type_label and film_folder != "Inconnu":
            sub_dir_name = f"{media_type_label}_{film_id}"
            target_dir = base_target_dir / sub_dir_name
        else:
            target_dir = base_target_dir / category

        target_dir.mkdir(parents=True, exist_ok=True)

        original_name = file_path.name
        new_name = sanitize_filename(original_name)

        target_path = target_dir / new_name

        counter = 1
        base, ext = os.path.splitext(new_name)
        while target_path.exists():
            new_name = f"{base}_copy{counter}{ext}"
            target_path = target_dir / new_name
            counter += 1
            if counter > 100:
                raise OSError("Trop de tentatives de renommage pour éviter les doublons.")

        shutil.copy2(str(file_path), str(target_path))
        return target_path, None

    except Exception as e:
        console.print(f"[red]Erreur lors du déplacement/renommage de {file_path.name} vers {category}: {e}[/red]")
        return None, str(e)


async def process_file(file_path, film_paths, detected_films_map):
    """Traiter un seul fichier : ignorer, catégoriser, déterminer film, déplacer, logger."""
    start_process_time = time.monotonic()
    log_entry = {'original_path': file_path, 'status': 'unknown'}

    try:
        # 1. Vérifier si le fichier doit être ignoré
        ignore, reason = should_ignore_file(file_path)
        if ignore:
            log_entry.update({'status': 'ignored', 'reason': reason})
            return log_entry # Ne pas traiter plus loin

        # 2. Vérifier si le fichier existe réellement
        if not file_path.exists():
            log_entry.update({'status': 'error', 'reason': 'Fichier source introuvable'})
            return log_entry

        # 3. Déterminer la catégorie (règles, contenu, IA)
        category = await categorize_file(file_path)
        log_entry['category'] = category

        # 4. Déterminer le film associé (si possible)
        film_id = await determine_film_for_file(file_path, film_paths)
        
        # Vérification supplémentaire: s'assurer que l'ID existe dans les films détectés avec certitude
        if film_id and film_id not in detected_films_map:
            # Si l'ID existe dans real_film_ids mais pas dans detected_films_map, 
            # c'est une correspondance incertaine, on la rejette
            film_id = None
            log_entry['reason'] = "ID trouvé mais ne correspond pas à un film détecté avec certitude"
        
        film_name = detected_films_map.get(film_id, None) if film_id else None
        log_entry['film_id'] = film_id
        log_entry['film_name'] = film_name

        # 5. Déplacer et renommer
        media_type_label = MEDIA_LABELS.get(category) # Obtient '1', '2', etc. si c'est une catégorie média principale

        # Si la catégorie est une des principales mais qu'on n'a pas trouvé de film_id,
        # ou si l'ID n'est pas dans detected_films_map (correspondance incertaine),
        # le fichier ira dans le dossier "Inconnu"
        if not film_id or film_id not in detected_films_map:
            if category in MEDIA_LABELS:
                media_type_label = None  # Pas de label de type média
                log_entry['reason'] = f"Catégorie {category} sans ID film confirmé, ira dans Inconnu/{category}"

        new_path, error_reason = move_file(file_path, category, film_id, media_type_label)

        if new_path:
            log_entry.update({'status': 'success', 'new_path': new_path})
        else:
            log_entry.update({'status': 'error', 'reason': f"Échec du déplacement: {error_reason}"})

        return log_entry

    except Exception as e:
        console.print(f"[bold red]Erreur inattendue lors du traitement de {file_path.name}: {e}[/bold red]")
        import traceback
        traceback.print_exc() # Afficher la trace complète pour le debug
        log_entry.update({'status': 'error', 'reason': f"Erreur inattendue: {e}"})
        return log_entry
    finally:
        # Enregistrer l'événement dans le log CSV, quel que soit le résultat
        log_file_event(
            original_path=log_entry['original_path'],
            status=log_entry['status'],
            film_id=log_entry.get('film_id'),
            film_name=log_entry.get('film_name'),
            category=log_entry.get('category'),
            new_path=log_entry.get('new_path'),
            reason=log_entry.get('reason')
        )

async def process_batch(batch, film_paths, detected_films_map):
    """Traiter un lot de fichiers en parallèle."""
    tasks = [process_file(file_path, film_paths, detected_films_map) for file_path in batch]
    # Utiliser gather avec return_exceptions=True pour ne pas arrêter tout le batch si un fichier plante
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Traiter les exceptions potentielles retournées par gather
    final_results = []
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            file_path = batch[i]
            console.print(f"[bold red]Erreur critique non gérée dans process_file pour {file_path.name}: {res}[/bold red]")
            # Logger cette erreur critique spécifique
            log_file_event(original_path=file_path, status='critical_error', reason=str(res))
            final_results.append({'original_path': file_path, 'status': 'critical_error', 'reason': str(res)}) # Ajouter une entrée d'erreur
        else:
            final_results.append(res) # C'était un résultat normal (dict)
    return final_results

async def main():
    """Fonction principale améliorée."""
    console.print("\n[bold blue]===== TRIEUR DE MÉDIAS INTELLIGENT (v2) =====")
    start_time = time.time()

    # Initialiser le logger CSV
    setup_csv_logger()

    # Étape 1: Analyser la structure pour détecter les films
    film_folders, film_paths = await detect_film_structure()

    # Créer une map ID -> Nom pour accès facile (utilisée dans le logging)
    detected_films_map = {f['id']: f['name'] for f in film_folders}

    # Afficher les films détectés
    if film_folders:
        film_table = Table(title="Films Détectés")
        film_table.add_column("Nom du Dossier Film", style="cyan", no_wrap=True)
        film_table.add_column("ID Assigné", style="yellow")
        film_table.add_column("Source ID", style="magenta") # Excel ou Généré
        for film in film_folders:
            film_table.add_row(film['name'], film['id'], film['id_source'])
        console.print(film_table)
    else:
        console.print("[yellow]Aucun dossier de film spécifique n'a été détecté.[/yellow]")
        # On peut continuer, mais les fichiers iront probablement dans 'Divers' ou nécessiteront une association manuelle

    # Étape 2: Collecter tous les fichiers à traiter
    file_list = []
    console.print(f"[blue]Analyse des fichiers dans '{SOURCE_DIR}'...[/blue]")
    # Utiliser rglob pour une collecte plus directe et compatible Pathlib
    for item in SOURCE_DIR.rglob('*'):
         if item.is_file():
             file_list.append(item)

    total_files = len(file_list)
    console.print(f"[blue]Nombre total de fichiers trouvés:[/blue] {total_files}")

    if not file_list:
        console.print("[yellow]Aucun fichier à traiter dans le dossier source.[/yellow]")
        if csv_logger: csv_logger.close()
        return

    # Statistiques détaillées
    stats = {
        'total': total_files,
        'success': 0,
        'ignored': 0,
        'errors': 0,
        'critical_errors': 0,
        'categories': {cat: 0 for cat in ALL_CATEGORIES},
        'films': {film_id: {'name': film_info, 'files': 0} for film_id, film_info in detected_films_map.items()}
    }
    stats['films'][None] = {'name': 'Non Associé / Divers', 'files': 0}


    # Traiter les fichiers par lots avec barre de progression
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        TimeElapsedColumn()
    ) as progress:
        task = progress.add_task("[cyan]Tri des fichiers...", total=total_files)

        # Taille de lot dynamique (plus petit si l'IA est utilisée fréquemment?)
        # Pour l'instant, gardons une taille fixe raisonnable
        batch_size = 10 # Augmenté car process_file gère les exceptions
        processed_count = 0

        for i in range(0, total_files, batch_size):
            batch = file_list[i:min(i+batch_size, total_files)]
            # Passer la map ID->Nom à process_batch pour le logging
            results = await process_batch(batch, film_paths, detected_films_map)

            # Mettre à jour les statistiques et la barre de progression
            for result in results:
                 processed_count += 1
                 status = result['status']
                 category = result.get('category')
                 film_id = result.get('film_id') # Peut être None

                 if status == 'success':
                     stats['success'] += 1
                     if category in stats['categories']:
                         stats['categories'][category] += 1
                     if film_id in stats['films']: # Gère le cas film_id=None
                          stats['films'][film_id]['files'] += 1
                     else: # Cas où un film_id est trouvé mais pas dans la détection initiale (peu probable)
                          stats['films'][film_id] = {'name': f'Film Inconnu #{film_id}', 'files': 1}
                 elif status == 'ignored':
                     stats['ignored'] += 1
                 elif status == 'error':
                     stats['errors'] += 1
                     # Log l'erreur aussi dans la console pour visibilité
                     # console.print(f"[yellow]Erreur traitée pour {result['original_path'].name}: {result.get('reason')}[/yellow]")
                 elif status == 'critical_error':
                     stats['critical_errors'] += 1
                 progress.update(task, completed=processed_count, description=f"[cyan]Tri: {result['original_path'].name}")
            # Petite pause pour éviter de saturer l'API ou le disque ?
            await asyncio.sleep(0.05)

    # Sauvegarde finale du cache IA
    await save_ai_cache()

    # Afficher le résumé
    elapsed_time = time.time() - start_time
    console.print(f"\n[bold green]Traitement terminé en {elapsed_time:.2f} secondes ![/bold green]")
    console.print(Panel(
        f"[green]Succès: {stats['success']}[/green]\n"
        f"[yellow]Ignorés: {stats['ignored']}[/yellow]\n"
        f"[red]Erreurs gérées: {stats['errors']}[/red]\n"
        f"[bold red]Erreurs critiques: {stats['critical_errors']}[/bold red]\n"
        f"Total traité: {stats['success'] + stats['errors'] + stats['critical_errors']}\n"
        f"Fichiers analysés: {total_files}",
        title="Résumé du Traitement",
        border_style="blue"
    ))

    # Afficher les statistiques par film
    film_stats_table = Table(title="Statistiques par Film")
    film_stats_table.add_column("ID Film", style="yellow")
    film_stats_table.add_column("Nom du Film / Catégorie", style="cyan", no_wrap=True)
    film_stats_table.add_column("Fichiers Associés", style="green", justify="right")

    # Trier les films par nom pour l'affichage, mettre 'Non Associé' à la fin
    sorted_films = sorted(stats['films'].items(), key=lambda item: (item[0] is None, item[1]['name']))

    for film_id, film_info in sorted_films:
        if film_info['files'] > 0:
            display_id = film_id if film_id is not None else "[grey]N/A[/grey]"
            film_stats_table.add_row(display_id, film_info['name'], str(film_info['files']))
    if film_stats_table.row_count > 0:
         console.print(film_stats_table)

    # Afficher les statistiques par catégorie finale
    cat_stats_table = Table(title="Statistiques par Catégorie Finale")
    cat_stats_table.add_column("Catégorie", style="magenta")
    cat_stats_table.add_column("Nombre de Fichiers", style="green", justify="right")

    sorted_categories = sorted(stats['categories'].items(), key=lambda item: item[0]) # Tri par nom de catégorie

    for category, count in sorted_categories:
         if count > 0:
             cat_stats_table.add_row(category, str(count))
    if cat_stats_table.row_count > 0:
        console.print(cat_stats_table)


    # Informations MK2 (inchangé, mais utilise les stats mises à jour)
    media_counts = {cat: stats['categories'].get(cat, 0) for cat in MEDIA_LABELS.keys()}
    mk2_info = f"""
Enfin, comme vu ensemble ce matin, les médias suivants seront ajoutés manuellement par l'équipe Marketing de MK2 :
* AfficheS [1] - {media_counts.get('AfficheS', 0)} fichiers
* Photo HD [2] - {media_counts.get('Photo HD', 0)} fichiers
* Dossier de presse [3] - {media_counts.get('Dossier de presse', 0)} fichiers
* Revue de presse [4] - {media_counts.get('Revue de presse', 0)} fichiers

Afin de gagner du temps sur cette partie, nous vous proposons d'éditer brièvement le nom de chaque média puis de nous donner l'accès afin d'importer rapidement tous ces médias sur MovieChainer. Pour ce faire, il vous suffit d'ajouter en préfixe de chaque média :
1. Le numéro correspondant au type de média (visible entre crochets juste au dessus) : 1, 2, 3 ou 4.
2. Un underscore
3. L'ID du film sur MCH (que vous trouverez dans le fichier Excel)

Un dossier de presse pour le titre "Holly" (ID MCH 2373) par exemple sera sous la forme 3_2373_[nom_original].
    """
    console.print(Panel(mk2_info, title="Instructions MK2 (Rappel Convention Nommage)", border_style="blue"))
    console.print(f"\n[bold]Le détail complet du traitement est disponible dans le fichier journal : '{LOG_FILE}'[/bold]")

    # Créer un graphique récapitulatif (inchangé, mais basé sur les nouvelles stats)
    if stats['success'] > 0:
        try:
            plt.figure(figsize=(10, 7))
            # Utiliser les catégories finales pour le graphique
            plot_data = {cat: count for cat, count in stats['categories'].items() if count > 0}

            if plot_data:
                plt.pie(plot_data.values(), labels=plot_data.keys(), autopct='%1.1f%%', startangle=140, pctdistance=0.85)
                # Dessiner un cercle au centre pour faire un donut chart (plus lisible)
                centre_circle = plt.Circle((0,0),0.70,fc='white')
                fig = plt.gcf()
                fig.gca().add_artist(centre_circle)

                plt.title("Répartition des Fichiers Triés par Catégorie Finale", pad=20)
                plt.axis('equal') # Assure que le pie est circulaire.

                chart_path = "resume_categories_finales.png"
                plt.savefig(chart_path, dpi=300, bbox_inches='tight')
                plt.close()
                console.print(f"\n[green]Graphique récapitulatif sauvegardé dans '{chart_path}'[/green]")
            else:
                 console.print("[yellow]Aucune donnée à afficher dans le graphique.[/yellow]")

        except Exception as e:
            console.print(f"[yellow]Impossible de créer le graphique: {e}[/yellow]")


    console.print("\n[bold blue]===== FIN DU TRAITEMENT =====")

    # Fermer le fichier CSV proprement
    if csv_logger:
        csv_logger.close()


# Lancer le programme
if __name__ == "__main__":
    # Optimisation avec uvloop si disponible
    use_uvloop = False
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        use_uvloop = True
    except ImportError:
        pass

    if use_uvloop:
        console.print("[blue]Utilisation de uvloop pour des performances asyncio améliorées[/blue]")

    # Exécuter le programme principal
    asyncio.run(main())