# Scripts de Test S3 Access Points AWS

Ce projet contient des scripts Python pour tester et diagnostiquer les points d'accès S3 AWS.

## 📁 Fichiers

- `test.py` - Script principal de test des points d'accès S3
- `diagnostic_iam.py` - Script de diagnostic des permissions IAM
- `README.md` - Ce fichier de documentation

## 🚀 Utilisation

### Prérequis

1. **Python 3.6+** installé
2. **AWS CLI** configuré avec vos credentials
3. **boto3** installé : `pip install boto3`

### Configuration AWS

Assurez-vous que vos credentials AWS sont configurés :

```bash
aws configure
```

Ou via les variables d'environnement :
```bash
export AWS_ACCESS_KEY_ID=votre_access_key
export AWS_SECRET_ACCESS_KEY=votre_secret_key
export AWS_DEFAULT_REGION=eu-west-1
```

### Test du Point d'Accès S3

1. **Modifiez l'ARN** dans `test.py` (ligne 250) :
```python
ACCESS_POINT_ARN = "arn:aws:s3:eu-west-1:VOTRE_COMPTE:accesspoint/VOTRE_POINT_ACCES"
```

2. **Lancez le test** :
```bash
python test.py
```

Le script effectuera les tests suivants :
- ✅ Vérification des credentials AWS
- 🔑 Test des permissions S3 Control
- 🔍 Vérification de l'existence du point d'accès
- 📋 Test GET (list objects)
- 📤 Test PUT (upload d'objet)
- 📥 Test GET (lecture d'objet)
- 🗑️ Nettoyage (suppression de l'objet de test)

### Diagnostic IAM

Si vous rencontrez des erreurs "Access Denied", utilisez le script de diagnostic :

```bash
python diagnostic_iam.py
```

Ce script vous aidera à :
- 👤 Identifier votre utilisateur AWS actuel
- 📋 Lister vos politiques IAM
- 👥 Vérifier les politiques de vos groupes
- 💡 Suggérer les permissions nécessaires

## 🔧 Résolution des Problèmes

### Erreur "Access Denied"

**Causes possibles :**
1. Credentials AWS non configurées ou invalides
2. Utilisateur dans le mauvais compte AWS
3. Permissions IAM insuffisantes
4. Point d'accès inexistant ou dans la mauvaise région

**Solutions :**
1. Vérifiez vos credentials : `aws sts get-caller-identity`
2. Contactez votre administrateur AWS
3. Vérifiez que vous êtes dans le bon compte (488643426355)
4. Vérifiez que le point d'accès existe dans eu-west-1

### Permissions IAM Requises

Votre utilisateur AWS doit avoir au minimum ces permissions :

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetAccessPoint",
        "s3:ListAccessPoints"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:eu-west-1:488643426355:accesspoint/accesspoint-megascope",
        "arn:aws:s3:eu-west-1:488643426355:accesspoint/accesspoint-megascope/*"
      ]
    }
  ]
}
```

## 📊 Interprétation des Résultats

### Tests Réussis ✅
- Tous les tests passent : Votre point d'accès fonctionne correctement
- Certains tests échouent : Vérifiez les permissions spécifiques

### Tests Échoués ❌
- **Credentials** : Reconfigurez vos credentials AWS
- **S3 Control** : Demandez les permissions s3:ListAccessPoints
- **Point d'accès** : Vérifiez l'ARN et l'existence du point d'accès
- **GET/PUT** : Vérifiez les permissions sur le bucket sous-jacent

## 🆘 Support

Si vous rencontrez des problèmes :

1. Lancez d'abord le diagnostic IAM : `python diagnostic_iam.py`
2. Vérifiez les logs détaillés du script de test
3. Contactez votre administrateur AWS avec les informations du diagnostic
4. Vérifiez la documentation AWS sur les S3 Access Points

## 📝 Notes

- Les scripts sont conçus pour la région `eu-west-1`
- Modifiez la région dans le code si nécessaire
- Les objets de test sont automatiquement supprimés après les tests
- Les scripts incluent des messages d'aide détaillés en français 