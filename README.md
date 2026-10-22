# Assistant d'admission IMSET

Assistant conversationnel qui accompagne les prospects de l'information jusqu'à la demande d'inscription :

1. **Questions sur la procédure d'admission (RAG)** : étapes de la procédure, pièces justificatives à fournir, conditions générales d'éligibilité, dates limites et frais (uniquement s'ils figurent dans le document). Les réponses s'appuient exclusivement sur le document officiel ; si l'information est introuvable ou incomplète, l'assistant le signale et oriente vers le service des admissions.
2. **Recherche de formations** : propositions issues de la base des formations selon le diplôme souhaité, la spécialité ou l'école, affichées dès que possible sous forme de cartes (diplôme, spécialité, école, critères d'éligibilité), puis affinées au fil de la conversation. L'assistant peut demander le niveau d'études, la nationalité ou la nature du baccalauréat pour vérifier les critères, mais ne confirme jamais une éligibilité sans les informations nécessaires.
3. **Inscription conversationnelle** : collecte et validation du nom, du prénom, de l'e-mail et du téléphone ; choix d'une formation existante, avec demande de précision si plusieurs correspondent ; récapitulatif et enregistrement **uniquement après confirmation explicite**, avec le statut « Nouvelle » et sans doublon (e-mail ou téléphone) ; puis notification par e-mail à l'équipe des admissions et confirmation au prospect. L'admission n'est jamais garantie : la décision finale appartient à l'équipe des admissions.

**Stack :** Django REST Framework · Angular · LangGraph · Gemini via API compatible OpenAI (secours : second modèle Gemini, puis Groq) · embeddings multilingual-e5 (exécutés en local) · PostgreSQL + pgvector · Docker

> 🚧 Projet en cours de développement : les sections marquées « *à venir* » seront complétées au fil des étapes.

---

## Sommaire

