#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de test pour vérifier la configuration du script Zapier-like
"""

import os
import json
import sys
from zapp.zappier import GoogleDriveToWordPress

def test_configuration():
    """Teste la configuration du script"""
    print("🔧 Test de la configuration...")
    
    # Vérifie si le fichier de configuration existe
    if not os.path.exists("zappier_config.json"):
        print("❌ Fichier de configuration non trouvé")
        print("   Lancez d'abord le script principal pour créer la configuration")
        return False
    
    try:
        with open("zappier_config.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        print("✅ Fichier de configuration trouvé")
        
        # Vérifie la structure de la configuration
        required_sections = ["google_drive", "wordpress", "monitoring"]
        for section in required_sections:
            if section not in config:
                print(f"❌ Section '{section}' manquante dans la configuration")
                return False
        
        print("✅ Structure de configuration valide")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la lecture de la configuration: {e}")
        return False

def test_google_drive_credentials():
    """Teste les identifiants Google Drive"""
    print("\n🔑 Test des identifiants Google Drive...")
    
    if not os.path.exists("credentials.json"):
        print("❌ Fichier credentials.json non trouvé")
        print("   Téléchargez vos identifiants depuis Google Cloud Console")
        return False
    
    try:
        connector = GoogleDriveToWordPress()
        connector.authenticate_google_drive()
        print("✅ Authentification Google Drive réussie")
        return True
        
    except Exception as e:
        print(f"❌ Erreur d'authentification Google Drive: {e}")
        return False

def test_wordpress_connection():
    """Teste la connexion WordPress"""
    print("\n🌐 Test de la connexion WordPress...")
    
    try:
        connector = GoogleDriveToWordPress()
        
        # Test de connexion basique
        site_url = connector.config["wordpress"]["site_url"]
        if site_url == "https://votre-site.com":
            print("❌ URL WordPress non configurée")
            print("   Modifiez zappier_config.json avec votre URL WordPress")
            return False
        
        # Test de l'API REST
        api_url = f"{site_url}/wp-json/wp/v2/posts"
        response = connector.wordpress_session.get(api_url)
        
        if response.status_code == 200:
            print("✅ API REST WordPress accessible")
        else:
            print(f"⚠️  API REST WordPress retourne le code {response.status_code}")
        
        # Test d'authentification
        try:
            connector.authenticate_wordpress()
            print("✅ Authentification WordPress réussie")
            return True
        except Exception as e:
            print(f"❌ Erreur d'authentification WordPress: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur de connexion WordPress: {e}")
        return False

def test_folder_access():
    """Teste l'accès au dossier Google Drive"""
    print("\n📁 Test d'accès au dossier Google Drive...")
    
    try:
        connector = GoogleDriveToWordPress()
        connector.authenticate_google_drive()
        
        folder_name = connector.config["google_drive"]["folder_name"]
        folder_id = connector.find_folder_id(folder_name)
        
        if folder_id:
            print(f"✅ Dossier '{folder_name}' trouvé (ID: {folder_id})")
            
            # Test de récupération des fichiers
            files = connector.get_files_from_folder(folder_id)
            print(f"✅ {len(files)} fichiers trouvés dans le dossier")
            return True
        else:
            print(f"❌ Dossier '{folder_name}' non trouvé")
            print("   Vérifiez que le dossier existe dans votre Google Drive")
            return False
            
    except Exception as e:
        print(f"❌ Erreur d'accès au dossier: {e}")
        return False

def main():
    """Fonction principale de test"""
    print("=== Test de configuration du script Zapier-like ===\n")
    
    tests = [
        ("Configuration", test_configuration),
        ("Identifiants Google Drive", test_google_drive_credentials),
        ("Connexion WordPress", test_wordpress_connection),
        ("Accès au dossier Google Drive", test_folder_access)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Erreur lors du test '{test_name}': {e}")
            results.append((test_name, False))
    
    # Résumé des tests
    print("\n" + "="*50)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSÉ" if result else "❌ ÉCHOUÉ"
        print(f"{test_name:<30} {status}")
        if result:
            passed += 1
    
    print(f"\nRésultat: {passed}/{total} tests réussis")
    
    if passed == total:
        print("\n🎉 Tous les tests sont passés ! Le script est prêt à être utilisé.")
        print("   Lancez 'python zappier.py' pour démarrer la surveillance.")
    else:
        print("\n⚠️  Certains tests ont échoué. Veuillez corriger les problèmes avant d'utiliser le script.")
        print("   Consultez la documentation dans README_zappier.md pour plus d'informations.")

if __name__ == "__main__":
    main() 