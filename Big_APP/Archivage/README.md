# Application de Traitement de Documents Word

Cette application Streamlit permet de traiter des documents Word et d'ajouter automatiquement des hyperliens vers le site SET.

## Installation

1. Assurez-vous d'avoir Python installé sur votre machine
2. Installez les dépendances requises :
```bash
pip install -r requirements.txt
```

## Utilisation

1. Lancez l'application avec la commande :
```bash
streamlit run app.py
```

2. Ouvrez votre navigateur à l'adresse indiquée (généralement http://localhost:8501)
3. Déposez votre document Word dans la zone de dépôt
4. Cliquez sur le bouton "Télécharger le document modifié" pour obtenir votre document avec les hyperliens

## Fonctionnalités

- Traitement automatique des documents Word
- Ajout d'hyperliens vers SET pour les occurrences du mot "set"
- Préservation du formatage original du document
- Interface utilisateur simple et intuitive 