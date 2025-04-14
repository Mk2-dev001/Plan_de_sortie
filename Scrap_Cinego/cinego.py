from playwright.sync_api import sync_playwright
import csv
import time
import Scrap_Cinego.credentials as credentials
import json

login_url = "https://distri.cinego.net"
cinemas_url = "https://distri.cinego.net/#/cinemas/list?view_id=1"
output_csv = "cinemas_export.csv"

def log(msg):
    print(f"[🧩] {msg}")

with sync_playwright() as p:
    log("Lancement de Playwright...")
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    log("Connexion en cours...")
    page.goto(login_url)
    page.fill('input[placeholder="Nom d\'utilisateur"]', credentials.USERNAME)
    page.fill('input[placeholder="Mot de passe"]', credentials.PASSWORD)
    page.click("button:has-text('Se connecter')")
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    log("Navigation vers la liste des cinémas...")
    page.goto(cinemas_url)
    page.wait_for_load_state("networkidle")
    time.sleep(3)

    scroll_container = page.query_selector("cdk-virtual-scroll-viewport")
    if not scroll_container:
        raise Exception("Scroll container not found")

    seen = set()
    cinemas = []

    log("🔽 Début du scroll pour récupérer tous les cinémas...")
    previous_count = -1

    while len(seen) != previous_count:
        previous_count = len(seen)
        links = page.query_selector_all("a.link-content")

        for link in links:
            name = link.inner_text().strip()
            href = link.get_attribute("href")
            if name and href and name not in seen:
                seen.add(name)
                cinemas.append({"name": name, "href": href})

        page.evaluate("el => el.scrollBy(0, 600)", scroll_container)
        time.sleep(0.6)

    log(f"✅ Fin du scroll. {len(cinemas)} cinémas collectés.")
    cinemas = sorted(cinemas, key=lambda c: c["href"])

    data = []
    for index, c in enumerate(cinemas, 1):
        log(f"\n🎬 {index}/{len(cinemas)} - Traitement de : {c['name']}")
        base_url = f"https://distri.cinego.net{c['href'].split('?')[0]}"

        adresse = ""
        contact_nom = ""
        contact_mail = ""
        contact_tel = ""

        # ÉQUIPEMENT
        salles = []
        try:
            page.goto(f"{base_url}/equipement?view_id=1")
            page.wait_for_load_state("networkidle")
            page.wait_for_selector("table", timeout=5000)
            time.sleep(1.5)

            salle_rows = page.query_selector_all("table tr")
            if len(salle_rows) < 2:
                log(f"⚠️ Pas de salles listées pour {c['name']}")
                continue

            for row in salle_rows[1:]:
                cols = row.query_selector_all("td")
                if len(cols) < 6:
                    continue
                try:
                    salle = cols[0].inner_text().strip()
                    cnc = cols[1].inner_text().strip()
                    capacite = cols[2].inner_text().strip()
                    equipement = cols[4].inner_text().strip()
                    format_proj = cols[5].inner_text().strip()
                    if not salle or not salle[0].isdigit():
                        continue
                    salles.append((salle, cnc, capacite, equipement, format_proj))
                except Exception as e:
                    log(f"⚠️ Erreur de parsing dans une salle ({c['name']}) : {e}")
                    continue
        except Exception as e:
            log(f"❌ Échec d'accès à l'onglet équipement pour {c['name']} : {e}")
            continue

        if not salles:
            log(f"⚠️ Aucune salle trouvée pour {c['name']}")
            continue

        # GÉNÉRAL
        try:
            page.goto(f"{base_url}/general?view_id=1")
            page.wait_for_load_state("networkidle")
            time.sleep(1.5)

            contact_locator = page.locator("tr.contact-item").first
            contact_locator.wait_for(timeout=5000)
            cells = contact_locator.locator("td")
            if cells.count() >= 3:
                contact_nom = cells.nth(0).inner_text().strip()
                contact_mail = cells.nth(1).inner_text().strip()
                contact_tel = cells.nth(2).inner_text().strip()
                log(f"📇 Contact : {contact_nom} / {contact_mail} / {contact_tel}")
            else:
                log("⚠️ Contact incomplet")

            bloc_adresse_label = page.locator("text=Adresse du cinéma")
            bloc_adresse_label.wait_for(timeout=5000)
            bloc_adresse = bloc_adresse_label.locator("xpath=following-sibling::*[1]")
            full_text = bloc_adresse.inner_text().strip().split("\n")
            adresse_lines = [line.strip() for line in full_text if line.strip()][:2]
            adresse = " - ".join(adresse_lines)
            log(f"🏠 Adresse : {adresse}")

        except Exception as e:
            log(f"⚠️ Erreur infos générales pour {c['name']} : {e}")
            continue

        for salle, cnc, capacite, equipement, format_proj in salles:
            data.append([
                c["name"], adresse,
                salle, cnc, capacite, equipement, format_proj,
                contact_nom, contact_mail, contact_tel
            ])

    if len(data) == 0:
        log("⚠️ Aucune donnée collectée, fallback de test ajouté.")
        data.append(["TEST", "TEST", "1", "000000", "100", "Numérique", "Numérique 2D", "Jean Dupont", "test@email.com", "0600000000"])

    log("💾 Écriture du fichier CSV...")
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Cinéma", "Adresse du cinéma",
            "Salle", "CNC", "Capacité", "Équipement", "Format de projection",
            "Nom contact", "Email", "Téléphone"
        ])
        writer.writerows(data)

    log("🧾 Génération du fichier JSON...")
    json_output = output_csv.replace(".csv", ".json")
    json_data = []

    for row in data:
        json_data.append({
            "cinema": row[0],
            "adresse": row[1],
            "salle": row[2],
            "cnc": row[3],
            "capacite": row[4],
            "equipement": row[5],
            "format_projection": row[6],
            "nom_contact": row[7],
            "email": row[8],
            "telephone": row[9]
        })

    with open(json_output, "w", encoding="utf-8") as f_json:
        json.dump(json_data, f_json, ensure_ascii=False, indent=2)

    log(f"✅ Extraction terminée : {len(data)} lignes exportées")
    log(f"📁 CSV : {output_csv}")
    log(f"📁 JSON : {json_output}")

    browser.close()


TEST