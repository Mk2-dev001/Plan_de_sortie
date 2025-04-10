from playwright.sync_api import sync_playwright
import json
import re
import time
from datetime import datetime
import traceback

login_url = "https://otto-bo.vodfactory.com/"
catalogue_url = "https://otto-bo.vodfactory.com/catalogue"

def log(msg):
    print(f"[LOG] {msg}")

def clean_large_text_block(raw_text):
    noisy_headers = [
        "CATALOGUE", "MARKETING", "STATISTIQUES", "PARAMÈTRES", "Page d'accueil",
        "Toutes mes fiches", "Mettre en ligne", "Enregistrer les modifications",
        "Sélectionner", "Ajouter un participant", "Supprimer la fiche"
    ]
    for header in noisy_headers:
        raw_text = raw_text.replace(header, "")
    lines = raw_text.splitlines()
    cleaned_lines = [line.strip() for line in lines if line.strip() and not line.strip().isdigit()]
    return "\n".join(cleaned_lines)

def extract_from_raw_text(raw_text, label, end_labels=[]):
    if end_labels:
        end_patterns = "|".join([re.escape(end) for end in end_labels])
        pattern = re.compile(re.escape(label) + r"\s*:\s*(.*?)(?=\n(?:{}))".format(end_patterns), re.DOTALL)
    else:
        pattern = re.compile(re.escape(label) + r"\s*:\s*(.*?)\n", re.DOTALL)
    match = pattern.search(raw_text)
    if match:
        text = match.group(1).strip()
        text = re.sub(r"\s{2,}", " ", text)
        return text
    return ""

def main():
    with sync_playwright() as p:
        log("Lancement de Playwright...")
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        log("Ouverture de la page de connexion...")
        page.goto(login_url)
        log("Veuillez vous connecter manuellement...")
        input("Appuyez sur Entrée pour continuer une fois connecté...")

        log("Navigation vers le catalogue...")
        page.goto(catalogue_url)
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        films = extract_catalogue_data(page)
        if not films:
            log("Aucun film trouvé dans le catalogue.")
            browser.close()
            return

        films_details = collect_film_details(page, films)
        export_to_json(films_details)

        log(f"Extraction terminée : {len(films_details)} films exportés")
        browser.close()

def extract_catalogue_data(page):
    log("Récupération de la liste des films sur toutes les pages...")
    all_films = []
    current_page = 1
    hrefs_seen = set()  # Pour éviter les doublons par URL
    page_stuck_count = 0
    max_stuck_count = 3
    
    while True:
        log(f"Page {current_page}")
        
        try:
            page.wait_for_selector("tbody tr", timeout=20000)
        except Exception as e:
            log(f"Erreur en attendant 'tbody tr': {e}")
            break

        film_elements = page.query_selector_all("tbody tr")
        log(f"Trouvé {len(film_elements)} éléments sur la page")
        
        new_films_on_page = 0
        for element in film_elements:
            try:
                # Extraire le titre
                title_element = element.query_selector("td strong") or element.query_selector("td:first-child")
                if not title_element:
                    continue
                    
                title_text = title_element.inner_text().strip()
                if not title_text or title_text.lower() == "id :":
                    continue
                    
                # Extraire l'ID si présent
                id_match = re.search(r"ID\s*:\s*(\d+)", title_text, re.IGNORECASE)
                film_id = id_match.group(1) if id_match else None
                
                # Nettoyer le titre
                title = re.sub(r"ID\s*:\s*\d+", "", title_text, flags=re.IGNORECASE).strip()
                
                # Extraire le lien
                link_element = element.query_selector("a:has-text('Fiche contenu')") or element.query_selector("a[href*='/catalogue/']") or element.query_selector("a")
                href = link_element.get_attribute("href") if link_element else None
                
                # Si nous avons les informations nécessaires et que ce n'est pas un doublon par URL
                if title and href and href not in hrefs_seen:
                    all_films.append({"title": title, "href": href, "id": film_id})
                    hrefs_seen.add(href)
                    new_films_on_page += 1
            except Exception as e:
                log(f"Erreur lors de l'extraction d'un film: {e}")

        log(f"Ajouté {new_films_on_page} films depuis la page {current_page}. Total : {len(all_films)}")
        
        # Si aucun nouveau film n'a été trouvé, il y a peut-être un problème
        if new_films_on_page == 0:
            page_stuck_count += 1
            log(f"Aucun nouveau film trouvé, compteur de blocage: {page_stuck_count}/{max_stuck_count}")
            if page_stuck_count >= max_stuck_count:
                log(f"Aucun nouveau film trouvé après {max_stuck_count} tentatives, fin de l'extraction")
                break
        else:
            # Réinitialiser le compteur si nous avons trouvé de nouveaux films
            page_stuck_count = 0

        # Méthode originale de navigation : cliquer sur un bouton spécifique
        try:
            # Essayer de trouver les boutons de pagination
            pagination_buttons = page.query_selector_all("ul >> li >> button")
            log(f"Trouvé {len(pagination_buttons)} boutons de pagination")
            
            # Afficher les textes des boutons pour le débogage
            for i, button in enumerate(pagination_buttons):
                log(f"Bouton {i}: '{button.inner_text().strip()}'")
            
            # Rechercher spécifiquement un bouton avec le texte suivant
            next_page_num = current_page + 1
            button_index = -1
            
            for i, button in enumerate(pagination_buttons):
                if button.inner_text().strip() == str(next_page_num):
                    button_index = i
                    break
            
            # Si le bouton spécifique n'est pas trouvé, essayer le bouton '⟩'
            if button_index == -1:
                for i, button in enumerate(pagination_buttons):
                    if button.inner_text().strip() == "⟩":
                        button_index = i
                        break
            
            if button_index != -1:
                log(f"Tentative de clic sur le bouton d'indice {button_index}")
                pagination_buttons[button_index].click()
                time.sleep(2)
                current_page += 1
            else:
                log("Aucun bouton de pagination suivant trouvé, fin de l'extraction")
                break
        except Exception as e:
            log(f"Erreur lors de la tentative de pagination : {e}")
            break

    log(f"Fin de la récupération : {len(all_films)} films trouvés au total.")
    return all_films

