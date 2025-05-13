import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import calendar
import plotly.graph_objects as go
from icalendar import Calendar, Event, vDate
import tempfile
import os
import re
import openai
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize session state variables
if "events" not in st.session_state:
    st.session_state.events = []
if "messages" not in st.session_state:
    st.session_state.messages = []

def create_calendar_event(start_date, end_date, summary):
    cal = Calendar()
    cal.add('prodid', '-//Mon Calendrier//FR')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH')
    
    event = Event()
    event.add('summary', summary)
    event.add('dtstart', start_date)
    event.add('dtend', end_date)
    event.add('dtstamp', datetime.now())
    event.add('created', datetime.now())
    event.add('last-modified', datetime.now())
    event.add('status', 'CONFIRMED')
    event.add('transp', 'OPAQUE')
    cal.add_component(event)
    return cal

def parse_date(date_str):
    # Nettoyer la chaîne de caractères
    date_str = date_str.strip().lower()
    
    # Dictionnaire des mois en français
    mois_fr = {
        'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
        'juillet': 7, 'août': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12
    }
    
    # Pattern pour les dates au format "jour mois" ou "jour/mois"
    pattern_jour_mois = r'(\d{1,2})\s*(?:/|-)?\s*(' + '|'.join(mois_fr.keys()) + ')'
    match = re.search(pattern_jour_mois, date_str)
    
    if match:
        jour = int(match.group(1))
        mois = mois_fr[match.group(2)]
        annee = datetime.now().year
        return datetime(annee, mois, jour)
    
    # Pattern pour les dates au format "jour/mois/année"
    pattern_complet = r'(\d{1,2})/(\d{1,2})/(\d{4})'
    match = re.search(pattern_complet, date_str)
    
    if match:
        jour = int(match.group(1))
        mois = int(match.group(2))
        annee = int(match.group(3))
        return datetime(annee, mois, jour)
    
    # Pattern pour les dates avec seulement le jour (utilise le mois courant)
    pattern_jour_seul = r'(?:^|\D)(\d{1,2})(?:\D|$)'
    match = re.search(pattern_jour_seul, date_str)
    
    if match:
        jour = int(match.group(1))
        mois = datetime.now().month
        annee = datetime.now().year
        return datetime(annee, mois, jour)
    
    return None

def extract_events(text):
    events = []
    # Diviser le texte en phrases
    sentences = re.split(r'[.,]', text)
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        # Chercher une date dans la phrase
        date = parse_date(sentence)
        if date:
            # Prendre la phrase complète comme description de l'événement
            events.append({
                'date': date,
                'description': sentence
            })
    
    return events

# Configuration de l'API OpenAI
def setup_openai():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("La clé API OpenAI n'a pas été trouvée dans les variables d'environnement. Veuillez configurer le fichier .env")
        return False
    
    openai.api_key = api_key
    return True

