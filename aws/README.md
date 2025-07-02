# 🚀 Script de Test Megascope S3/CloudFront

Ce script permet de tester les fonctionnalités d'upload et de récupération d'images via AWS S3 et CloudFront pour le projet Megascope.

## 📋 Prérequis

1. **Python 3.7+** installé
2. **Compte AWS** avec accès S3 et CloudFront
3. **Bucket S3** configuré (`megascope-media`)
4. **Distribution CloudFront** configurée

## 🔧 Installation

1. **Installer les dépendances :**
```bash
pip install -r requirements.txt
```

2. **Configurer les credentials AWS :**
   - Remplacer `VOTRE_ACCESS_KEY_ID` et `VOTRE_SECRET_ACCESS_KEY` dans le script
   - Ou utiliser les variables d'environnement AWS

3. **Configurer l'URL CloudFront :**
   - Remplacer `VOTRE_URL_CLOUDFRONT` par votre URL CloudFront

## 🧪 Tests Disponibles

### Test 1 : Upload d'Image (POST)
```python
upload_image('mon-image.jpg', 'images/produit-123.jpg')
```
- Upload une image locale vers S3
- Retourne les URLs S3 et CloudFront

### Test 2 : Récupération d'Image (GET)
```python
get_image_info('images/produit-123.jpg')
```
- Vérifie l'existence de l'image dans S3
- Teste l'accessibilité via CloudFront
- Retourne les métadonnées

### Test 3 : Liste des Images
```python
list_images('images/')
```
- Liste toutes les images dans un dossier S3
- Affiche les URLs CloudFront

## 🚀 Utilisation

### Lancement des tests automatiques :
```python
# Dans le script, décommenter :
run_tests()
```

### Utilisation manuelle :
```python
# Upload d'une image
result = upload_image('./mon-produit.jpg', 'images/produit-456.jpg')
if result['success']:
    print(f"Image uploadée: {result['cloudfront_url']}")

# Vérifier une image
info = get_image_info('images/produit-456.jpg')
if info['success']:
    print(f"Image accessible: {info['accessible']}")

# Lister les images
images = list_images('images/')
```

## 📁 Structure S3

Le script utilise la structure suivante :
```
megascope-media/
└── media/
    └── images/
        ├── produit-123.jpg
        ├── produit-456.jpg
        └── ...
```

## 🔍 Configuration AWS

### Variables d'environnement (recommandé) :
```bash
export AWS_ACCESS_KEY_ID="votre_access_key"
export AWS_SECRET_ACCESS_KEY="votre_secret_key"
export AWS_DEFAULT_REGION="eu-west-1"
```

### Ou dans le script :
```python
AWS_CONFIG = {
    'aws_access_key_id': 'VOTRE_ACCESS_KEY_ID',
    'aws_secret_access_key': 'VOTRE_SECRET_ACCESS_KEY',
    'region_name': 'eu-west-1'
}
```

## 🛠️ Fonctionnalités

- ✅ Upload automatique avec détection MIME
- ✅ Optimisation coût (StorageClass STANDARD_IA)
- ✅ Test d'accessibilité CloudFront
- ✅ Gestion d'erreurs complète
- ✅ Création d'image de test automatique
- ✅ Listing avec métadonnées

## 📝 Exemples de Sortie

```
🔄 Upload de test-image.jpg vers S3...
✅ Upload réussi!
📍 S3 URL: https://megascope-media.s3.eu-west-1.amazonaws.com/media/images/test-produit-123.jpg
🌐 CloudFront URL: https://votre-url.cloudfront.net/images/test-produit-123.jpg

🔄 Vérification de l'image images/test-produit-123.jpg...
✅ Image trouvée dans S3:
📏 Taille: 1024 bytes
📅 Dernière modification: 2024-01-15 10:30:00
🏷️ Type: image/jpeg
✅ CloudFront accessible!
```

## ⚠️ Notes Importantes

1. **Sécurité** : Ne jamais commiter les credentials AWS dans le code
2. **Permissions** : L'utilisateur AWS doit avoir les permissions S3 et CloudFront
3. **Région** : Vérifier que la région correspond à votre configuration
4. **Bucket** : Le bucket `megascope-media` doit exister et être accessible

## 🐛 Dépannage

### Erreur "Access Denied"
- Vérifier les permissions AWS
- Vérifier que le bucket existe

### Erreur "NoSuchBucket"
- Vérifier le nom du bucket
- Vérifier la région

### Erreur CloudFront
- Vérifier l'URL CloudFront
- Vérifier la configuration de la distribution 