
# 🎬 Assistant IA de Planification Cinéma - mk2

Un outil de planification intelligente pour organiser des séances de cinéma événementielles (test, tournée, avant-première, lancement…) sur l’ensemble du territoire français.

> 🧠 Propulsé par GPT-4 pour transformer une intention utilisateur en plan de sortie géolocalisé, précis, équilibré et réaliste.

---

## ✨ Fonctionnalités

- 🗺️ Génération automatique d’une **liste de villes** en France selon les zones évoquées
- 📊 Répartition des **spectateurs et séances** selon :
  - des objectifs globaux
  - des **fourchettes de spectateurs**
  - un nombre exact de séances (ex: 500 maximum)
- 🧩 Respect strict du format **JSON** pour intégration automatisée
- 📍 Calcul dynamique des cinémas proches (avec rayon personnalisable)
- ✅ Vérification automatique du nombre total de séances demandé

---

## 🏗️ Structure du projet

```
📁 plan_cinema_ai/
│
├── ai.py                  # Script principal
├── ai_fourchette.py       # Version avec fourchette min/max
├── data/                  # Fichiers de cinéma (JSON des salles, capacités, géolocalisation…)
├── output/                # Export HTML avec la carte des cinémas choisis
├── requirements.txt       # Dépendances
└── README.md              # Ce fichier
```

---

## 🧠 Comment ça marche ?

### ✍️ Exemple d'entrée :

```text
Je veux 500 séances dans toute la France pour entre 30 000 et 40 000 personnes
```

### 🤖 Ce que l’IA renvoie :

```json
[
  { "localisation": "Paris", "nombre": 3500, "nombre_seances": 50 },
  { "localisation": "Lille", "nombre": 2800, "nombre_seances": 40 },
  ...
]
```

Puis l’application trouve automatiquement les **cinémas réels** pour accueillir ces séances, dans un rayon défini autour de chaque ville.

---

## 📌 Principales règles IA intégrées

- **500 séances max**
- Chaque ville a une ou plusieurs **séances max** à distribuer
- Les zones vagues (ex : “sud de la France”) sont converties via un mapping précis
- Si une **fourchette de spectateurs** est donnée, le total reste **strictement** dans cette limite
- Le format de réponse est un **JSON pur** (guillemets doubles, pas de texte autour)

---

## ▶️ Lancer l'application

### 1. Installer les dépendances :

```bash
pip install -r requirements.txt
```

### 2. Exécuter le script principal :

```bash
streamlit run ai.py
```

### 3. Utiliser l'interface :

Décrivez simplement votre intention :  
➡️ *"100 séances à Paris et 400 ailleurs pour entre 30 000 et 45 000 spectateurs"*

---

## 📦 Export

Un fichier `.html` est généré avec :
- la **carte des cinémas**
- la liste détaillée des salles sélectionnées
- la capacité totale par zone

---

## 🛠️ Technologies

- 🧠 GPT-4 via OpenAI
- 🐍 Python 3.10+
- 📍 Geopy / Folium pour la cartographie
- 🎯 Streamlit pour l’interface utilisateur

---

## 🧪 Exemples de prompts utiles

- *“Je veux une tournée dans le sud avec 200 séances et au moins 20 000 spectateurs”*
- *“Lancement national : 500 séances pour 35 000 personnes dans toute la France”*
- *“Je veux 50 séances en région parisienne et 100 ailleurs, pour max 25 000 spectateurs”*

---

## 🧾 Licence

MIT — libre de réutilisation, adaptation et extension.

---

## 📬 Contact

Projet développé par **mk2 / Etienne Rouillon**  
→ [contact@mk2.com](mailto:contact@mk2.com)
