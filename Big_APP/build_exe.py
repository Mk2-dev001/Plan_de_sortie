import PyInstaller.__main__
import os

# Liste des dossiers à inclure
folders = [
    'Ai_Map',
    'BuissnessPlan',
    'CreateurContenue',
    'Redaction_AI',
    'Archivage'
]

# Créer la liste des datas à inclure
datas = []
for folder in folders:
    if os.path.exists(folder):
        datas.extend([f'--add-data={folder};{folder}'])

# Configuration de PyInstaller
PyInstaller.__main__.run([
    'app.py',  # Script principal
    '--name=Multi_Apps_Launcher',  # Nom de l'exécutable
    '--onefile',  # Créer un seul fichier exécutable
    '--windowed',  # Ne pas afficher la console
    '--icon=NONE',  # Vous pouvez ajouter une icône plus tard
    '--clean',  # Nettoyer le cache
    *datas,  # Ajouter les dossiers
    '--hidden-import=streamlit',
    '--hidden-import=streamlit.runtime',
    '--hidden-import=streamlit.runtime.scriptrunner',
    '--hidden-import=streamlit.runtime.scriptrunner.magic_funcs',
]) 