def collect_film_details(page, films):
    films_details = []
    for index, film in enumerate(films, 1):
        log(f"{index}/{len(films)} - {film['title']}")
        if not film["href"]:
            continue

        film_url = film["href"]
        if not film_url.startswith("http"):
            film_url = f"https://otto-bo.vodfactory.com{film_url if film_url.startswith('/') else '/' + film_url}"

        try:
            page.goto(film_url)
            page.wait_for_load_state("networkidle")
            time.sleep(2)
            film_detail = extract_film_info(page, film)
            films_details.append(film_detail)
        except Exception as e:
            log(f"Erreur accès fiche : {e}")
    return films_details

def extract_film_info(page, film_base):
    film_info = {"titre": film_base["title"].strip()}
    raw_text = page.inner_text("body")
    clean_text = clean_large_text_block(raw_text)
    film_info["notre_avis"] = re.sub(r"\d{1,4}/5000$", "", extract_from_raw_text(clean_text, "Notre avis", ["Titre L'auteur", "Comédiens/Comédiennes"])).strip()
    film_info["synopsis"] = extract_from_raw_text(clean_text, "Synopsis", ["Comédiens/Comédiennes", "Cinéastes"]).replace("Synopsis\nSynopsis :", "").strip()
    film_info["durée"] = extract_from_raw_text(clean_text, "Durée").replace("Durée de ma vidéo ", "").strip()
    genre_raw = extract_from_raw_text(clean_text, "Genre", ["Type", "Catégories"])
    film_info["genre"] = re.sub(r"^Type\s*:\s*", "", genre_raw).split("\n")[0].strip()
    film_info["type"] = extract_from_raw_text(clean_text, "Type", ["Date"])
    film_info["pays"] = extract_from_raw_text(clean_text, "Pays", ["Lien vers films"])
    film_info["csa"] = extract_from_raw_text(clean_text, "CSA", ["Version"])
    film_info["version"] = extract_from_raw_text(clean_text, "Version", ["Pays"])
    try:
        date_input = page.query_selector('input[name="date"]')
        film_info["année"] = date_input.get_attribute("value").strip() if date_input else ""
    except:
        film_info["année"] = ""

    comediens = extract_from_raw_text(clean_text, "Comédiens/Comédiennes", ["Titre A la sortie...", "Titre Sa sélection"])
    if "Titre A la sortie" in comediens or "Texte A la sortie" in comediens:
        comediens = ""
    film_info["comédiens"] = comediens

    try:
        cineastes_blocks = page.query_selector_all(".movie-participants-item")
        cineastes = []
        for block in cineastes_blocks:
            name_el = block.query_selector("h4.participant-name")
            role_el = block.query_selector("p.participant-role")
            if name_el and role_el and "Réalisateur" in role_el.inner_text():
                cineastes.append(name_el.inner_text().strip())
        film_info["réalisateur"] = ", ".join(cineastes)
    except:
        film_info["réalisateur"] = ""

    return film_info

def export_to_json(films_details):
    log("Génération du fichier JSON...")
    now = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"otto_catalogue_export_{now}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(films_details, f, ensure_ascii=False, indent=2)
    log(f"Fichier JSON généré : {filename}")

if __name__ == "__main__":
    main()