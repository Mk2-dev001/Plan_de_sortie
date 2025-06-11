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
if "rejected_events" not in st.session_state:
    st.session_state.rejected_events = []

def create_calendar_event(start_date, end_date, summary):
    cal = Calendar()
    cal.add('prodid', '-//Mon Calendrier//FR')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH')
    
    event = Event()
    event.add('summary', summary)
    
    # Si l'heure est spécifiée (différente de minuit), on utilise dtstart/dtend avec l'heure
    if start_date.hour != 0 or start_date.minute != 0:
        event.add('dtstart', start_date)
        # Si end_date n'a pas d'heure spécifiée, on ajoute 1 heure par défaut
        if end_date.hour == 0 and end_date.minute == 0:
            end_date = end_date.replace(hour=start_date.hour + 1, minute=start_date.minute)
        event.add('dtend', end_date)
    else:
        # Si pas d'heure spécifiée, on utilise vDate pour un événement sur toute la journée
        event.add('dtstart', vDate(start_date.date()))
        event.add('dtend', vDate(end_date.date()))
    
    event.add('dtstamp', datetime.now())
    event.add('created', datetime.now())
    event.add('last-modified', datetime.now())
    event.add('status', 'CONFIRMED')
    event.add('transp', 'OPAQUE')
    cal.add_component(event)
    return cal

