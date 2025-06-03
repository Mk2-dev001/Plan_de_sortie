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
    page_title="Business Plan - Projet Cinématographique",
    page_icon="🎬",
    layout="wide"
)

# Titre de l'application
st.title("🎬 Business Plan - Projet Cinématographique")
st.markdown("""
Ce questionnaire vous guidera dans l'élaboration du business plan pour votre projet de film.
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
    story.append(Paragraph("Business Plan - Projet Cinématographique", title_style))
    story.append(Spacer(1, 20))

    # Section 1: Informations générales du projet
    story.append(Paragraph("1. Informations générales du projet", subtitle_style))
    info_data = [
        ["Titre du film", reponses.get('titre_film', 'Non renseigné')],
        ["Durée", reponses.get('duree', 'Non renseigné')],
        ["Budget de production", f"{reponses.get('budget_production', 0):,.2f} € HT"],
        ["Budget de commercialisation", reponses.get('budget_commercialisation', 'Non renseigné')],
        ["Date de tournage", reponses.get('date_tournage', 'Non renseigné')],
        ["Lieu de tournage", reponses.get('lieu_tournage', 'Non renseigné')]
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

    # Section 2: Synopsis et Concept
    story.append(Paragraph("2. Synopsis et Concept", subtitle_style))
    story.append(Paragraph("Synopsis:", styles['Heading3']))
    story.append(Paragraph(reponses.get('synopsis', 'Non renseigné'), normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Format et Style:", styles['Heading3']))
    story.append(Paragraph(reponses.get('format_style', 'Non renseigné'), normal_style))
    story.append(Spacer(1, 20))

    # Section 3: Partenaires et Distribution
    story.append(Paragraph("3. Partenaires et Distribution", subtitle_style))
    story.append(Paragraph("Production:", styles['Heading3']))
    story.append(Paragraph(reponses.get('production', 'Non renseigné'), normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Distribution:", styles['Heading3']))
    story.append(Paragraph(reponses.get('distribution', 'Non renseigné'), normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Partenaires:", styles['Heading3']))
    story.append(Paragraph(reponses.get('partenaires', 'Non renseigné'), normal_style))
    story.append(Spacer(1, 20))

    # Section 4: Stratégie de Diffusion
    story.append(Paragraph("4. Stratégie de Diffusion", subtitle_style))
    story.append(Paragraph("Sortie en salles:", styles['Heading3']))
    story.append(Paragraph(reponses.get('sortie_salles', 'Non renseigné'), normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Diffusion digitale:", styles['Heading3']))
    story.append(Paragraph(reponses.get('diffusion_digitale', 'Non renseigné'), normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Stratégie marketing:", styles['Heading3']))
    story.append(Paragraph(reponses.get('strategie_marketing', 'Non renseigné'), normal_style))
    story.append(Spacer(1, 20))

    # Section 5: Budget et Financement
    story.append(Paragraph("5. Budget et Financement", subtitle_style))
    finance_data = [
        ["Budget de production", f"{reponses.get('budget_production', 0):,.2f} € HT"],
        ["Budget de commercialisation", reponses.get('budget_commercialisation', 'Non renseigné')],
        ["Sources de financement", reponses.get('sources_financement', 'Non renseigné')],
        ["Retour sur investissement attendu", reponses.get('roi_attendu', 'Non renseigné')]
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

    # Section 6: Analyse des Risques et Opportunités
    story.append(Paragraph("6. Analyse des Risques et Opportunités", subtitle_style))
    story.append(Paragraph("Risques:", styles['Heading3']))
    story.append(Paragraph(reponses.get('risques', 'Non renseigné'), normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Opportunités:", styles['Heading3']))
    story.append(Paragraph(reponses.get('opportunites', 'Non renseigné'), normal_style))
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

# Section 1: Informations générales du projet
st.header("1️⃣ Informations générales du projet")
col1, col2 = st.columns(2)

with col1:
    st.session_state.reponses['titre_film'] = st.text_input("Titre du film")
    st.session_state.reponses['duree'] = st.text_input("Durée")
    st.session_state.reponses['budget_production'] = st.number_input(
        "Budget de production (€ HT)",
        min_value=0,
        step=1000
    )

with col2:
    st.session_state.reponses['budget_commercialisation'] = st.text_input(
        "Budget de commercialisation"
    )
    st.session_state.reponses['date_tournage'] = st.text_input(
        "Date de tournage"
    )
    st.session_state.reponses['lieu_tournage'] = st.text_input(
        "Lieu de tournage"
    )

# Section 2: Synopsis et Concept
st.header("2️⃣ Synopsis et Concept")
st.session_state.reponses['synopsis'] = st.text_area(
    "Synopsis",
    height=150
)
st.session_state.reponses['format_style'] = st.text_area(
    "Format et Style",
    height=100
)

# Section 3: Partenaires et Distribution
st.header("3️⃣ Partenaires et Distribution")
st.session_state.reponses['production'] = st.text_area(
    "Production",
    height=100
)
st.session_state.reponses['distribution'] = st.text_area(
    "Distribution",
    height=100
)
st.session_state.reponses['partenaires'] = st.text_area(
    "Partenaires",
    height=100
)

# Section 4: Stratégie de Diffusion
st.header("4️⃣ Stratégie de Diffusion")
st.session_state.reponses['sortie_salles'] = st.text_area(
    "Sortie en salles",
    height=100
)
st.session_state.reponses['diffusion_digitale'] = st.text_area(
    "Diffusion digitale",
    height=100
)
st.session_state.reponses['strategie_marketing'] = st.text_area(
    "Stratégie marketing",
    height=100
)

# Section 5: Budget et Financement
st.header("5️⃣ Budget et Financement")
col1, col2 = st.columns(2)

with col1:
    st.session_state.reponses['sources_financement'] = st.text_area(
        "Sources de financement",
        height=100
    )

with col2:
    st.session_state.reponses['roi_attendu'] = st.text_area(
        "Retour sur investissement attendu",
        height=100
    )

# Section 6: Analyse des Risques et Opportunités
st.header("6️⃣ Analyse des Risques et Opportunités")
st.session_state.reponses['risques'] = st.text_area(
    "Risques",
    height=100
)
st.session_state.reponses['opportunites'] = st.text_area(
    "Opportunités",
    height=100
)
st.session_state.reponses['strategies_mitigation'] = st.text_area(
    "Stratégies de mitigation",
    height=100
)

# Bouton pour générer le business plan
if st.button("Générer le Business Plan"):
    pdf_buffer = generer_pdf(st.session_state.reponses)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"business_plan_{timestamp}.pdf"
    
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