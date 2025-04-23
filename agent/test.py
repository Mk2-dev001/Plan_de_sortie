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
DESTINATION_DIR = Path("Sorted2")
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
FUZZY_MATCH_THRESHOLD_FOLDER = 80 # Pourcentage de similarité pour lier dossier <-> titre excel
FUZZY_MATCH_THRESHOLD_FILE = 85   # Pourcentage de similarité pour lier fichier <-> titre connu

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

def load_excel_ids():
    """Tenter de charger les IDs des films depuis un fichier Excel"""
    # ... (code inchangé, mais on pourrait ajouter du fuzzy matching ici aussi si les titres Excel sont variables) ...
    try:
        excel_path = "MK2 - Metadatas export.xlsx"
        if not os.path.exists(excel_path):
            console.print("[yellow]Fichier Excel introuvable: Utilisation d'IDs séquentiels[/yellow]")
            return {}

        # Essayer plusieurs engines
        df = None
        engines = ['openpyxl', 'xlrd', None]
        for engine in engines:
            try:
                if (engine):
                    df = pd.read_excel(excel_path, engine=engine)
                else:
                    df = pd.read_excel(excel_path)
                break # Succès
            except Exception as e:
                # console.print(f"[grey]Essai avec engine {engine} échoué: {e}[/grey]") # Debug
                continue
        else: # Si la boucle se termine sans break
             console.print("[yellow]Impossible de lire le fichier Excel avec les engines disponibles: Utilisation d'IDs séquentiels[/yellow]")
             return {}

        if df is None: # Sécurité
            return {}

        # Chercher les colonnes pertinentes (inchangé)
        title_col, id_col = None, None
        for col in df.columns:
            col_str = str(col).lower()
            if not title_col and ('titre' in col_str or 'title' in col_str or 'nom' in col_str):
                title_col = col
            if not id_col and ('id' in col_str or 'code' in col_str or 'ref' in col_str):
                 id_col = col
            if title_col and id_col:
                break # Trouvé les deux

        if title_col is None or id_col is None:
            console.print("[yellow]Colonnes Titre/ID non trouvées explicitement. Tentative avec les premières colonnes.[/yellow]")
            if len(df.columns) >= 2:
                title_col = df.columns[0]
                id_col = df.columns[1]
                console.print(f"[grey]Utilisation de '{title_col}' comme Titre et '{id_col}' comme ID[/grey]")
            else:
                console.print("[red]Pas assez de colonnes dans le fichier Excel pour déterminer Titre/ID.[/red]")
                return {}

        # Construire le dictionnaire
        film_ids_dict = {}
        duplicates = 0
        for _, row in df.iterrows():
            if pd.notnull(row[title_col]) and pd.notnull(row[id_col]):
                title = str(row[title_col]).strip()
                try:
                    # Essayer de convertir en entier, puis en string pour nettoyer (ex: 123.0 -> 123)
                    id_val = str(int(row[id_col]))
                except ValueError:
                     # Sinon, utiliser la valeur telle quelle (peut être alphanumérique)
                    id_val = str(row[id_col]).strip()

                if title in film_ids_dict and film_ids_dict[title] != id_val:
                    duplicates += 1
                    # console.print(f"[yellow]Titre dupliqué avec ID différent: '{title}' (IDs: {film_ids_dict[title]}, {id_val})[/yellow]")
                    # On garde le premier rencontré pour l'instant
                elif title not in film_ids_dict:
                     film_ids_dict[title] = id_val
                     # Ajouter une version lowercase pour la recherche insensible à la casse
                     film_ids_dict[title.lower()] = id_val

        if duplicates > 0:
             console.print(f"[yellow]Avertissement: {duplicates} titres dupliqués trouvés dans l'Excel (premier ID conservé).[/yellow]")
        console.print(f"[green]Chargement réussi de {len(film_ids_dict) // 2} IDs uniques depuis le fichier Excel[/green]")
        return film_ids_dict

    except Exception as e:
        console.print(f"[red]Erreur critique lors du chargement des IDs Excel: {e}[/red]")
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

    # Règle 1: Format "ANNÉE - TITRE"
    if re.match(r'(19|20)\d{2}\s*-\s*', folder_name):
        return True

    # Règle 2: Contient le nom d'un film Chaplin connu (match exact ou flou si activé)
    if process: # Vérifie si thefuzz est chargé
        # Recherche floue partielle (plus tolérante)
        match, score = process.extractOne(folder_lower, [f.lower() for f in KNOWN_FILMS], scorer=fuzz.partial_ratio)
        if score >= FUZZY_MATCH_THRESHOLD_FOLDER: # Utilisation du seuil
            return True
    else: # Fallback si thefuzz n'est pas dispo
        for film in KNOWN_FILMS:
            if film.lower() in folder_lower:
                return True

    # Règle 3: Termes qui indiquent un NON-film
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

    # Cas spécial pour THE KID qui doit être un film (renforcé)
    if 'the kid' in folder_lower:
        return True

    # Par défaut, si on ne sait pas
    return None  # Incertain, l'IA (si dispo) ou une règle par défaut décidera

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
    """Analyser la structure des dossiers pour détecter les films"""
    global next_id
    console.print("[blue]Analyse de la structure des dossiers...[/blue]")

    film_folders = []
    film_paths = {}
    known_films_map = {}  # Map des noms normalisés vers les IDs
    title_to_id = {}  # Map directe titre -> ID

    # Mapping des titres connus (pour normalisation)
    title_mapping = {
        "the kid": "The Kid",
        "the gold rush": "The Gold Rush",
        "the circus": "The Circus",
        "city lights": "City Lights",
        "modern times": "Modern Times",
        "the great dictator": "The Great Dictator",
        "monsieur verdoux": "Monsieur Verdoux",
        "limelight": "Limelight",
        "a king in new york": "A King in New York",
        "a woman of paris": "A Woman of Paris"
    }

    # Récupérer tous les sous-dossiers récursivement
    all_subdirs = []
    for root, dirs, _ in os.walk(SOURCE_DIR):
        for dir_name in dirs:
            if dir_name.startswith(('19', '20')) and '-' in dir_name:
                dir_path = Path(root) / dir_name
                if not any(ignore in str(dir_path) for ignore in IGNORE_PATTERNS):
                    all_subdirs.insert(0, dir_path)
            else:
                dir_path = Path(root) / dir_name
                if not any(ignore in str(dir_path) for ignore in IGNORE_PATTERNS):
                    all_subdirs.append(dir_path)

    # Fonction pour normaliser les titres
    def normalize_title(title):
        title = title.lower().strip()
        # Supprimer l'année si présente
        title = re.sub(r'^(19|20)\d{2}\s*-\s*', '', title)
        # Normaliser les variantes connues
        return title_mapping.get(title, title.title())

    with Progress() as progress:
        task = progress.add_task("Traitement TITRES", total=len(all_subdirs))
        
        for folder in all_subdirs:
            folder_name = folder.name
            clean_title = None

            # 1. Extraire le titre du format année si présent
            year_match = re.match(r'^(19|20)\d{2}\s*-\s*(.+)$', folder_name)
            if year_match:
                clean_title = year_match.group(2).strip()
            
            # 2. Sinon chercher dans les films connus
            if not clean_title and process:
                matches = process.extractBests(folder_name, KNOWN_FILMS, score_cutoff=FUZZY_MATCH_THRESHOLD_FOLDER)
                if matches:
                    clean_title = matches[0][0]

            if clean_title:
                normalized_title = normalize_title(clean_title)
                
                # Utiliser l'ID existant si le film est déjà connu
                if normalized_title in title_to_id:
                    film_id = title_to_id[normalized_title]
                else:
                    # Chercher dans les IDs Excel
                    film_id = None
                    for known_title, known_id in real_film_ids.items():
                        if fuzz.ratio(normalized_title.lower(), known_title.lower()) > FUZZY_MATCH_THRESHOLD_FOLDER:
                            film_id = known_id
                            break
                    
                    # Si pas trouvé, générer un nouvel ID
                    if not film_id:
                        next_id += 1
                        film_id = str(next_id).zfill(3)
                    
                    title_to_id[normalized_title] = film_id
                    DETECTED_FILMS[film_id] = normalized_title

                film_info = {
                    'id': film_id,
                    'name': normalized_title,
                    'path': folder,
                    'match_score': 100 if year_match else 90,
                    'id_source': 'Excel' if film_id in real_film_ids.values() else 'Généré'
                }
                
                film_folders.append(film_info)
                film_paths[str(folder)] = film_id
            
            progress.advance(task)

    # Afficher un résumé de la détection
    if film_folders:
        unique_films = len(set(f['id'] for f in film_folders))
        console.print(f"[green]Détection de {unique_films} films uniques terminée.[/green]")
        
        # Afficher les associations
        for film_id, film_name in sorted(DETECTED_FILMS.items()):
            matching_folders = [f['path'].name for f in film_folders if f['id'] == film_id]
            if matching_folders:
                console.print(f"[grey]{film_name} (ID: {film_id}) -> {', '.join(matching_folders)}[/grey]")
    else:
        console.print("[yellow]Attention: Aucun film n'a été détecté.[/yellow]")

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
    """Déterminer le film associé à un fichier avec une logique améliorée."""
    file_str_lower = str(file_path).lower()
    file_name_lower = file_path.name.lower()

    # Stratégie 1: Le fichier est DANS un dossier de film déjà identifié
    current_path = file_path.parent
    while current_path != SOURCE_DIR and current_path != current_path.parent: # Eviter boucle infinie
        path_str = str(current_path)
        if path_str in film_paths:
            return film_paths[path_str] # Trouvé !
        current_path = current_path.parent

    # Stratégie 2: Le nom du fichier contient EXACTEMENT le nom d'un film détecté (ou son ID)
    for film_id, detected_name in DETECTED_FILMS.items():
        # Extraire le nom "propre" du film (sans année si format "YYYY - Titre")
        clean_name = detected_name
        match_year_title = re.match(r'(19|20)\d{2}\s*-\s*(.*)', detected_name)
        if match_year_title:
            clean_name = match_year_title.group(2).strip()

        # Vérifier nom propre et nom complet
        if clean_name.lower() in file_name_lower or detected_name.lower() in file_name_lower:
             return film_id
        # Vérifier si l'ID lui-même est dans le nom (ex: 3_2373...)
        if f"_{film_id}_" in file_name_lower or file_name_lower.startswith(f"{film_id}_"):
             return film_id

    # Stratégie 3: Le nom/chemin du fichier contient le nom d'un film CONNU (fuzzy match)
    if process: # Si thefuzz est disponible
        known_film_titles_lower = [f.lower() for f in KNOWN_FILMS]
        # Utiliser partial_ratio car le nom du film peut être une partie du nom de fichier/chemin
        best_match, score = process.extractOne(file_str_lower, known_film_titles_lower, scorer=fuzz.partial_ratio)

        if score >= FUZZY_MATCH_THRESHOLD_FILE:
            # Trouver l'ID du film détecté qui correspond le mieux à ce film connu
            # (peut être ambigu si plusieurs dossiers détectés correspondent au même film connu)
            matched_film_id = None
            highest_score = 0
            for film_id, detected_name in DETECTED_FILMS.items():
                 # Comparer le film connu trouvé (best_match) avec le nom du dossier détecté
                 current_score = fuzz.token_sort_ratio(best_match, detected_name.lower())
                 if current_score > highest_score:
                     highest_score = current_score
                     matched_film_id = film_id

            if matched_film_id and highest_score > 75: # Seuil interne pour lier match flou <-> dossier détecté
                # console.print(f"[grey]Match flou fichier: '{file_path.name}' (via '{best_match}', score {score}) -> Film ID {matched_film_id}[/grey]")
                return matched_film_id

    # Stratégie 4: En dernier recours, vérifier si du texte extrait contient un nom de film
    # (Cette partie pourrait être ajoutée si nécessaire, mais peut être lente)
    # extracted_text = extract_text_from_file(file_path)
    # if extracted_text:
    #    # ... rechercher KNOWN_FILMS dans extracted_text ...

    # Fallback: Pas de film spécifique trouvé
    return None # Indique qu'aucun film spécifique n'a pu être associé

