#!/usr/bin/env python3
"""
===== CODE DE TEST MEGASCOPE S3/CLOUDFRONT =====
Test d'upload (POST) et récupération (GET) d'images
"""

import boto3
import requests
import os
import mimetypes
from datetime import datetime
from botocore.exceptions import ClientError
import re

# ===== CONFIGURATION =====
AWS_CONFIG = {
    'aws_access_key_id': 'AKIAXDP3VD4B5FRZGLHX',
    'aws_secret_access_key': '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',
    'region_name': 'eu-west-1'
}

S3_BUCKET = 'megascope-media'
CLOUDFRONT_URL = 'https://d1cnrm9bmymjdm.cloudfront.net'  # URL CloudFront complète

# ===== INSTALLATION REQUISE =====
# pip install boto3 requests

# Initialisation du client S3
s3_client = boto3.client('s3', **AWS_CONFIG)

def upload_image(local_file_path, s3_key):
    """
    TEST 1: UPLOAD D'IMAGE (POST)
    Upload une image locale vers S3 et retourne l'URL CloudFront
    """
    try:
        print(f"🔄 Upload de {local_file_path} vers S3...")
        
        # Vérifier que le fichier existe
        if not os.path.exists(local_file_path):
            raise FileNotFoundError(f"Fichier non trouvé: {local_file_path}")
        
        # Détecter le type MIME
        content_type, _ = mimetypes.guess_type(local_file_path)
        if not content_type:
            content_type = 'application/octet-stream'
        
        # Préparer la clé S3 avec le préfixe media/
        s3_full_key = f"media/{s3_key}"
        
        # Upload vers S3
        extra_args = {
            'ContentType': content_type,
            'StorageClass': 'STANDARD_IA'  # Optimisation coût
        }
        
        s3_client.upload_file(
            local_file_path, 
            S3_BUCKET, 
            s3_full_key,
            ExtraArgs=extra_args
        )
        
        # URLs de résultat
        s3_url = f"https://{S3_BUCKET}.s3.eu-west-1.amazonaws.com/{s3_full_key}"
        cloudfront_url = f"{CLOUDFRONT_URL}/{s3_key}"
        
        print(f"✅ Upload réussi!")
        print(f"📍 S3 URL: {s3_url}")
        print(f"🌐 CloudFront URL: {cloudfront_url}")
        
        return {
            'success': True,
            's3_url': s3_url,
            'cloudfront_url': cloudfront_url,
            's3_key': s3_key
        }
        
    except Exception as e:
        print(f"❌ Erreur upload: {str(e)}")
        return {'success': False, 'error': str(e)}

def get_image_info(s3_key):
    """
    TEST 2: RÉCUPÉRATION D'IMAGE (GET)
    Vérifie qu'une image existe dans S3 et est accessible via CloudFront
    """
    try:
        print(f"🔄 Vérification de l'image {s3_key}...")
        
        # Vérifier si l'image existe dans S3
        s3_full_key = f"media/{s3_key}"
        
        response = s3_client.head_object(Bucket=S3_BUCKET, Key=s3_full_key)
        
        print(f"✅ Image trouvée dans S3:")
        print(f"📏 Taille: {response['ContentLength']} bytes")
        print(f"📅 Dernière modification: {response['LastModified']}")
        print(f"🏷️ Type: {response.get('ContentType', 'N/A')}")
        
        # Tester l'accès via CloudFront
        cloudfront_url = f"{CLOUDFRONT_URL}/{s3_key}"
        print(f"🔄 Test d'accès CloudFront...")
        
        cf_response = requests.head(cloudfront_url, timeout=10)
        
        if cf_response.status_code == 200:
            print(f"✅ CloudFront accessible!")
            print(f"🌐 URL publique: {cloudfront_url}")
            accessible = True
        else:
            print(f"⚠️ CloudFront non accessible (code: {cf_response.status_code})")
            accessible = False
        
        return {
            'success': True,
            's3_key': s3_key,
            'size': response['ContentLength'],
            'content_type': response.get('ContentType'),
            'last_modified': response['LastModified'],
            'cloudfront_url': cloudfront_url,
            'accessible': accessible
        }
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            print(f"❌ Image non trouvée: {s3_key}")
        else:
            print(f"❌ Erreur S3: {str(e)}")
        return {'success': False, 'error': str(e)}
    
    except requests.RequestException as e:
        print(f"❌ Erreur CloudFront: {str(e)}")
        return {'success': False, 'error': f"CloudFront error: {str(e)}"}
    
    except Exception as e:
        print(f"❌ Erreur récupération: {str(e)}")
        return {'success': False, 'error': str(e)}