0. [Récupérer le projet](#0-récupérer-le-projet)
1. [Configuration](#1-configuration)
2. [Lancer l'infrastructure](#2-lancer-linfrastructure-base-de-données-et-e-mails)
3. [Backend Django](#3-backend-django)
4. [Frontend Angular](#4-frontend-angular)
5. [Tests](#5-tests)
6. [Structure du projet](#6-structure-du-projet)
7. [Dépannage](#7-dépannage)

---

## Prérequis

| Outil | Version testée | Installation |
|---|---|---|
| Python | 3.12 | https://www.python.org/downloads/ |
| Node.js | 24 (LTS) | https://nodejs.org/ |
| Angular CLI | 21 | `npm install -g @angular/cli` |
| Git | 2.55 | https://git-scm.com/ |
| Docker + Docker Compose | 29 / 2.40 | https://docs.docker.com/get-docker/ |

Environnement de développement : **Windows 11**, avec Docker installé dans **WSL2 (Ubuntu)**.

**Clés API** (offres gratuites, sans carte bancaire) :
- **Google Gemini** (modèle principal) : https://aistudio.google.com/ → « Get API key »
- **Groq** (modèle de secours) : https://console.groq.com/ → « API Keys »

---

## 0. Récupérer le projet

```bash
git clone https://github.com/nourrouissi/assistant-admission.git
cd assistant-admission
```

## 1. Configuration

Toute la configuration est centralisée dans un fichier `.env` à la racine, lu par Docker et par Django.

```bash
# Windows (cmd)
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Ouvrir `.env` et renseigner au minimum :

| Variable | Valeur |
|---|---|
| `DJANGO_SECRET_KEY` | Clé secrète Django (générée à l'étape 3 du backend) |
| `POSTGRES_PASSWORD` | Un mot de passe de votre choix (lettres et chiffres) |
| `LLM_PRIMARY_API_KEY` | Votre clé Google Gemini (modèle principal et premier secours) |
| `LLM_FALLBACK_API_KEY` | Votre clé Groq (second secours) |

Les noms des modèles (`LLM_PRIMARY_MODEL`, `LLM_SECONDARY_MODEL`, `LLM_FALLBACK_MODEL`, `EMBEDDINGS_MODEL`) sont déjà renseignés dans `.env.example`.

> ⚠️ Le fichier `.env` contient des secrets : il est ignoré par Git et ne doit jamais être partagé. Seul `.env.example`, sans valeurs secrètes, est versionné.

## 2. Lancer l'infrastructure (base de données et e-mails)

```bash
docker compose up -d
```

Sous Windows avec Docker dans WSL2 (sans Docker Desktop), depuis le dossier du projet :

```bash
wsl -d Ubuntu -- docker compose up -d
```

| Service | Rôle | Adresse |
|---|---|---|
| `db` | PostgreSQL 17 + extension pgvector | `localhost:5432` |
| `mailpit` | Serveur e-mail de test : capture tous les e-mails, aucun n'est réellement envoyé | http://localhost:8025 |

**Vérification :**

```bash
docker compose ps
```

Les deux services doivent afficher `Up … (healthy)`.

**Arrêter les services :**

```bash
docker compose down
```

Les données sont conservées dans le volume Docker `pgdata`.

## 3. Backend Django

Depuis le dossier `backend` :

**1. Créer et activer l'environnement virtuel (Python 3.12)**

```bash
py -3.12 -m venv .venv          # macOS / Linux : python3.12 -m venv .venv
.venv\Scripts\activate          # macOS / Linux : source .venv/bin/activate
```

**2. Installer les dépendances**

```bash
python -m pip install -r requirements.txt
```

**3. Générer la clé secrète Django**

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copier la valeur affichée dans `DJANGO_SECRET_KEY` du fichier `.env`.

**4. Créer les tables dans PostgreSQL** (l'infrastructure doit être lancée, voir étape 2)

```bash
python manage.py migrate
```

**5. Importer les formations** depuis `data/diplome_specialite.xlsx`

```bash
python manage.py import_formations
```

Résultat attendu : `89 formations importées`, suivi d'un rapport des anomalies détectées dans le fichier (lignes à faire vérifier par l'équipe des admissions ; elles sont importées sans modification). La commande peut être relancée sans risque : elle met à jour les formations existantes au lieu de les dupliquer.

**6. Indexer le document de procédure** `data/procedure_admission.docx` dans la base vectorielle

```bash
python manage.py index_procedure
```

Résultat attendu : `5 sections indexées` (les sections 1 à 5 du document ; la section 6 contient les consignes du chatbot, reprises dans ses instructions). Au premier lancement, le modèle d'embeddings `intfloat/multilingual-e5-small` est téléchargé (environ 450 Mo, une seule fois). La commande peut être relancée sans créer de doublons.

**7. Créer un compte d'administration** et lancer le serveur

```bash
python manage.py createsuperuser
python manage.py runserver
```

Le serveur occupe le terminal : utiliser un second terminal (environnement activé) pour les autres commandes. Arrêt : `Ctrl + C`.

Administration : http://127.0.0.1:8000/admin/

**Vérifier l'API** (serveur lancé) :

| URL | Résultat attendu |
|---|---|
| http://127.0.0.1:8000/api/health/ | `{"status": "ok"}` |
| http://127.0.0.1:8000/api/formations/?q=informatique | Formations dont un mot commence par « informatique » (28) |
| http://127.0.0.1:8000/api/formations/?school=Sousse | Formations d'une école (nom ou ville) |
| http://127.0.0.1:8000/api/formations/?q=reseaux&diploma_type=BTS | Recherche combinée par type de diplôme |

La liste est paginée par 20 : la réponse contient `count` (nombre total), `next` et `previous` (adresses des pages voisines, ou `null`), `results` (les cartes de la page), `unmatched_terms` (mots de `q` qui ne correspondent à aucune formation du catalogue, retirés de la recherche). `q` attend des mots-clés (le chatbot les extrait de la demande du prospect) : chaque mot doit commencer un mot des données, tous les mots doivent être présents, sans tenir compte des accents ni des majuscules ; aucune règle de langue (synonymes, mots vides) n'est écrite dans le code. Les cartes affichent la spécialité et les critères tels qu'écrits dans le fichier. Un `diploma_type` inconnu renvoie une erreur 400 avec la liste des valeurs possibles (`CAP`, `BTP`, `BTS`, `LICENCE`, `LICENCE_PRO`, `BACHELOR`, `INGENIEUR`, `TITRE_RNCP`, `SHORT_COURSE`) ; la casse est ignorée (`bts` = `BTS`).

### Vérifier l'éligibilité

`POST /api/formations/eligibility/` compare le profil déclaré d'un prospect aux critères des formations. C'est une action distincte de la recherche : la recherche ne renvoie jamais de statut d'éligibilité.

**Corps JSON** (tous les champs sont facultatifs) :

| Champ | Contenu |
|---|---|
| `profile.level` | Niveau d'études (un diplôme professionnel se déclare ici : `CAP` ou `BTP`) : `9EME`, `2EME_SEC`, `3EME_SEC`, `4EME_SEC`, `CAP`, `BTP`, `BAC`, `BAC_PLUS_2`, `LICENCE`, `LICENCE_PLUS_1`, `MASTER` |
| `profile.nationality` | Texte libre : `Tunisienne`, `Tunisie`, `TN`… sont reconnus comme tunisiens. Une valeur qui n'est pas une nationalité (`123`) renvoie une erreur 400 |
| `profile.bac_section` | Section du bac (ou du secondaire) : `MATH`, `SCIENCES_EXP`, `TECHNIQUE`, `INFORMATIQUE`, `ECONOMIE_GESTION`, `LETTRES`, `SPORT` |
| `formation_ids` | Identifiants des formations à évaluer (1 à 100) |
| `q`, `school`, `diploma_type` | Ou, à la place de `formation_ids`, les mêmes filtres que la recherche (100 formations évaluées au maximum) |

**Les 4 statuts** (aucun ne garantit l'admission : la décision finale revient à l'équipe des admissions) :

| Statut | Signification |
|---|---|
| `incomplet` | Il manque une information pour vérifier les critères (voir `missing`) |
| `non_compatible` | D'après les informations indiquées, au moins un critère n'est pas rempli (voir `reasons`, qui cite le texte officiel de l'école) |
| `a_confirmer` | Le code ne peut ni confirmer ni refuser, l'équipe tranche : voie CAP/BTP « dans le même secteur », diplôme professionnel (CAP, BTP) face à une année du secondaire, ou formation dont les données sont signalées comme à vérifier (`criteria_under_review`, aucun refus ferme n'est alors prononcé) |
| `compatible` | Les critères affichés sont remplis |

**Réponse :** `count`, `missing_information` (informations à demander au prospect, regroupées et sans doublon), `unknown_formation_ids` (identifiants demandés introuvables ou inactifs), pour une recherche par `q`/`school`/`diploma_type` seulement : `unmatched_terms` (comme pour la recherche), et `results` (les cartes, chacune avec un bloc `eligibility` : `status`, `missing`, `reasons`, `message`). Les cartes sont triées par statut : `compatible`, `a_confirmer`, `incomplet`, puis `non_compatible` ; à statut égal, l'ordre de la recherche est conservé.

Exemple :

```bash
curl -X POST http://127.0.0.1:8000/api/formations/eligibility/ \
  -H "Content-Type: application/json" \
  -d '{"profile": {"level": "BAC_PLUS_2"}, "q": "batiment"}'
```

Extrait de la réponse :

```json
{
  "count": 1,
  "missing_information": ["nationalité"],
  "unknown_formation_ids": [],
  "unmatched_terms": [],
  "results": [
    {
      "diploma": "Diplome de LICENCE",
      "specialty": "Licence en Batiment",
      "school": "IMSET SOUSSE",
      "criteria": {"level": "Bac+ 2/ BTS", "nationality": "Tunisienne", "bac": "All"},
      "criteria_under_review": false,
      "eligibility": {
        "status": "incomplet",
        "missing": ["nationalité"],
        "reasons": [],
        "message": "Pour vérifier les critères de cette formation, j'ai besoin de : nationalité."
      }
    }
  ]
}
```

### Discuter avec l'assistant

`POST /api/chat/` envoie un message à l'assistant. Corps JSON : `message` (obligatoire) et `session_id` (facultatif : sans lui, une nouvelle conversation est créée et son identifiant est renvoyé ; il faut le renvoyer à chaque message pour garder la conversation).

```bash
curl -X POST http://127.0.0.1:8000/api/chat/   -H "Content-Type: application/json"   -d '{"session_id": "demo-1", "message": "Quels documents dois-je fournir pour déposer une candidature ?"}'
```

Réponse : `{"session_id": "demo-1", "blocks": [...]}`, avec deux types de blocs :
- `{"type": "text", "text": "…"}` : texte affiché au prospect ;
- `{"type": "formations", "items": [...]}` : cartes des formations (diplôme, spécialité, école, critères d'éligibilité, et le bloc `eligibility` quand les critères ont été vérifiés), au même format que l'API des formations.

Les questions sur la procédure d'admission (étapes, pièces justificatives, dates limites, frais, conditions générales d'éligibilité) sont traitées à partir du document de procédure uniquement. Si l'information est absente ou incomplète, l'assistant le signale et oriente vers le service des admissions (`ADMISSIONS_CONTACT`). Si aucun modèle de langage ne répond, un message fixe oriente vers ce même contact.

Les recherches de formations et les vérifications d'éligibilité utilisent le même code que l'API des formations : l'assistant affiche les formations dès qu'une demande le permet, puis vérifie les critères quand le prospect indique son niveau d'études, sa nationalité ou la nature de son baccalauréat, en ne demandant que les informations utiles. Les textes et les cartes sont produits par le code et transmis tels quels : le modèle de langage choisit l'action, il ne rédige jamais lui-même un résultat ni un statut d'éligibilité.

## 4. Frontend Angular

*À venir.*

## 5. Tests

Depuis le dossier `backend`, avec l'infrastructure lancée :

```bash
python -m pytest
```

Les tests utilisent une base de données temporaire, créée puis supprimée automatiquement : les données réelles ne sont pas modifiées.

---

## 6. Structure du projet

```
assistant-admission/
├── docker-compose.yml        # Infrastructure : PostgreSQL + pgvector, Mailpit
├── .env.example              # Modèle de configuration (sans secrets)
├── backend/                  # API Django REST
│   ├── manage.py
│   ├── requirements.txt      # Dépendances Python
│   ├── pytest.ini            # Configuration des tests
│   ├── config/               # Réglages et adresses (URL) du projet
│   ├── catalog/              # Formations : normalisation, import, recherche, éligibilité, API
│   ├── knowledge/            # Procédure d'admission : indexation (pgvector) et réponses (RAG)
│   ├── chatbot/              # Assistant : modèles de langage, agent LangGraph, API /api/chat/
│   ├── data/                 # Fichier Excel des formations et document de procédure
│   └── tests/                # Tests automatisés
└── frontend/                 # Application Angular (à venir)
```

---

## 7. Dépannage

| Problème | Solution |
|---|---|
| Sous WSL2 sans Docker Desktop, les conteneurs redémarrent ou la base ne répond pas | Garder une fenêtre **Ubuntu** ouverte pendant le travail : WSL arrête Ubuntu, et donc Docker, quand aucune fenêtre n'est ouverte. |
| Erreur d'authentification PostgreSQL alors que le mot de passe est correct | Vérifier que `.env` utilise des fins de ligne **LF** (VS Code : barre d'état, en bas à droite). Avec CRLF, un caractère invisible s'ajoute aux valeurs. |
| Le mot de passe a été modifié dans `.env` après le premier lancement | PostgreSQL ne lit ce mot de passe qu'à la création de la base. Recréer la base (⚠️ efface les données) : `docker compose down -v` puis `docker compose up -d`. |
| `port is already allocated` sur 5432 | Un autre PostgreSQL utilise déjà ce port : l'arrêter, ou remplacer `"5432:5432"` par `"5433:5432"` dans `docker-compose.yml` et mettre `POSTGRES_PORT=5433` dans `.env`. |
| Windows bloque un exécutable de `.venv\Scripts` (« stratégie Device Guard » / App Control) | Lancer les outils via Python : `python -m django`, `python -m pip`, `python -m pytest`. Si une DLL est bloquée au premier lancement, relancer la commande. |
| Les commandes Django (`migrate`, `runserver`…) mettent longtemps à répondre | Sous Windows avec WSL2, utiliser `POSTGRES_HOST=127.0.0.1` au lieu de `localhost` dans `.env`. Au tout premier lancement, Windows peut aussi vérifier les bibliothèques installées : patienter quelques secondes. |