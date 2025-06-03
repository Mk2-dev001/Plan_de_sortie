import streamlit as st
import pandas as pd
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import matplotlib.pyplot as plt
import io
import base64

def create_pdf_report(combined_df, total_capacity, budget_global, revenu_brut_ttc, 
                     revenu_brut_ht, revenu_exploitant, revenu_ayant_droit, 
                     revenu_distributeur, benefice_net, taux_remplissage):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []
    
    # Titre
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30
    )
    elements.append(Paragraph("Rapport de Calcul des Revenus", title_style))
    elements.append(Spacer(1, 20))
    
    # Paramètres de calcul
    elements.append(Paragraph("Paramètres de Calcul", styles['Heading2']))
    params_data = [
        ["Paramètre", "Valeur"],
        ["Budget Global", f"{budget_global:,.2f} €"],
        ["Prix du Ticket", f"{prix_ticket:,.2f} €"],
        ["Taux de Remplissage", f"{taux_remplissage*100:.1f}%"],
        ["Capacité Totale", f"{total_capacity:,.0f} places"]
    ]
    params_table = Table(params_data, colWidths=[3*inch, 2*inch])
    params_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(params_table)
    elements.append(Spacer(1, 20))
    
    # Résultats globaux
    elements.append(Paragraph("Résultats Globaux", styles['Heading2']))
    results_data = [
        ["Métrique", "Montant"],
        ["Revenu Brut TTC", f"{revenu_brut_ttc:,.2f} €"],
        ["Revenu Brut HT", f"{revenu_brut_ht:,.2f} €"],
        ["Bénéfice Net", f"{benefice_net:,.2f} €"],
        ["Revenu Exploitant (50%)", f"{revenu_exploitant:,.2f} €"],
        ["Revenu Ayant Droit (35%)", f"{revenu_ayant_droit:,.2f} €"],
        ["Revenu Distributeur (15%)", f"{revenu_distributeur:,.2f} €"]
    ]
    results_table = Table(results_data, colWidths=[3*inch, 2*inch])
    results_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(results_table)
    elements.append(Spacer(1, 20))
    
    # Graphique de répartition
    plt.figure(figsize=(8, 6))
    revenus = {
        'Exploitant (50%)': revenu_exploitant,
        'Ayant Droit (35%)': revenu_ayant_droit,
        'Distributeur (15%)': revenu_distributeur
    }
    plt.pie(revenus.values(), labels=revenus.keys(), autopct='%1.1f%%')
    plt.title('Répartition des Revenus HT')
    
    # Sauvegarder le graphique
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', bbox_inches='tight')
    img_buffer.seek(0)
    elements.append(Image(img_buffer, width=6*inch, height=4*inch))
    elements.append(Spacer(1, 20))
    
    # Détail par onglet
    elements.append(Paragraph("Détail par Onglet", styles['Heading2']))
    for sheet_name in combined_df['Onglet'].unique():
        sheet_df = combined_df[combined_df['Onglet'] == sheet_name]
        elements.append(Paragraph(f"Onglet: {sheet_name}", styles['Heading3']))
        
        # Créer le tableau pour cet onglet
        sheet_data = [['Capacité', 'Places Occupées', 'Revenu TTC', 'Revenu HT', 
                      'Revenu Exploitant', 'Revenu Ayant Droit', 'Revenu Distributeur']]
        
        for _, row in sheet_df.iterrows():
            sheet_data.append([
                f"{row['Capacité']:,.0f}",
                f"{row['Places_Occupées']:,.0f}",
                f"{row['Revenu_Brut_TTC']:,.2f} €",
                f"{row['Revenu_Brut_HT']:,.2f} €",
                f"{row['Revenu_Exploitant']:,.2f} €",
                f"{row['Revenu_Ayant_Droit']:,.2f} €",
                f"{row['Revenu_Distributeur']:,.2f} €"
            ])
        
        sheet_table = Table(sheet_data, colWidths=[1*inch]*7)
        sheet_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(sheet_table)
        elements.append(Spacer(1, 20))
    
    # Générer le PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