def parse_date(date_str):
    date_str = date_str.strip().lower()
    now = datetime.now()

    mois_fr = {
        'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
        'juillet': 7, 'août': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12
    }

    # Expressions relatives simples
    if "demain" in date_str:
        return now + timedelta(days=1)
    elif "après-demain" in date_str:
        return now + timedelta(days=2)
    elif "semaine prochaine" in date_str:
        return now + timedelta(days=7)
    elif "mois prochain" in date_str:
        if now.month == 12:
            return datetime(now.year + 1, 1, now.day)
        return datetime(now.year, now.month + 1, now.day)

    # Pattern : jour mois écrit explicitement avec heure optionnelle
    pattern_jour_mois = r'(?:le\s+)?(\d{1,2})\s*(?:/|-)?\s*(' + '|'.join(mois_fr.keys()) + ')(?:\s+à\s+(\d{1,2})(?::(\d{2}))?)?'
    match = re.search(pattern_jour_mois, date_str)
    if match:
        jour = int(match.group(1))
        mois = mois_fr[match.group(2)]
        annee = now.year
        heure = int(match.group(3)) if match.group(3) else 9  # 9h par défaut
        minute = int(match.group(4)) if match.group(4) else 0
        date_detectee = datetime(annee, mois, jour, heure, minute)
        if date_detectee < now:
            date_detectee = date_detectee.replace(year=annee + 1)
        return date_detectee

    # Pattern complet JJ/MM/AAAA avec heure optionnelle
    pattern_complet = r'(?:le\s+)?(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+à\s+(\d{1,2})(?::(\d{2}))?)?'
    match = re.search(pattern_complet, date_str)
    if match:
        jour, mois, annee = int(match.group(1)), int(match.group(2)), int(match.group(3))
        heure = int(match.group(4)) if match.group(4) else 9
        minute = int(match.group(5)) if match.group(5) else 0
        date_detectee = datetime(annee, mois, jour, heure, minute)
        if date_detectee < now:
            date_detectee = date_detectee.replace(year=now.year)
            if date_detectee < now:
                date_detectee = date_detectee.replace(year=now.year + 1)
        return date_detectee

    # Pattern jour seul avec heure optionnelle
    pattern_jour_seul = r'(?:le\s+)?(\d{1,2})(?:\s+à\s+(\d{1,2})(?::(\d{2}))?)?'
    match = re.search(pattern_jour_seul, date_str)
    if match:
        jour = int(match.group(1))
        heure = int(match.group(2)) if match.group(2) else 9
        minute = int(match.group(3)) if match.group(3) else 0
        mois = now.month
        annee = now.year
        date_detectee = datetime(annee, mois, jour, heure, minute)
        if date_detectee < now:
            if mois == 12:
                mois = 1
                annee += 1
            else:
                mois += 1
            date_detectee = datetime(annee, mois, jour, heure, minute)
        return date_detectee

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

    current_date = datetime.now().strftime("%d/%m/%Y")
    prompt = f"""Analyse le texte suivant et extrait les événements avec leurs dates. 
    Contexte temporel : Nous sommes le {current_date}.
    
    Retourne uniquement un JSON avec la structure suivante:
    {{
        "events": [
            {{
                "description": "description de l'événement",
                "date": "YYYY-MM-DD",
                "time": "HH:MM" (optionnel)
            }}
        ]
    }}

    Texte à analyser: {text}

    Règles importantes:
    1. Les dates sont au format YYYY-MM-DD
    2. Si l'année n'est pas spécifiée, utilise l'année courante ({datetime.now().year})
    3. Si le jour est inférieur au jour actuel ({datetime.now().day}), passe au mois suivant
    4. Si l'heure n'est pas spécifiée, utilise 09:00
    5. Inclus le contexte complet de l'événement dans la description
    6. Retourne uniquement le JSON, sans autre texte
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
        
        json_str = response.choices[0].message.content.strip()
        try:
            data = json.loads(json_str)
            
            events = []
            rejected_events = []
            for event in data["events"]:
                try:
                    date = datetime.strptime(event["date"], "%Y-%m-%d")
                    if "time" in event:
                        time = datetime.strptime(event["time"], "%H:%M").time()
                        date = datetime.combine(date.date(), time)
                    else:
                        date = datetime.combine(date.date(), datetime.strptime("09:00", "%H:%M").time())
                    
                    if date.date() >= datetime.now().date():
                        events.append({
                            "date": date,
                            "description": event["description"]
                        })
                    else:
                        rejected_events.append({
                            "description": event["description"],
                            "date": date,
                            "reason": "Date dans le passé"
                        })
                except ValueError as e:
                    rejected_events.append({
                        "description": event["description"],
                        "reason": f"Format de date invalide: {str(e)}"
                    })
            
            if rejected_events:
                st.warning("Certains événements ont été ignorés :")
                for event in rejected_events:
                    st.info(f"- {event['description']} : {event['reason']}")
            
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

    color_palette = [
        "#e74c3c", "#f39c12", "#3498db", "#1abc9c",
        "#9b59b6", "#2ecc71", "#e67e22", "#34495e"
    ]
    
    event_dates = sorted(event_by_date.keys())
    color_map = {date: color_palette[i % len(color_palette)] for i, date in enumerate(event_dates)}

    html = '''
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mon Calendrier</title>
        <style>
            :root {
                --primary-color: #3498db;
                --text-color: #2c3e50;
                --bg-color: #f8f9fa;
                --border-radius: 12px;
                --shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
            
            body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                background: var(--bg-color);
                color: var(--text-color);
                margin: 0;
                padding: 20px;
                line-height: 1.6;
            }
            
            .calendar-container {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 24px;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }
            
            .month {
                background: white;
                border-radius: var(--border-radius);
                box-shadow: var(--shadow);
                padding: 20px;
                transition: transform 0.2s;
            }
            
            .month:hover {
                transform: translateY(-2px);
            }
            
            .month-title {
                text-align: center;
                font-size: 1.4em;
                font-weight: 600;
                margin-bottom: 16px;
                color: var(--primary-color);
            }
            
            table {
                width: 100%;
                border-collapse: collapse;
            }
            
            th {
                color: #666;
                font-weight: 500;
                padding: 8px 0;
                font-size: 0.9em;
            }
            
            td {
                text-align: center;
                padding: 4px;
                height: 40px;
                position: relative;
            }
            
            .day {
                display: flex;
                align-items: center;
                justify-content: center;
                width: 36px;
                height: 36px;
                margin: 2px auto;
                border-radius: 50%;
                font-weight: 500;
                transition: all 0.2s;
            }
            
            .event-day {
                color: white;
                font-weight: 600;
                cursor: pointer;
            }
            
            .event-tooltip {
                display: none;
                position: absolute;
                left: 50%;
                top: 110%;
                transform: translateX(-50%);
                background: white;
                color: var(--text-color);
                border-radius: 8px;
                box-shadow: var(--shadow);
                padding: 12px 16px;
                font-size: 0.95em;
                z-index: 10;
                min-width: 200px;
                max-width: 280px;
                white-space: pre-line;
            }
            
            .event-day:hover .event-tooltip {
                display: block;
            }
            
            @media (max-width: 768px) {
                .calendar-container {
                    grid-template-columns: 1fr;
                    padding: 10px;
                }
                
                .month {
                    padding: 15px;
                }
                
                .event-tooltip {
                    min-width: 160px;
                }
            }
        </style>
    </head>
    <body>
        <div class="calendar-container">
    '''
    
    months_fr = ["janvier", "février", "mars", "avril", "mai", "juin", 
                "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    days_fr = ["L", "M", "M", "J", "V", "S", "D"]
    
    for year, month in months:
        cal = calendar.Calendar(firstweekday=0)
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
    st.set_page_config(
        page_title="Assistant de Planning",
        page_icon="📅",
        layout="wide"
    )
    
    st.title("🤖 Assistant de Planning")
    st.write("Dites-moi vos événements et je créerai un calendrier pour vous!")

    # Zone de chat
    user_input = st.chat_input("Entrez vos événements (ex: 'j'ai un tournage le 27 juin et je dois monter la vidéo le 23/07')")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        new_events = extract_events_with_gpt(user_input)
        
        if new_events:
            st.success(f"J'ai trouvé {len(new_events)} événement(s) dans votre message!")
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
                
                if event['date'].hour != 0 or event['date'].minute != 0:
                    event_obj.add('dtstart', event['date'])
                    end_date = event['date'] + timedelta(hours=1)
                    event_obj.add('dtend', end_date)
                else:
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

            # Interface de téléchargement améliorée
            st.write("### 📥 Télécharger le calendrier")
            export_format = st.multiselect(
                "Choisissez le format d'export",
                ["ICS (Google Calendar, Apple Calendar)", "HTML (Vue web)"],
                default=["ICS (Google Calendar, Apple Calendar)"]
            )

            if "ICS (Google Calendar, Apple Calendar)" in export_format:
                with open(temp_path_ics, 'rb') as f:
                    st.download_button(
                        label="📥 Télécharger le calendrier (ICS)",
                        data=f,
                        file_name="planning.ics",
                        mime="text/calendar"
                    )
            
            if "HTML (Vue web)" in export_format:
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
                height=400,
                template="plotly_white"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Afficher les événements détectés
            st.write("### 📝 Événements détectés")
            for event in st.session_state.events:
                st.write(f"- {event['description']} ({event['date'].strftime('%d/%m/%Y %H:%M')})")
        else:
            st.warning("Je n'ai pas trouvé de dates dans votre message. Essayez de reformuler avec des dates explicites.")

        # Afficher l'historique du chat
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])

if __name__ == "__main__":
    main()
