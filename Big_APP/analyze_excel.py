import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Lire le fichier Excel
file_path = 'NewApp/RevenuCalculator/resultats_cinemas_f94cb98d-7a12-4dde-948c-5956f32ece9f.xlsx'
df = pd.read_excel(file_path)

# Afficher les informations de base
print("\nInformations de base sur le fichier Excel:")
print("=" * 50)
print(f"Nombre de feuilles: {len(pd.ExcelFile(file_path).sheet_names)}")
print(f"Nom des feuilles: {pd.ExcelFile(file_path).sheet_names}")
print("\nAperçu des données:")
print("=" * 50)
print(df.head())

# Statistiques descriptives
print("\nStatistiques descriptives:")
print("=" * 50)
print(df.describe())

# Informations sur les colonnes
print("\nInformations sur les colonnes:")
print("=" * 50)
print(df.info()) 