def categorize_file_by_rules(file_path):
    """Catégoriser un fichier selon des règles basées sur nom/chemin/extension (Première passe)."""
    file_name_lower = file_path.name.lower()
    # Utiliser le chemin relatif pour éviter les faux positifs dus au nom du dossier source
    try:
        relative_path_str = str(file_path.relative_to(SOURCE_DIR)).lower()
    except ValueError: # Si le fichier n'est pas dans SOURCE_DIR (ne devrait pas arriver ici)
        relative_path_str = str(file_path).lower()

    ext = file_path.suffix.lower()

    # Règles spécifiques prioritaires
    if any(term in file_name_lower or term in relative_path_str for term in ['affiche', 'poster', ' aff ', '_aff_', 'movie poster']):
        if ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.gif', '.bmp', '.pdf']:
            return 'AfficheS'

    if any(term in file_name_lower or term in relative_path_str for term in ['dossier de presse', 'press kit', 'dp_', 'pressbook']):
        if ext in ['.pdf', '.doc', '.docx', '.zip', '.rar']: # Zip peut contenir un DP
             return 'Dossier de presse'

    if any(term in file_name_lower or term in relative_path_str for term in ['revue de presse', 'press review', ' article', 'critique', 'review', 'clipping']):
         if ext in ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.txt']: # Articles scannés ou textes
            return 'Revue de presse'

    if any(term in file_name_lower or term in relative_path_str for term in ['photo', 'image', 'still', ' hd ', '_hd_', ' highres', ' high res', ' scene ']):
         if ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.gif']:
             return 'Photo HD'

    # Autres catégories moins prioritaires (peuvent être affinées par contenu/IA)
    if any(term in file_name_lower or term in relative_path_str for term in ['facture', 'invoice', 'billing']):
         if ext in ['.pdf', '.xlsx', '.xls', '.doc', '.docx', '.csv']:
            return 'Factures'
    if any(term in file_name_lower or term in relative_path_str for term in ['contrat', 'agreement', 'nda', 'contract']):
        if ext in ['.pdf', '.doc', '.docx']:
            return 'Contrats'
    if any(term in file_name_lower or term in relative_path_str for term in ['présentation', 'presentation', 'slides', 'deck']):
        if ext in ['.pptx', '.ppt', '.pdf', '.key']:
            return 'Présentations'
    if any(term in file_name_lower or term in relative_path_str for term in ['administratif', 'admin', 'legal', 'document']):
        if ext in ['.pdf', '.doc', '.docx', '.txt', '.xls', '.xlsx']:
            return 'Documents administratifs' # Catégorie assez générique


    # Catégorisation par défaut basée sur l'extension si aucune règle n'a matché
    if ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.gif']:
        return 'Photo HD' # Par défaut pour les images non identifiées autrement
    if ext in ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.mpg', '.mpeg', '.webm']:
        return 'Médias (audio/vidéo)'
    if ext in ['.mp3', '.wav', '.aac', '.ogg', '.flac', '.m4a']:
         return 'Médias (audio/vidéo)' # On pourrait séparer Audio/Vidéo si besoin
    if ext in ['.pdf']:
        # PDF est ambigu, peut être DP, Revue, Contrat, Facture...
        return 'Divers' # Laisser l'analyse de contenu/IA décider
    if ext in ['.docx', '.doc']:
        return 'Divers' # Idem pour les documents Word
    if ext in ['.pptx', '.ppt']:
        return 'Présentations'
    if ext in ['.xlsx', '.xls', '.csv']:
         # Souvent admin ou factures, mais laissons 'Divers' pour affinage
        return 'Divers'
    if ext in ['.txt']:
        return 'Divers'

    # Catégorie par défaut ultime
    return 'Divers'


