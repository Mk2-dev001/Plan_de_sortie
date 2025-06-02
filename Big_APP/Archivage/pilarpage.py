import streamlit as st
import json
from openai import OpenAI
import logging
from datetime import datetime
import os
import re
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from app import process_word_document, load_wordpress_db
import io

# Configuration du logging
log_filename = f'pillar_page_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
logging.basicConfig(
    filename=log_filename,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuration du client OpenAI
client = OpenAI(api_key="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")

def get_latest_log_content():
    """Récupère le contenu du dernier fichier de log."""
    try:
        if os.path.exists(log_filename):
            with open(log_filename, 'r', encoding='utf-8') as f:
                return f.read()
        return "Aucun log disponible pour le moment."
    except Exception as e:
        return f"Erreur lors de la lecture des logs: {str(e)}"

def generate_pillar_page(topic, wp_db):
    """Génère une page pilier optimisée SEO sur un sujet donné."""
    try:
        logging.info(f"Génération d'une page pilier sur le sujet: {topic}")
        
        if not wp_db:
            logging.error("La base de données WordPress est vide")
            return None
            
        # Extraire les titres disponibles pour l'inspiration
        available_titles = [item["title"] for item in wp_db]
        titles_str = "\n".join(available_titles[:50])  # Limiter à 50 titres pour le contexte
        
        logging.info("Envoi de la requête à GPT-4...")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": f"""Tu es un expert SEO et créateur de contenu qui génère des pages pilier optimisées.
                Ta tâche est de créer une page pilier complète et optimisée SEO sur le sujet demandé.
                
                Articles disponibles pour inspiration:
                {titles_str}
                
                Règles de création:
                1. Structure de texte brut pour Word:
                   - Titre 1 pour le titre principal
                   - Titre 2 pour les sections principales
                   - Titre 3 pour les sous-sections
                
                2. Optimisation SEO:
                   - Titre principal accrocheur et optimisé avec le mot-clé exact
                   - Introduction captivante (150-200 mots) avec mots-clés naturels
                   - Structure hiérarchique claire
                   - Paragraphes courts et aérés
                   - Utilisation naturelle des mots-clés
                
                3. Contenu:
                   - Long et détaillé (minimum 1500 mots)
                   - Professionnel et engageant
                   - Basé uniquement sur les sujets des articles disponibles
                   - Sans balises de lien ou formatage
                   - Avec des listes à puces quand pertinent
                   - Section FAQ obligatoire avec 4-5 questions fréquentes
                
                4. Style et ton:
                   - Informatif et accessible
                   - Formulations engageantes
                   - Pas de contenu superflu
                   - Priorité à la clarté et la lisibilité
                   - Rythme dynamique
                
                5. Format de réponse:
                {{
                    "title": "Titre principal optimisé SEO",
                    "content": "Introduction de 150-200 mots",
                    "sections": [
                        {{
                            "title": "Titre de la section",
                            "level": 2,
                            "content": "Contenu de la section"
                        }},
                        {{
                            "title": "Titre de la sous-section",
                            "level": 3,
                            "content": "Contenu de la sous-section"
                        }},
                        {{
                            "title": "FAQ",
                            "level": 2,
                            "content": "4-5 questions fréquentes avec réponses détaillées"
                        }}
                    ]
                }}
                
                Important: 
                - Ne pas inclure de balises de lien ou de formatage dans le contenu
                - Les liens seront ajoutés automatiquement par un programme externe
                - Assurez-vous que chaque section est séparée par une ligne vide
                - Utilisez des mots-clés pertinents qui correspondent aux titres d'articles disponibles"""},
                {"role": "user", "content": f"Crée une page pilier optimisée SEO sur le sujet: {topic}"}
            ],
            temperature=0.7,
            max_tokens=2500
        )
        
        content = response.choices[0].message.content
        logging.debug(f"Réponse GPT reçue: {content}")
        
        try:
            # Nettoyer le contenu JSON avant de le parser
            cleaned_content = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', content)
            cleaned_content = re.sub(r'^\s+', '', cleaned_content, flags=re.MULTILINE)
            
            result = json.loads(cleaned_content)
            logging.info("Parsing JSON réussi")
            
            # Vérification de la structure du résultat
            required_fields = ["title", "content", "sections"]
            missing_fields = [field for field in required_fields if field not in result]
            
            if missing_fields:
                logging.error(f"Champs manquants dans la réponse: {missing_fields}")
                return None
                
            # Formater le contenu avec une meilleure structure
            formatted_content = f"{result['title']}\n\n"
            formatted_content += f"{result['content']}\n\n"
            
            for section in result['sections']:
                level = section['level']
                title = section['title']
                content = section['content']
                
                # Ajouter le titre avec le bon niveau
                formatted_content += f"{'=' * (level + 1)} {title} {'=' * (level + 1)}\n\n"
                # Ajouter le contenu
                formatted_content += f"{content}\n\n"
            
            result['content'] = formatted_content
            logging.info(f"Page pilier générée avec succès. Titre: {result['title']}")
            return result
            
        except json.JSONDecodeError as e:
            logging.error(f"Erreur de parsing JSON: {str(e)}")
            logging.error(f"Contenu reçu: {content}")
            return None
            
    except Exception as e:
        logging.error(f"Erreur lors de la génération de la page pilier: {str(e)}")
        logging.exception("Trace complète de l'erreur:")
        return None