def extract_events_with_gpt(text):
    if not setup_openai():
        st.warning("Veuillez entrer votre clé API OpenAI dans la barre latérale")
        return []

    prompt = f"""Analyse le texte suivant et extrait les événements avec leurs dates. 
    Retourne uniquement un JSON avec la structure suivante:
    {{
        "events": [
            {{
                "description": "description de l'événement",
                "date": "YYYY-MM-DD"
            }}
        ]
    }}

    Texte à analyser: {text}

    Assure-toi que:
    1. Les dates sont au format YYYY-MM-DD
    2. Si l'année n'est pas spécifiée, utilise l'année courante
    3. Inclus le contexte complet de l'événement dans la description
    4. Retourne uniquement le JSON, sans autre texte
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Tu es un assistant spécialisé dans l'extraction de dates et d'événements. Tu retournes uniquement du JSON valide."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        
        # Extraire le JSON de la réponse
        json_str = response.choices[0].message.content.strip()
        try:
            data = json.loads(json_str)
            
            # Convertir les dates en objets datetime
            events = []
            for event in data["events"]:
                date = datetime.strptime(event["date"], "%Y-%m-%d")
                events.append({
                    "date": date,
                    "description": event["description"]
                })
            
            return events
        except json.JSONDecodeError:
            st.error("Erreur lors de l'analyse de la réponse de l'IA. Veuillez réessayer.")
            return []
    except Exception as e:
        st.error(f"Erreur lors de l'analyse du texte: {str(e)}")
        return []

def generate_html_calendar(events):
    # Regrouper les événements par date
    event_by_date = {}
    for event in events:
        date = event['date'].date()
        if date not in event_by_date:
            event_by_date[date] = []
        event_by_date[date].append(event['description'])

    # Trouver tous les mois concernés
    if not events:
        return "<p>Aucun événement à afficher.</p>"
    min_date = min(e['date'] for e in events)
    max_date = max(e['date'] for e in events)
    months = []
    d = datetime(min_date.year, min_date.month, 1)
    while d <= datetime(max_date.year, max_date.month, 1):
        months.append((d.year, d.month))
        if d.month == 12:
            d = datetime(d.year + 1, 1, 1)
        else:
            d = datetime(d.year, d.month + 1, 1)

    # Couleurs pour les événements (Skyscanner style)
    color_palette = [
        "#e74c3c",  # rouge
        "#f39c12",  # orange
        "#3498db",  # bleu
        "#1abc9c",  # vert
        "#9b59b6",  # violet
        "#2ecc71",  # vert clair
        "#e67e22",  # orange foncé
        "#34495e",  # bleu foncé
    ]
    
    # Associer une couleur à chaque date d'événement (ou description unique)
    event_dates = sorted(event_by_date.keys())
    color_map = {date: color_palette[i % len(color_palette)] for i, date in enumerate(event_dates)}

    # Générer le HTML
    html = '''
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Mon Calendrier</title>
        <style>
            body { font-family: 'Inter', Arial, sans-serif; background: #fff; color: #222; margin: 0; padding: 0; }
            .calendar-container { display: flex; flex-wrap: wrap; gap: 32px; justify-content: center; margin: 32px 0; }
            .month { background: #fff; border-radius: 16px; box-shadow: 0 2px 8px #0001; padding: 24px; min-width: 320px; }
            .month-title { text-align: center; font-size: 1.4em; font-weight: 600; margin-bottom: 12px; text-transform: capitalize; }
            table { width: 100%; border-collapse: collapse; }
            th { color: #888; font-weight: 500; padding: 6px 0; }
            td { text-align: center; padding: 0; height: 38px; position: relative; }
            .day { display: flex; align-items: center; justify-content: center; width: 36px; height: 36px; margin: 2px auto; border-radius: 50%; font-weight: 500; transition: background 0.2s; }
            .event-day { color: #fff; font-weight: 600; cursor: pointer; }
            .event-tooltip {
                display: none;
                position: absolute;
                left: 50%;
                top: 110%;
                transform: translateX(-50%);
                background: #fff;
                color: #222;
                border: 1px solid #eee;
                border-radius: 8px;
                box-shadow: 0 2px 8px #0002;
                padding: 8px 14px;
                font-size: 0.95em;
                z-index: 10;
                min-width: 160px;
                max-width: 220px;
                white-space: pre-line;
            }
            .event-day:hover .event-tooltip {
                display: block;
            }
            @media (max-width: 900px) {
                .calendar-container { flex-direction: column; align-items: center; }
            }
        </style>
    </head>
    <body>
        <div class="calendar-container">
    '''
    months_fr = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    days_fr = ["L", "M", "M", "J", "V", "S", "D"]
    for year, month in months:
        cal = calendar.Calendar(firstweekday=0)  # Lundi
        html += f'<div class="month">'
        html += f'<div class="month-title">{months_fr[month-1]} {year}</div>'
        html += '<table>'
        html += '<tr>' + ''.join(f'<th>{d}</th>' for d in days_fr) + '</tr>'
        month_days = list(cal.itermonthdates(year, month))
        for week in range(0, len(month_days), 7):
            html += '<tr>'
            for day in month_days[week:week+7]:
                if day.month != month:
                    html += '<td></td>'
                else:
                    if day in event_by_date:
                        color = color_map[day]
                        tooltip = "<br/>".join(event_by_date[day])
                        html += f'<td><div class="day event-day" style="background:{color}">{day.day}<span class="event-tooltip">{tooltip}</span></div></td>'
                    else:
                        html += f'<td><div class="day">{day.day}</div></td>'
            html += '</tr>'
        html += '</table></div>'
    html += '</div></body></html>'
    return html

def main():
    st.title("🤖 Assistant de Planning")
    st.write("Dites-moi vos événements et je créerai un calendrier pour vous!")

    # Zone de chat
    user_input = st.chat_input("Entrez vos événements (ex: 'j'ai un tournage le 27 juin et je dois monter la vidéo le 23/07')")

    if user_input:
        # Ajouter le message de l'utilisateur
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Extraire les événements avec GPT
        new_events = extract_events_with_gpt(user_input)
        
        if new_events:
            st.success(f"J'ai trouvé {len(new_events)} événement(s) dans votre message!")
            # Ajouter les nouveaux événements à la liste existante
            st.session_state.events.extend(new_events)
            
            # Créer le calendrier ICS
            cal = Calendar()
            cal.add('prodid', '-//Mon Calendrier//FR')
            cal.add('version', '2.0')
            cal.add('calscale', 'GREGORIAN')
            cal.add('method', 'PUBLISH')
            
            for event in st.session_state.events:
                event_obj = Event()
                event_obj.add('summary', event['description'])
                event_obj.add('dtstart', vDate(event['date'].date()))
                event_obj.add('dtend', vDate((event['date'] + timedelta(days=1)).date()))
                event_obj.add('dtstamp', datetime.now())
                event_obj.add('created', datetime.now())
                event_obj.add('last-modified', datetime.now())
                event_obj.add('status', 'CONFIRMED')
                event_obj.add('transp', 'OPAQUE')
                cal.add_component(event_obj)

            # Créer les fichiers temporaires
            with tempfile.NamedTemporaryFile(delete=False, suffix='.ics') as f_ics:
                f_ics.write(cal.to_ical())
                temp_path_ics = f_ics.name

            with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as f_html:
                html_content = generate_html_calendar(st.session_state.events)
                f_html.write(html_content.encode('utf-8'))
                temp_path_html = f_html.name

            # Afficher les boutons de téléchargement
            col1, col2 = st.columns(2)
            with col1:
                with open(temp_path_ics, 'rb') as f:
                    st.download_button(
                        label="📥 Télécharger le calendrier (ICS)",
                        data=f,
                        file_name="planning.ics",
                        mime="text/calendar"
                    )
            
            with col2:
                with open(temp_path_html, 'rb') as f:
                    st.download_button(
                        label="📥 Télécharger le calendrier (HTML)",
                        data=f,
                        file_name="planning.html",
                        mime="text/html"
                    )

            # Nettoyer les fichiers temporaires
            os.unlink(temp_path_ics)
            os.unlink(temp_path_html)

            # Afficher une visualisation du calendrier
            st.write("### 📅 Aperçu du calendrier")
            fig = go.Figure()
            
            for event in st.session_state.events:
                fig.add_trace(go.Scatter(
                    x=[event['date']],
                    y=[0],
                    mode='markers+text',
                    name=event['description'],
                    text=[event['description']],
                    textposition="top center"
                ))
            
            fig.update_layout(
                title="Vue d'ensemble des événements",
                xaxis_title="Date",
                yaxis_visible=False,
                showlegend=False,
                height=400
            )
            st.plotly_chart(fig)
            
            # Afficher les événements détectés
            st.write("### 📝 Événements détectés")
            for event in st.session_state.events:
                st.write(f"- {event['description']} ({event['date'].strftime('%d/%m/%Y')})")
        else:
            st.warning("Je n'ai pas trouvé de dates dans votre message. Essayez de reformuler avec des dates explicites.")

        # Afficher l'historique du chat
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])

if __name__ == "__main__":
    main()