async def categorize_file(file_path):
    """Déterminer la catégorie d'un fichier en utilisant règles, contenu et IA."""
    file_name = file_path.name
    cache_key = f"category:{str(file_path)}" # Utiliser le chemin complet pour le cache

    if cache_key in ai_cache:
        return ai_cache[cache_key]

    # 1. Catégorisation par règles (rapide)
    category = categorize_file_by_rules(file_path)

    # 2. Affinage par contenu textuel (si catégorie ambiguë et fichier texte/doc)
    extracted_text = None
    if category == 'Divers' and file_path.suffix.lower() in ['.pdf', '.docx', '.txt']:
        extracted_text = extract_text_from_file(file_path, max_chars=1000) # Plus de contexte
        if extracted_text:
            text_lower = extracted_text.lower()
            # Mots-clés pour affiner 'Divers' (priorité haute)
            if 'facture' in text_lower or 'invoice' in text_lower: category = 'Factures'
            elif 'contrat' in text_lower or 'agreement' in text_lower: category = 'Contrats'
            elif 'dossier de presse' in text_lower or 'press kit' in text_lower: category = 'Dossier de presse'
            elif 'communiqué de presse' in text_lower: category = 'Dossier de presse'
            elif 'revue de presse' in text_lower or 'critique' in text_lower or 'article paru' in text_lower: category = 'Revue de presse'
            elif 'présentation' in text_lower or 'slides' in text_lower: category = 'Présentations'
            # Ajouter d'autres règles spécifiques basées sur le contenu ici

    # 3. Affinage par métadonnées EXIF (si image et catégorie ambiguë)
    extracted_metadata = None
    if category in ['Photo HD', 'Divers'] and Image and file_path.suffix.lower() in ['.jpg', '.jpeg', '.tif', '.tiff']:
        extracted_metadata = get_image_metadata(file_path)
        if extracted_metadata:
            # Chercher des indices dans les métadonnées
            desc = str(extracted_metadata.get('ImageDescription', '')).lower()
            keywords = str(extracted_metadata.get('Keywords', '')).lower() # Peut être un tag spécifique
            if 'affiche' in desc or 'poster' in desc or 'affiche' in keywords or 'poster' in keywords:
                category = 'AfficheS'
            # Ajouter d'autres règles basées sur EXIF

    # 4. Utilisation de l'IA (si configurée et catégorie toujours ambiguë ou 'Divers')
    # On fait confiance à l'IA pour reclasser même une catégorie déjà trouvée si elle semble générique
    # Ou si la catégorie est 'Divers'
    should_use_ai = openai_client and (category == 'Divers' or category not in MEDIA_LABELS)

    if should_use_ai:
        try:
            ext = file_path.suffix.lower()
            folder_path_rel = str(file_path.parent.relative_to(SOURCE_DIR))

            # Préparer le contexte pour l'IA
            context_info = f"Extension: {ext}\nChemin relatif: {folder_path_rel}"
            if extracted_text:
                context_info += f"\nExtrait texte (max 100 chars): {extracted_text[:100]}..."
            if extracted_metadata:
                 # Ajouter quelques métadonnées clés si elles existent
                 meta_sample = {k: v for k, v in extracted_metadata.items() if k in ['ImageDescription', 'Keywords', 'Artist']}
                 if meta_sample:
                     context_info += f"\nMetadonnées image (échantillon): {json.dumps(meta_sample, ensure_ascii=False)}"

            # Prompt amélioré pour l'IA
            prompt = f"""
            Classe ce fichier dans la catégorie la plus appropriée parmi la liste fournie. Analyse le nom, le chemin, l'extension et les extraits de contenu/métadonnées si disponibles.

            Nom du fichier: {file_path.name}
            Contexte:
            {context_info}

            Choisis UNE SEULE catégorie parmi celles-ci (respecte la casse):
            - AfficheS (Affiches de film, posters)
            - Photo HD (Photos de plateau, portraits, images promotionnelles haute résolution)
            - Dossier de presse (Documents pour la presse: communiqués, synopsis, biographies...)
            - Revue de presse (Articles de presse publiés, critiques, interviews scannées/transcrites)
            - Documents administratifs (Documents internes, notes, mémos, non liés à une transaction)
            - Factures (Factures, notes de frais, documents de paiement)
            - Contrats (Contrats, accords légaux, licences)
            - Présentations (Diaporamas, présentations type PowerPoint/Keynote)
            - Médias (audio/vidéo) (Fichiers vidéo ou audio : rushes, bandes-annonces, interviews audio...)
            - Divers (Uniquement si absolument aucune autre catégorie ne correspond)

            Réponds UNIQUEMENT avec le nom exact de la catégorie choisie. Pas d'explication.
            """

            response = await openai_client.chat.completions.create(
                model="gpt-3.5-turbo", # Ou gpt-4 si besoin de plus de précision
                messages=[
                    {"role": "system", "content": f"Tu es un archiviste expert. Classe le fichier donné dans l'une des catégories suivantes: {', '.join(ALL_CATEGORIES)}."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=30, # Suffisant pour un nom de catégorie
                temperature=0.2 # Plus déterministe
            )

            ai_category = response.choices[0].message.content.strip()

            # Vérifier si la réponse de l'IA est une catégorie valide
            if ai_category in ALL_CATEGORIES:
                # console.print(f"[grey]IA category for {file_name}: {ai_category}[/grey]") # Debug
                category = ai_category # L'IA a priorité si elle donne une réponse valide
            else:
                # console.print(f"[yellow]IA category invalid: '{ai_category}' for {file_name}. Keeping previous: {category}[/yellow]")
                pass # Garder la catégorie précédente si l'IA répond n'importe quoi

        except Exception as e:
            console.print(f"[yellow]Erreur lors de la catégorisation IA pour {file_name}: {e}. Utilisation de la catégorie précédente: {category}[/yellow]")
            # Ne rien faire, garder la catégorie déterminée avant l'IA

    # Sauvegarder la décision finale dans le cache
    ai_cache[cache_key] = category
    # Pas besoin de sauvegarder le cache ici à chaque fois, on le fera à la fin.
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
        # Dossier film = nom du film (ou ID si indisponible)
        film_folder = sanitize_filename(DETECTED_FILMS[film_id] if film_id in DETECTED_FILMS else "Inconnu")
        base_target_dir = DESTINATION_DIR / film_folder

        # Créer sous-dossier selon type (ex: '1_123')
        if category in MEDIA_LABELS and film_id and media_type_label:
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
        film_name = detected_films_map.get(film_id, None) if film_id else None
        log_entry['film_id'] = film_id
        log_entry['film_name'] = film_name

        # 5. Déplacer et renommer
        media_type_label = MEDIA_LABELS.get(category) # Obtient '1', '2', etc. si c'est une catégorie média principale

        # Si la catégorie est une des principales et qu'on n'a pas trouvé de film_id,
        # on DOIT le mettre dans 'Divers' ou une catégorie générique, car le nommage l'exige.
        # Ou alors, on pourrait lui assigner un ID 'UNKNOWN' ou '000'. Choisissons 'Divers' pour l'instant.
        final_category = category
        final_film_id = film_id
        if category in MEDIA_LABELS and not film_id:
             final_category = 'Divers' # Réaffecter car pas de film ID
             final_film_id = None     # Assurer qu'on ne met pas d'ID
             media_type_label = None # Pas de label de type non plus
             log_entry['reason'] = f"Réaffecté à Divers (catégorie {category} sans ID film)"


        new_path, error_reason = move_file(file_path, final_category, final_film_id, media_type_label)

        if new_path:
            log_entry.update({'status': 'success', 'new_path': new_path})
            # Si on a réaffecté à Divers, on met à jour la catégorie dans le log aussi
            if final_category != category:
                 log_entry['category'] = final_category

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
        # Log du temps de traitement par fichier (optionnel, pour analyse de perf)
        # end_process_time = time.monotonic()
        # print(f"Processed {file_path.name} in {end_process_time - start_process_time:.2f}s")


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