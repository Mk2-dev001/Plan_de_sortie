import streamlit as st
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import io

# Configuration de la page
st.set_page_config(
    page_title="Assistant Business Plan - Application Cinéma",
    page_icon="🎬",
    layout="wide"
)

# Titre de l'application
st.title("🎬 Business Plan - Application de Planification Cinématographique")
st.markdown("""
Ce questionnaire vous guidera dans l'élaboration du business plan pour votre application de planification de projections cinématographiques.
""")

def generer_pdf(reponses):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    story = []

    # Style personnalisé pour les titres
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=20,
        textColor=colors.HexColor('#2E86C1')
    )

    # Style pour les sous-titres
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=10,
        textColor=colors.HexColor('#3498DB')
    )

    # Style pour le texte normal
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=10
    )

    # Titre principal
    story.append(Paragraph("Business Plan - Application Cinématographique", title_style))
    story.append(Spacer(1, 20))

    # Section 1: Informations générales
    story.append(Paragraph("1. Informations générales", subtitle_style))
    info_data = [
        ["Nom de l'entreprise", reponses.get('nom_entreprise', 'Non renseigné')],
        ["Date de lancement", str(reponses.get('date_creation', 'Non renseigné'))],
        ["Forme juridique", reponses.get('forme_juridique', 'Non renseigné')],
        ["Type de cinéma cible", reponses.get('type_cinema', 'Non renseigné')],
        ["Zone géographique", ", ".join(reponses.get('zone_geographique', ['Non renseigné']))],
        ["Nombre d'utilisateurs cible", str(reponses.get('nombre_utilisateurs_cible', 'Non renseigné'))]
    ]
    info_table = Table(info_data, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8F4F8')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2E86C1')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#D6EAF8'))
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))

    # Section 2: Analyse du marché
    story.append(Paragraph("2. Analyse du marché", subtitle_style))
    story.append(Paragraph("Description de l'application:", styles['Heading3']))
    story.append(Paragraph(reponses.get('description_application', 'Non renseigné'), normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Clientèle cible:", styles['Heading3']))
    story.append(Paragraph(", ".join(reponses.get('cible_principale', ['Non renseigné'])), normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Analyse de la concurrence:", styles['Heading3']))
    story.append(Paragraph(reponses.get('concurrence', 'Non renseigné'), normal_style))
    story.append(Spacer(1, 20))

    # Section 3: Stratégie marketing
    story.append(Paragraph("3. Stratégie marketing", subtitle_style))
    story.append(Paragraph("Positionnement:", styles['Heading3']))
    story.append(Paragraph(reponses.get('positionnement', 'Non renseigné'), normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Canaux d'acquisition:", styles['Heading3']))
    story.append(Paragraph(", ".join(reponses.get('canaux_acquisition', ['Non renseigné'])), normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Modèle économique:", styles['Heading3']))
    story.append(Paragraph(reponses.get('strategie_prix', 'Non renseigné'), normal_style))
    story.append(Spacer(1, 20))

    # Section 4: Plan opérationnel
    story.append(Paragraph("4. Plan opérationnel", subtitle_style))
    story.append(Paragraph("Fonctionnalités principales:", styles['Heading3']))
    story.append(Paragraph(reponses.get('fonctionnalites_principales', 'Non renseigné'), normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Technologies utilisées:", styles['Heading3']))
    story.append(Paragraph(", ".join(reponses.get('technologies', ['Non renseigné'])), normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Infrastructure nécessaire:", styles['Heading3']))
    story.append(Paragraph(reponses.get('infrastructure', 'Non renseigné'), normal_style))
    story.append(Spacer(1, 20))

    # Section 5: Plan financier
    story.append(Paragraph("5. Plan financier", subtitle_style))
    finance_data = [
        ["Investissement initial", f"{reponses.get('investissement_initial', 0):,.2f} €"],
        ["Prix de l'abonnement mensuel", f"{reponses.get('prix_abonnement', 0):,.2f} €"],
        ["Coût opérationnel mensuel", f"{reponses.get('cout_operationnel_mensuel', 0):,.2f} €"],
        ["Objectif d'utilisateurs payants", str(reponses.get('objectif_utilisateurs_payants', 0))]
    ]
    finance_table = Table(finance_data, colWidths=[3*inch, 3*inch])
    finance_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8F4F8')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2E86C1')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#D6EAF8'))
    ]))
    story.append(finance_table)
    story.append(Spacer(1, 20))

    # Section 6: Analyse des risques
    story.append(Paragraph("6. Analyse des risques", subtitle_style))
    story.append(Paragraph("Risques techniques:", styles['Heading3']))
    story.append(Paragraph(reponses.get('risques_techniques', 'Non renseigné'), normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Risques liés au marché:", styles['Heading3']))
    story.append(Paragraph(reponses.get('risques_marche', 'Non renseigné'), normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Stratégies de mitigation:", styles['Heading3']))
    story.append(Paragraph(reponses.get('strategies_mitigation', 'Non renseigné'), normal_style))

    # Génération du PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

# Initialisation des réponses
if 'reponses' not in st.session_state:
    st.session_state.reponses = {}

# Section 1: Informations générales
st.header("1️⃣ Informations générales")
col1, col2 = st.columns(2)

with col1:
    st.session_state.reponses['nom_entreprise'] = st.text_input("Nom de l'entreprise")
    st.session_state.reponses['date_creation'] = st.date_input("Date de lancement prévue")
    st.session_state.reponses['forme_juridique'] = st.selectbox(
        "Forme juridique",
        ["SARL", "SAS", "EURL", "Auto-entrepreneur", "Autre"]
    )

with col2:
    st.session_state.reponses['type_cinema'] = st.selectbox(
        "Type de cinéma cible",
        ["Cinéma indépendant", "Réseau de cinémas", "Distributeur", "Producteur", "Autre"]
    )
    st.session_state.reponses['zone_geographique'] = st.multiselect(
        "Zone géographique cible",
        ["France", "Europe", "Amérique du Nord", "Asie", "Autre"]
    )
    st.session_state.reponses['nombre_utilisateurs_cible'] = st.number_input(
        "Nombre d'utilisateurs cible (année 1)",
        min_value=0,
        step=100
    )

# Section 2: Analyse du marché
st.header("2️⃣ Analyse du marché")
st.session_state.reponses['description_application'] = st.text_area(
    "Description détaillée de l'application",
    height=100,
    help="Décrivez les fonctionnalités principales comme la planification de projections, l'analyse de données, etc."
)
st.session_state.reponses['cible_principale'] = st.multiselect(
    "Clientèle cible principale",
    ["Distributeurs", "Producteurs", "Exploitants de salles", "Organisateurs d'événements", "Autre"]
)
st.session_state.reponses['concurrence'] = st.text_area(
    "Analyse de la concurrence",
    height=100,
    help="Listez les solutions concurrentes existantes et leurs points forts/faibles"
)

# Section 3: Stratégie marketing
st.header("3️⃣ Stratégie marketing")
st.session_state.reponses['positionnement'] = st.text_area(
    "Positionnement sur le marché",
    height=100,
    help="Comment votre application se différencie-t-elle des solutions existantes ?"
)
st.session_state.reponses['canaux_acquisition'] = st.multiselect(
    "Canaux d'acquisition clients",
    ["Salons professionnels", "Réseaux sociaux", "Email marketing", "Partenariats", "Conférences", "Autre"]
)
st.session_state.reponses['strategie_prix'] = st.selectbox(
    "Modèle économique",
    ["Abonnement mensuel", "Abonnement annuel", "Paiement à l'utilisation", "Freemium", "Licence"] 
)

# Section 4: Plan opérationnel
st.header("4️⃣ Plan opérationnel")
st.session_state.reponses['fonctionnalites_principales'] = st.text_area(
    "Fonctionnalités principales",
    height=100,
    help="Listez les fonctionnalités clés de l'application"
)
st.session_state.reponses['technologies'] = st.multiselect(
    "Technologies utilisées",
    ["Python", "Streamlit", "OpenAI API", "Base de données", "Cloud", "Autre"]
)
st.session_state.reponses['infrastructure'] = st.text_area(
    "Infrastructure nécessaire",
    height=100,
    help="Décrivez les besoins en infrastructure (serveurs, stockage, etc.)"
)

# Section 5: Plan financier
st.header("5️⃣ Plan financier")
col1, col2 = st.columns(2)

with col1:
    st.session_state.reponses['investissement_initial'] = st.number_input(
        "Investissement initial (€)",
        min_value=0,
        step=1000
    )
    st.session_state.reponses['prix_abonnement'] = st.number_input(
        "Prix de l'abonnement mensuel (€)",
        min_value=0,
        step=10
    )

with col2:
    st.session_state.reponses['cout_operationnel_mensuel'] = st.number_input(
        "Coût opérationnel mensuel (€)",
        min_value=0,
        step=100
    )
    st.session_state.reponses['objectif_utilisateurs_payants'] = st.number_input(
        "Objectif d'utilisateurs payants (année 1)",
        min_value=0,
        step=10
    )

# Section 6: Analyse des risques
st.header("6️⃣ Analyse des risques")
st.session_state.reponses['risques_techniques'] = st.text_area(
    "Risques techniques",
    height=100,
    help="Ex: Problèmes de scalabilité, dépendance aux APIs externes, etc."
)
st.session_state.reponses['risques_marche'] = st.text_area(
    "Risques liés au marché",
    height=100,
    help="Ex: Adoption lente, concurrence, etc."
)
st.session_state.reponses['strategies_mitigation'] = st.text_area(
    "Stratégies de mitigation des risques",
    height=100
)

# Bouton pour générer le business plan
if st.button("Générer le Business Plan"):
    pdf_buffer = generer_pdf(st.session_state.reponses)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"business_plan_cinema_{timestamp}.pdf"
    
    # Sauvegarde du PDF
    with open(pdf_filename, "wb") as f:
        f.write(pdf_buffer.getvalue())
    
    st.success(f"Votre business plan a été généré !")
    
    # Bouton pour télécharger le PDF
    with open(pdf_filename, "rb") as f:
        st.download_button(
            label="📥 Télécharger le PDF",
            data=f,
            file_name=pdf_filename,
            mime="application/pdf"
        ) 