def analyze_logs(log_content):
    """Analyse le contenu des logs et retourne un résumé des erreurs."""
    try:
        lines = log_content.split('\n')
        error_summary = []
        current_error = None
        
        for line in lines:
            if 'ERROR' in line:
                # Nouvelle erreur détectée
                if current_error:
                    error_summary.append(current_error)
                current_error = {
                    'timestamp': line.split(' - ')[0] if ' - ' in line else 'N/A',
                    'message': line.split('ERROR - ')[-1] if 'ERROR - ' in line else line,
                    'trace': []
                }
            elif current_error and line.strip():
                # Ajouter les lignes de trace à l'erreur courante
                current_error['trace'].append(line.strip())
        
        # Ajouter la dernière erreur si elle existe
        if current_error:
            error_summary.append(current_error)
            
        return error_summary
    except Exception as e:
        return [{'message': f'Erreur lors de l\'analyse des logs: {str(e)}'}]

def display_error_summary(error_summary):
    """Affiche un résumé des erreurs dans l'interface Streamlit."""
    if not error_summary:
        st.info("Aucune erreur n'a été détectée dans les logs.")
        return
        
    st.error("📊 Résumé des erreurs détectées:")
    
    for i, error in enumerate(error_summary, 1):
        with st.expander(f"Erreur #{i} - {error['message']}", expanded=True):
            st.write(f"**Timestamp:** {error['timestamp']}")
            st.write(f"**Message:** {error['message']}")
            if error['trace']:
                st.write("**Trace complète:**")
                st.code('\n'.join(error['trace']))

def save_to_word(pillar_page, topic):
    """Sauvegarde la page pilier dans un fichier Word avec des hyperliens."""
    try:
        # Créer d'abord le document Word de base
        doc = Document()
        
        # Titre principal
        title = doc.add_heading(pillar_page['title'], level=1)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Contenu
        content = pillar_page['content']
        sections = content.split('\n\n')
        
        for section in sections:
            if section.strip():
                # Détecter les niveaux de titre
                if section.startswith('==='):
                    # Titre de niveau 2
                    title_text = section.replace('===', '').strip()
                    doc.add_heading(title_text, level=2)
                elif section.startswith('===='):
                    # Titre de niveau 3
                    title_text = section.replace('====', '').strip()
                    doc.add_heading(title_text, level=3)
                else:
                    # Paragraphe normal
                    p = doc.add_paragraph(section.strip())
                    p.style = 'Normal'
        
        # Sauvegarder le document dans un fichier temporaire
        temp_filename = f"temp_page_pilier_{topic.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        doc.save(temp_filename)
        
        try:
            # Ouvrir le fichier temporaire et le traiter pour les hyperliens
            with open(temp_filename, 'rb') as f:
                final_doc = process_word_document(f)
            
            if final_doc:
                # Sauvegarder le fichier final
                filename = f"page_pilier_{topic.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
                # Écrire le contenu du BytesIO dans le fichier
                with open(filename, 'wb') as f:
                    f.write(final_doc.getvalue())
                logging.info(f"Document Word sauvegardé avec succès: {filename}")
                return filename
            else:
                logging.error("Erreur lors du traitement des hyperliens")
                return None
                
        finally:
            # Nettoyer le fichier temporaire
            try:
                os.remove(temp_filename)
            except:
                pass
            
    except Exception as e:
        logging.error(f"Erreur lors de la sauvegarde du fichier Word: {str(e)}")
        logging.exception("Trace complète de l'erreur:")
        return None

