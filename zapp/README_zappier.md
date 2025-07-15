# Zappier - Connecteur Google Drive vers WordPress

Un script Python qui surveille automatiquement un dossier Google Drive et crée des articles WordPress à partir des fichiers Word avec métadonnées structurées et hyperliens automatiques.

## Fonctionnalités

- 🔄 **Surveillance automatique** : Vérifie régulièrement les nouveaux fichiers dans Google Drive
- 📝 **Parsing intelligent** : Extrait automatiquement les métadonnées des fichiers Word
- 🔗 **Hyperliens automatiques** : Ajoute automatiquement des liens vers les articles existants
- 🏷️ **Gestion des catégories et tags** : Crée automatiquement les catégories et tags manquants
- 📊 **Métadonnées SEO Rank Math** : Support complet des métadonnées Rank Math (mot-clé principal, score SEO, robots, meta description, etc.)
- 🔐 **Authentification sécurisée** : OAuth2 pour Google Drive et JWT pour WordPress
- 📋 **Suivi des fichiers traités** : Évite le retraitement des fichiers déjà traités
- 💾 **Sauvegarde des documents traités** : Sauvegarde les versions avec hyperliens dans Google Drive

## Hyperliens automatiques

Le script utilise l'IA (GPT-4) pour analyser le contenu des documents Word et ajouter automatiquement des hyperliens vers les articles existants de votre site WordPress.

### Fonctionnement

1. **Analyse du contenu** : GPT-4 analyse chaque paragraphe du document
2. **Détection d'entités** : Identifie les noms propres, titres d'œuvres, réalisateurs, acteurs, etc.
3. **Correspondance** : Fait correspondre ces entités avec les articles existants
4. **Ajout d'hyperliens** : Crée des liens cliquables dans le document Word
5. **Sauvegarde** : Sauvegarde le document traité dans Google Drive

### Configuration des hyperliens

Dans `zappier_config.json`, vous pouvez configurer :

```json
{
  "content_processing": {
    "enable_hyperlinks": true,
    "save_processed_documents": true,
    "supported_formats": [
      "application/vnd.google-apps.document",
      "text/plain", 
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]
  }
}
```

- `enable_hyperlinks` : Active/désactive les hyperliens automatiques
- `save_processed_documents` : Sauvegarde les documents traités dans Google Drive
- `supported_formats` : Formats de fichiers supportés pour les hyperliens

### Base de données WordPress

Le script utilise le fichier `export_wordpress_propre.json` pour faire correspondre les entités avec vos articles existants. Assurez-vous que ce fichier est à jour avec vos articles WordPress.

## Format des fichiers Word

Le script attend que vos fichiers Word suivent ce format spécifique :

```
TITRE : Mission Impossible – The Final Reckoning : Tom and the band
CATEGORIE : Critiques
TAGS : Critiques, Festival de Cannes, Tom Cruise, Mission Impossible
AUTEUR : Damien Leblanc
SEO_KEYWORD : Mission Impossible
EXCERPT : Le dernier Mission Impossible mêle mélancolie, intelligence artificielle et esprit d'équipe, tout en faisant ses adieux à Ethan Hunt/Tom Cruise.

CONTENU :
CANNES 2025 . « Mission : Impossible. The Final Reckoning » : Tom and the band

Présenté comme l'ultime film de la saga, ce huitième volet des aventures d'Ethan Hunt/Tom Cruise fait flotter sur ses personnages une renversante mélancolie et défend une vision éloquente du combat collectif.

[... contenu de l'article ...]

Damien Leblanc
```

### Métadonnées supportées

- **TITRE** : Le titre de l'article WordPress
- **CATEGORIE** : La catégorie de l'article (sera créée automatiquement si elle n'existe pas)
- **TAGS** : Liste de tags séparés par des virgules
- **AUTEUR** : Nom de l'auteur de l'article
- **SEO_KEYWORD** : Mot-clé principal pour Rank Math (sera automatiquement configuré dans Rank Math)
- **EXCERPT** : Extrait/résumé de l'article
- **CONTENU** : Le contenu principal de l'article

## Installation

1. **Installer les dépendances** :
```bash
pip install -r requirements.txt
```

2. **Configurer Google Drive API** :
   - Créez un projet dans Google Cloud Console
   - Activez l'API Google Drive
   - Créez des identifiants OAuth2
   - Téléchargez le fichier `credentials.json`

3. **Configurer WordPress** :
   - Assurez-vous que l'API REST WordPress est activée
   - Installez le plugin JWT Authentication si nécessaire
   - Notez l'URL de votre site et vos identifiants

4. **Configurer le script** :
   - Modifiez `zappier_config.json` avec vos paramètres
   - Placez `credentials.json` dans le même dossier
   - Assurez-vous que `export_wordpress_propre.json` est présent pour les hyperliens

## Configuration

Modifiez `zappier_config.json` :

```json
{
  "google_drive": {
    "credentials_file": "credentials.json",
    "token_file": "token.json",
    "folder_name": "exemple",
    "scopes": ["https://www.googleapis.com/auth/drive.readonly"]
  },
  "wordpress": {
    "site_url": "https://votre-site.com",
    "username": "votre_username",
    "password": "votre_password",
    "api_endpoint": "/wp-json/wp/v2/posts"
  },
  "monitoring": {
    "check_interval": 300,
    "max_file_size": 10485760
  },
  "content_processing": {
    "enable_hyperlinks": true,
    "save_processed_documents": true,
    "supported_formats": [
      "application/vnd.google-apps.document",
      "text/plain",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]
  }
}
```

