import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import json
import re

# --- Nettoyage du XML brut ---
def nettoyer_xml(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8', errors='replace') as f:
        contenu = f.read()

    # Corriger les caractères & non échappés (hors entités valides)
    contenu = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;)', '&amp;', contenu)
    # Supprimer les caractères UTF illégaux (invisibles ou invalides XML)
    contenu = re.sub(r'[^\x09\x0A\x0D\x20-\x7F\u00A0-\uFFFF]', '', contenu)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(contenu)

# --- Parsing propre du XML vers JSON ---
def parser_xml(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    ns = {
        'content': 'http://purl.org/rss/1.0/modules/content/',
        'dc': 'http://purl.org/dc/elements/1.1/',
        'wp': 'http://wordpress.org/export/1.2/',
        'excerpt': 'http://wordpress.org/export/1.2/excerpt/',
    }

    data = []

    for item in root.findall('./channel/item'):
        post_type = item.findtext('wp:post_type', namespaces=ns)
        if post_type not in ['post', 'page']:
            continue  # Ignore les CPT pour l'instant

        post = {
            'title': item.findtext('title'),
            'date': item.findtext('wp:post_date', namespaces=ns),
            'author': item.findtext('dc:creator', namespaces=ns),
            'excerpt': item.findtext('excerpt:encoded', namespaces=ns) or '',
            'slug': item.findtext('wp:post_name', namespaces=ns),
            'status': item.findtext('wp:status', namespaces=ns),
            'type': post_type,
            'tags': [],
            'categories': [],
            'content': '',
            'link': item.findtext('link')
        }

        # Nettoyer le contenu HTML vers texte brut lisible
        content_html = item.findtext('content:encoded', namespaces=ns) or ''
        soup = BeautifulSoup(content_html, 'html.parser')
        post['content'] = soup.get_text(separator='\n').strip()

        # Récupération des catégories et tags
        for cat in item.findall('category'):
            domain = cat.attrib.get('domain')
            if domain == 'category':
                post['categories'].append(cat.text)
            elif domain == 'post_tag':
                post['tags'].append(cat.text)

        data.append(post)

    return data

# --- Pipeline complet ---
if __name__ == "__main__":
    input_file = 'TC.xml'
    cleaned_file = 'TC_nettoye.xml'
    output_json = 'export_wordpress_propre.json'

    nettoyer_xml(input_file, cleaned_file)
    posts = parser_xml(cleaned_file)

    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

    print(f"✅ Fichier JSON généré : {output_json} ({len(posts)} posts/pages)")