def main():
    """Interface principale de l'application Streamlit."""
    st.title("📚 Générateur de Pages Pilier")
    st.write("Générez des pages pilier optimisées basées sur votre contenu existant")
    
    # Informations sur l'application
    with st.expander("ℹ️ Informations"):
        st.write("""
        Cette application:
        - Génère des pages pilier optimisées pour le SEO
        - Utilise uniquement le contenu de votre site existant
        - Crée automatiquement des liens internes pertinents
        - Structure le contenu de manière professionnelle
        - Exporte le résultat en format Word (.docx)
        """)
    
    # Champ de saisie pour le sujet
    topic = st.text_input(
        "Sujet de la page pilier",
        help="Entrez le sujet principal de la page pilier que vous souhaitez créer"
    )
    
    if topic:
        # Bouton pour générer la page pilier
        if st.button("🔄 Générer la page pilier", type="primary"):
            with st.spinner("Génération en cours..."):
                try:
                    # Charger la base de données WordPress
                    logging.info("Chargement de la base de données WordPress...")
                    wp_db = load_wordpress_db()
                    if not wp_db:
                        error_msg = "Impossible de charger la base de données WordPress"
                        logging.error(error_msg)
                        st.error(error_msg)
                        return
                    
                    logging.info(f"Base de données WordPress chargée avec {len(wp_db)} articles")
                    
                    # Générer la page pilier
                    pillar_page = generate_pillar_page(topic, wp_db)
                    
                    if pillar_page:
                        # Sauvegarder dans un fichier Word
                        word_file = save_to_word(pillar_page, topic)
                        
                        if word_file:
                            st.success(f"✅ Page pilier générée avec succès! Fichier sauvegardé: {word_file}")
                            
                            # Afficher un aperçu du contenu
                            st.markdown("### Aperçu du contenu")
                            st.markdown(f"**Titre:** {pillar_page['title']}")
                            st.markdown("**Contenu:**")
                            st.text(pillar_page['content'])
                        else:
                            st.error("❌ Erreur lors de la sauvegarde du fichier Word")
                    else:
                        error_msg = "❌ Erreur lors de la génération de la page pilier. Consultez les logs pour plus de détails."
                        logging.error(error_msg)
                        st.error(error_msg)
                        
                        # Afficher l'analyse des logs
                        log_content = get_latest_log_content()
                        error_summary = analyze_logs(log_content)
                        display_error_summary(error_summary)
                        
                        # Afficher les logs complets
                        with st.expander("📋 Logs complets"):
                            st.code(log_content)
                    
                except Exception as e:
                    error_msg = f"❌ Une erreur s'est produite: {str(e)}"
                    logging.error(error_msg)
                    logging.exception("Trace complète de l'erreur:")
                    st.error(error_msg)
                    
                    # Afficher l'analyse des logs
                    log_content = get_latest_log_content()
                    error_summary = analyze_logs(log_content)
                    display_error_summary(error_summary)
                    
                    # Afficher les logs complets
                    with st.expander("📋 Logs complets"):
                        st.code(log_content)

if __name__ == "__main__":
    main()