## Utilisation

1. **Première exécution** :
```bash
python zappier.py
```

2. **Le script va** :
   - Créer un fichier de configuration par défaut si nécessaire
   - Demander l'authentification Google Drive (première fois)
   - Se connecter à WordPress
   - Commencer la surveillance du dossier

3. **Surveillance continue** :
   - Le script vérifie les nouveaux fichiers toutes les 5 minutes
   - Les fichiers traités sont sauvegardés pour éviter les doublons
   - Les documents Word sont traités avec hyperliens automatiques
   - Les versions traitées sont sauvegardées dans Google Drive
   - Les logs sont écrits dans `zappier.log`

## Formats de fichiers supportés

- Documents Google (`application/vnd.google-apps.document`)
- Fichiers texte (`text/plain`)
- Documents Word (.doc, .docx) - **avec support des hyperliens automatiques**

## Gestion des catégories et tags

Le script peut automatiquement :
- Créer de nouvelles catégories si elles n'existent pas
- Créer de nouveaux tags si ils n'existent pas
- Utiliser les catégories existantes

## Métadonnées WordPress et Rank Math

Le script ajoute automatiquement :

### Métadonnées générales
- Métadonnées de source (fichier original, ID, etc.)
- Informations d'auteur
- Horodatage de modification

### Métadonnées Rank Math SEO
- **Mot-clé principal** (`rank_math_focus_keyword`)
- **Score SEO** (`rank_math_seo_score`) - configurable (défaut: 60/100)
- **Robots** (`rank_math_robots_advanced`) - configurable (défaut: index,follow)
- **URL canonique** (`rank_math_robots_canonical`)
- **Meta description** (`rank_math_description`) - générée automatiquement depuis l'extrait
- **Titre SEO** (`rank_math_title`) - utilise le titre de l'article
- **Type Schema.org** (`rank_math_schema_type`) - défini comme "Article"

### Configuration SEO

Dans `zappier_config.json`, vous pouvez configurer les options SEO :

```json
{
  "seo": {
    "enable_rank_math": true,
    "default_seo_score": 60,
    "default_robots": "index,follow",
    "auto_generate_meta_description": true
  }
}
```

- `enable_rank_math` : Active/désactive le support Rank Math
- `default_seo_score` : Score SEO par défaut (0-100)
- `default_robots` : Instructions pour les robots d'indexation
- `auto_generate_meta_description` : Génère automatiquement la meta description depuis l'extrait

## Logs et débogage

Les logs sont écrits dans :
- `zappier.log` : Fichier de log détaillé
- Console : Affichage en temps réel

Niveaux de log :
- INFO : Opérations normales
- WARNING : Problèmes mineurs
- ERROR : Erreurs critiques

## Sécurité

- Les tokens d'authentification sont sauvegardés localement
- Les mots de passe ne sont pas stockés en clair
- Connexions HTTPS pour WordPress
- Permissions minimales pour Google Drive (lecture seule)

## Test de l'intégration Rank Math

Pour vérifier que l'intégration Rank Math fonctionne correctement, vous pouvez utiliser le script de test :

```bash
python test_rank_math.py
```

Ce script va :
1. Créer un article de test
2. Ajouter toutes les métadonnées Rank Math
3. Vérifier que les métadonnées ont été correctement ajoutées
4. Supprimer l'article de test

### Résultat attendu

Si tout fonctionne correctement, vous devriez voir :
```
🧪 Test d'intégration Rank Math
========================================
✅ Article de test créé avec succès (ID: 123)
✅ rank_math_focus_keyword: test rank math
✅ rank_math_seo_score: 60
✅ rank_math_robots_advanced: index,follow
✅ rank_math_robots_canonical: https://www.troiscouleurs.fr/?p=123
✅ rank_math_description: Test d'intégration des métadonnées SEO Rank Math...
✅ rank_math_title: Test Rank Math Integration
✅ rank_math_schema_type: Article

📊 Résultat: 7/7 métadonnées ajoutées avec succès

🎉 Test réussi! L'intégration Rank Math fonctionne correctement.
```

## Dépannage

### Erreurs courantes

1. **Authentification Google Drive échouée** :
   - Vérifiez que `credentials.json` est présent
   - Supprimez `token.json` pour refaire l'authentification

2. **Connexion WordPress échouée** :
   - Vérifiez l'URL du site
   - Assurez-vous que l'API REST est activée
   - Vérifiez les identifiants

3. **Fichiers non traités** :
   - Vérifiez le format du fichier
   - Consultez les logs pour les erreurs de parsing

4. **Hyperliens non ajoutés** :
   - Vérifiez que `export_wordpress_propre.json` est présent
   - Assurez-vous que `enable_hyperlinks` est activé dans la configuration
   - Consultez les logs pour les erreurs GPT-4

### Fichiers de données

- `processed_files.json` : Liste des fichiers déjà traités
- `token.json` : Tokens d'authentification Google Drive
- `export_wordpress_propre.json` : Base de données des articles WordPress pour les hyperliens
- `zappier.log` : Logs détaillés

## Support

Pour toute question ou problème :
1. Consultez les logs dans `zappier.log`
2. Vérifiez la configuration dans `zappier_config.json`
3. Assurez-vous que les formats de fichiers respectent la structure attendue
4. Vérifiez que la base de données WordPress est à jour pour les hyperliens 