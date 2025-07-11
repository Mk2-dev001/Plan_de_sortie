#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script d'installation automatique pour le script Zapier-like
"""

import os
import sys
import subprocess
import json
import getpass

def check_python_version():
    """Vérifie la version de Python"""
    print("🐍 Vérification de la version Python...")
    
    if sys.version_info < (3, 7):
        print("❌ Python 3.7+ requis")
        print(f"   Version actuelle: {sys.version}")
        return False
    
    print(f"✅ Python {sys.version.split()[0]} détecté")
    return True

def install_dependencies():
    """Installe les dépendances Python"""
    print("\n📦 Installation des dépendances...")
    
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dépendances installées avec succès")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur lors de l'installation des dépendances: {e}")
        return False

def create_config_file():
    """Crée le fichier de configuration interactif"""
    print("\n⚙️  Configuration du script...")
    
    config = {
        "google_drive": {
            "credentials_file": "credentials.json",
            "token_file": "token.json",
            "folder_name": "exemple",
            "scopes": ["https://www.googleapis.com/auth/drive.readonly"]
        },
        "wordpress": {
            "site_url": "",
            "username": "",
            "password": "",
            "api_endpoint": "/wp-json/wp/v2/posts"
        },
        "monitoring": {
            "check_interval": 300,
            "max_file_size": 10485760
        }
    }
    
    print("Veuillez configurer vos paramètres WordPress:")
    
    # URL du site WordPress
    while True:
        site_url = input("URL de votre site WordPress (ex: https://monsite.com): ").strip()
        if site_url:
            if not site_url.startswith(('http://', 'https://')):
                site_url = 'https://' + site_url
            config["wordpress"]["site_url"] = site_url
            break
        print("⚠️  L'URL est obligatoire")
    
    # Nom d'utilisateur WordPress
    while True:
        username = input("Nom d'utilisateur WordPress: ").strip()
        if username:
            config["wordpress"]["username"] = username
            break
        print("⚠️  Le nom d'utilisateur est obligatoire")
    
    # Mot de passe WordPress
    while True:
        password = getpass.getpass("Mot de passe WordPress: ").strip()
        if password:
            config["wordpress"]["password"] = password
            break
        print("⚠️  Le mot de passe est obligatoire")
    
    # Nom du dossier Google Drive
    folder_name = input("Nom du dossier Google Drive à surveiller (défaut: exemple): ").strip()
    if folder_name:
        config["google_drive"]["folder_name"] = folder_name
    
    # Intervalle de vérification
    while True:
        try:
            interval = input("Intervalle de vérification en minutes (défaut: 5): ").strip()
            if not interval:
                break
            interval = int(interval) * 60
            config["monitoring"]["check_interval"] = interval
            break
        except ValueError:
            print("⚠️  Veuillez entrer un nombre valide")
    
    # Sauvegarde de la configuration
    try:
        with open("zappier_config.json", 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print("✅ Fichier de configuration créé")
        return True
    except Exception as e:
        print(f"❌ Erreur lors de la création du fichier de configuration: {e}")
        return False

def check_google_credentials():
    """Vérifie la présence des identifiants Google"""
    print("\n🔑 Vérification des identifiants Google Drive...")
    
    if os.path.exists("credentials.json"):
        print("✅ Fichier credentials.json trouvé")
        return True
    else:
        print("❌ Fichier credentials.json non trouvé")
        print("\n📋 Pour obtenir vos identifiants Google Drive:")
        print("1. Allez sur https://console.cloud.google.com/")
        print("2. Créez un nouveau projet ou sélectionnez un projet existant")
        print("3. Activez l'API Google Drive")
        print("4. Créez des identifiants OAuth 2.0 (Application de bureau)")
        print("5. Téléchargez le fichier JSON et renommez-le en 'credentials.json'")
        print("6. Placez-le dans ce dossier")
        print("\n⚠️  Vous devrez redémarrer l'installation après avoir ajouté le fichier")
        return False

def create_sample_files():
    """Crée des fichiers d'exemple pour les tests"""
    print("\n📝 Création de fichiers d'exemple...")
    
    # Fichier .gitignore
    gitignore_content = """# Fichiers de configuration sensibles
credentials.json
token.json
zappier_config.json
processed_files.json

# Logs
*.log

# Cache Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
"""
    
    try:
        with open(".gitignore", 'w', encoding='utf-8') as f:
            f.write(gitignore_content)
        print("✅ Fichier .gitignore créé")
    except Exception as e:
        print(f"⚠️  Erreur lors de la création du .gitignore: {e}")
    
    # Fichier de test
    test_content = """Ceci est un fichier de test pour le script Zapier-like.

Contenu de test pour vérifier que le script fonctionne correctement.

Date de création: {date}
""".format(date=__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    try:
        with open("test_file.txt", 'w', encoding='utf-8') as f:
            f.write(test_content)
        print("✅ Fichier de test créé")
    except Exception as e:
        print(f"⚠️  Erreur lors de la création du fichier de test: {e}")

def main():
    """Fonction principale d'installation"""
    print("=== Installation du script Zapier-like ===\n")
    
    # Vérifications préliminaires
    if not check_python_version():
        sys.exit(1)
    
    # Installation des dépendances
    if not install_dependencies():
        print("\n❌ Échec de l'installation des dépendances")
        sys.exit(1)
    
    # Création de la configuration
    if not create_config_file():
        print("\n❌ Échec de la création de la configuration")
        sys.exit(1)
    
    # Vérification des identifiants Google
    if not check_google_credentials():
        print("\n⚠️  Installation partielle terminée")
        print("   Ajoutez le fichier credentials.json et relancez l'installation")
        sys.exit(0)
    
    # Création des fichiers d'exemple
    create_sample_files()
    
    # Résumé final
    print("\n" + "="*50)
    print("🎉 INSTALLATION TERMINÉE AVEC SUCCÈS")
    print("="*50)
    print("\n📋 Prochaines étapes:")
    print("1. Vérifiez votre configuration dans zappier_config.json")
    print("2. Lancez le script de test: python test_zappier.py")
    print("3. Si tous les tests passent, lancez le script: python zappier.py")
    print("\n📚 Documentation: README_zappier.md")
    print("\n🔧 Pour modifier la configuration:")
    print("   - Éditez zappier_config.json")
    print("   - Ou relancez: python install_zappier.py")

if __name__ == "__main__":
    main() 