st.set_page_config(page_title="Calculateur de Revenus", layout="wide")

st.title("Calculateur de Revenus")

# Upload Excel file
uploaded_file = st.file_uploader("Choisissez votre fichier Excel contenant les capacités des salles", type=['xlsx', 'xls'])

if uploaded_file is not None:
    try:
        # Read all sheets from Excel file
        excel_file = pd.ExcelFile(uploaded_file)
        sheet_names = excel_file.sheet_names
        
        st.subheader("Onglets trouvés dans le fichier")
        st.write(sheet_names)
        
        # Create a dictionary to store all dataframes
        all_dfs = {}
        all_capacity_cols = set()
        
        # Read each sheet
        for sheet_name in sheet_names:
            df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
            all_dfs[sheet_name] = df
            
            # Detect capacity columns
            for col in df.columns:
                col_lower = str(col).lower()
                if any(keyword in col_lower for keyword in ['capacité', 'capacite', 'places', 'sieges', 'sièges', 'capacity']):
                    all_capacity_cols.add(col)
        
        # Sidebar for parameters
        st.sidebar.header("Paramètres de calcul")
        
        # Sheet selection
        selected_sheets = st.sidebar.multiselect(
            "Sélectionnez les onglets à analyser",
            sheet_names,
            default=sheet_names
        )
        
        # Column selection
        capacity_col = st.sidebar.selectbox(
            "Sélectionnez la colonne des capacités",
            sorted(list(all_capacity_cols)) if all_capacity_cols else ["Aucune colonne détectée"]
        )
        
        # Parameters
        budget_global = st.sidebar.number_input(
            "Budget Global (€)",
            min_value=0.0,
            value=0.0,
            step=1000.0
        )
        
        prix_ticket = st.sidebar.number_input(
            "Prix du Ticket (€)",
            min_value=0.0,
            value=0.0,
            step=1.0
        )
        
        taux_remplissage = st.sidebar.number_input(
            "Taux de Remplissage (%)",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=1.0
        )
        
        # Calculate results
        if st.sidebar.button("Calculer"):
            # Convert percentages to decimals
            taux_remplissage = taux_remplissage / 100
            
            # Process each selected sheet
            all_results = []
            total_capacity = 0
            total_revenue = 0
            
            for sheet_name in selected_sheets:
                df = all_dfs[sheet_name].copy()
                
                # Clean and convert capacity column
                df[capacity_col] = pd.to_numeric(df[capacity_col], errors='coerce')
                df = df.dropna(subset=[capacity_col])
                
                if len(df) == 0:
                    st.warning(f"Aucune capacité valide trouvée dans l'onglet {sheet_name}")
                    continue
                
                # Add sheet name column
                df['Onglet'] = sheet_name
                
                # Calculate results for each room
                df['Capacité'] = df[capacity_col]
                df['Places_Occupées'] = df['Capacité'] * taux_remplissage
                df['Revenu_Brut_TTC'] = df['Places_Occupées'] * prix_ticket
                df['Revenu_Brut_HT'] = df['Revenu_Brut_TTC'] / 1.20  # Conversion TTC vers HT
                
                # Distribution des revenus HT
                df['Revenu_Exploitant'] = df['Revenu_Brut_HT'] * 0.5  # 50% pour l'exploitant
                df['Revenu_Reste'] = df['Revenu_Brut_HT'] * 0.5  # 50% restant
                df['Revenu_Ayant_Droit'] = df['Revenu_Reste'] * 0.7  # 70% pour l'ayant droit
                df['Revenu_Distributeur'] = df['Revenu_Reste'] * 0.3  # 30% pour le distributeur
                
                total_capacity += df['Capacité'].sum()
                total_revenue += df['Revenu_Brut_TTC'].sum()
                all_results.append(df)
            
            if not all_results:
                st.error("Aucune donnée valide trouvée dans les onglets sélectionnés")
                st.stop()
            
            # Combine all results
            combined_df = pd.concat(all_results, ignore_index=True)
            
            # Calculs globaux
            revenu_brut_ttc = combined_df['Revenu_Brut_TTC'].sum()
            revenu_brut_ht = combined_df['Revenu_Brut_HT'].sum()
            revenu_exploitant = combined_df['Revenu_Exploitant'].sum()
            revenu_ayant_droit = combined_df['Revenu_Ayant_Droit'].sum()
            revenu_distributeur = combined_df['Revenu_Distributeur'].sum()
            benefice_net = revenu_brut_ttc - budget_global
            
            # Display results
            st.header("Résultats Globaux")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Capacité Totale", f"{total_capacity:,.0f} places")
                st.metric("Budget Global", f"{budget_global:,.2f} €")
                st.metric("Revenu Brut TTC", f"{revenu_brut_ttc:,.2f} €")
                st.metric("Revenu Brut HT", f"{revenu_brut_ht:,.2f} €")
                st.metric("Bénéfice Net", f"{benefice_net:,.2f} €")
            
            with col2:
                st.metric("Revenu Exploitant", f"{revenu_exploitant:,.2f} €")
                st.metric("Revenu Ayant Droit", f"{revenu_ayant_droit:,.2f} €")
                st.metric("Revenu Distributeur", f"{revenu_distributeur:,.2f} €")
            
            # Display results by sheet
            st.subheader("Détail par onglet")
            for sheet_name in selected_sheets:
                sheet_df = combined_df[combined_df['Onglet'] == sheet_name]
                if len(sheet_df) > 0:
                    st.write(f"### {sheet_name}")
                    st.write(f"Capacité: {sheet_df['Capacité'].sum():,.0f} places")
                    st.dataframe(sheet_df[['Capacité', 'Places_Occupées', 'Revenu_Brut_TTC', 
                                        'Revenu_Brut_HT', 'Revenu_Exploitant', 
                                        'Revenu_Ayant_Droit', 'Revenu_Distributeur']].round(2))
            
            # Création d'un graphique
            st.subheader("Répartition des Revenus HT")
            revenus = {
                'Exploitant (50%)': revenu_exploitant,
                'Ayant Droit (35%)': revenu_ayant_droit,
                'Distributeur (15%)': revenu_distributeur
            }
            
            # Création du graphique en camembert
            fig = pd.DataFrame({
                'Partie': list(revenus.keys()),
                'Montant': list(revenus.values())
            }).plot.pie(y='Montant', labels=list(revenus.keys()), autopct='%1.1f%%')
            
            st.pyplot(fig.figure)
            
            # Après l'affichage des résultats, ajouter le bouton de téléchargement PDF
            pdf_buffer = create_pdf_report(
                combined_df, total_capacity, budget_global, revenu_brut_ttc,
                revenu_brut_ht, revenu_exploitant, revenu_ayant_droit,
                revenu_distributeur, benefice_net, taux_remplissage
            )
            
            st.download_button(
                label="Télécharger le rapport PDF",
                data=pdf_buffer,
                file_name="rapport_calculs.pdf",
                mime="application/pdf"
            )
            
            # Download button for results
            csv = combined_df.to_csv(index=False)
            st.download_button(
                label="Télécharger les résultats en CSV",
                data=csv,
                file_name="resultats_calculs.csv",
                mime="text/csv"
            )
            
    except Exception as e:
        st.error(f"Une erreur est survenue lors de l'analyse du fichier: {str(e)}")
        st.error("Veuillez vérifier que le fichier Excel contient des colonnes de capacité valides.")
else:
    st.info("Veuillez télécharger un fichier Excel contenant les capacités des salles pour commencer l'analyse.")