def list_images(prefix='images/', max_keys=10):
    """
    TEST 3: LISTER LES IMAGES
    Liste les images dans un dossier S3
    """
    try:
        print(f"🔄 Liste des images dans {prefix}...")
        
        s3_prefix = f"media/{prefix}"
        
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET,
            Prefix=s3_prefix,
            MaxKeys=max_keys
        )
        
        if 'Contents' not in response:
            print(f"📋 Aucune image trouvée dans {prefix}")
            return {'success': True, 'images': []}
        
        images = []
        print(f"📋 {len(response['Contents'])} images trouvées:")
        
        for i, item in enumerate(response['Contents'], 1):
            # Enlever le préfixe media/ pour l'URL CloudFront
            clean_key = item['Key'].replace('media/', '')
            
            image_info = {
                'key': clean_key,
                'size': item['Size'],
                'last_modified': item['LastModified'],
                'cloudfront_url': f"{CLOUDFRONT_URL}/{clean_key}"
            }
            
            images.append(image_info)
            
            print(f"{i}. {clean_key} ({item['Size']} bytes)")
            print(f"   🌐 {image_info['cloudfront_url']}")
        
        return {'success': True, 'images': images}
        
    except Exception as e:
        print(f"❌ Erreur listing: {str(e)}")
        return {'success': False, 'error': str(e)}

def create_test_image(filename='test-image.jpg'):
    """
    Crée une image de test simple (pixel rouge 1x1)
    """
    try:
        from PIL import Image
        
        # Créer une image rouge 100x100
        img = Image.new('RGB', (100, 100), color='red')
        img.save(filename)
        print(f"📷 Image de test créée: {filename}")
        return True
        
    except ImportError:
        print("⚠️ PIL non installé. Créez manuellement un fichier test-image.jpg")
        return False

def run_tests():
    """
    Lance tous les tests automatiquement
    """
    print('🚀 === TESTS MEGASCOPE S3/CLOUDFRONT ===\n')
    
    # Créer une image de test si nécessaire
    test_file = 'test-image.jpg'
    if not os.path.exists(test_file):
        create_test_image(test_file)
    
    # Test 1: Upload d'une image
    print('📤 TEST 1: Upload d\'image')
    upload_result = upload_image(test_file, 'images/test-produit-123.jpg')
    print('Résultat:', upload_result)
    print('\n' + '-'*50 + '\n')
    
    if upload_result['success']:
        # Attendre un peu pour la propagation
        print('⏳ Attente 5 secondes pour propagation...')
        import time
        time.sleep(5)
        
        # Test 2: Récupération de l'image
        print('📥 TEST 2: Récupération d\'image')
        get_result = get_image_info('images/test-produit-123.jpg')
        print('Résultat:', get_result)
        print('\n' + '-'*50 + '\n')
    
    # Test 3: Liste des images
    print('📋 TEST 3: Liste des images')
    list_result = list_images('images/')
    print('\n' + '-'*50 + '\n')
    
    print('🎉 Tests terminés!')

# ===== EXEMPLES D'UTILISATION =====

def exemples():
    """Exemples d'utilisation pour les développeurs"""
    
    # 1. Upload simple
    result = upload_image('./mon-produit.jpg', 'images/produit-456.jpg')
    if result['success']:
        print(f"Image uploadée: {result['cloudfront_url']}")
    
    # 2. Vérifier une image
    info = get_image_info('images/produit-456.jpg')
    if info['success']:
        print(f"Image accessible: {info['accessible']}")
    
    # 3. Lister toutes les images
    images = list_images('images/')
    if images['success']:
        for img in images['images']:
            print(f"Image: {img['cloudfront_url']}")

def is_id_folder(name):
    """
    Vérifie si le nom du dossier correspond à un ID (ex: 1_8323)
    """
    return re.match(r'^\d+_\d+$', name) is not None

def upload_sorted_folders(base_path='Sorted'):
    """
    Parcourt le dossier 'Sorted' et upload sur S3 uniquement les dossiers ayant des sous-dossiers ID.
    """
    total_files = 0
    uploaded = 0
    for folder in os.listdir(base_path):
        folder_path = os.path.join(base_path, folder)
        if not os.path.isdir(folder_path):
            continue
        # Cherche des sous-dossiers ID
        subfolders = [f for f in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, f))]
        id_subfolders = [f for f in subfolders if is_id_folder(f)]
        if id_subfolders:
            print(f"\n📦 Dossier à uploader: {folder_path} (contient des IDs: {id_subfolders})")
            # Parcourt récursivement tout le dossier et upload chaque fichier
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    local_file = os.path.join(root, file)
                    rel_path = os.path.relpath(local_file, base_path)
                    # Remplace les séparateurs Windows par des / pour S3
                    s3_key = f"sorted/{rel_path.replace(os.sep, '/')}"
                    print(f"Tentative d'upload: {local_file} -> S3: {s3_key}")
                    total_files += 1
                    result = upload_image(local_file, s3_key)
                    if result.get('success'):
                        uploaded += 1
                    else:
                        print(f"Erreur upload: {result.get('error')}")
        else:
            print(f"⏭️ Dossier ignoré (pas de sous-dossier ID): {folder_path}")
    print(f"\nRésumé: {uploaded}/{total_files} fichiers uploadés avec succès.")

if __name__ == '__main__':
    # Configuration à vérifier avant utilisation
    print("⚠️ N'oubliez pas de remplacer:")
    print("- VOTRE_ACCESS_KEY_ID")
    print("- VOTRE_SECRET_ACCESS_KEY") 
    print("- VOTRE_URL_CLOUDFRONT")
    print()
    
    # Exemple d'appel pour uploader les bons dossiers
    upload_sorted_folders('Sorted') 