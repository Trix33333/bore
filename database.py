# 🤖 Bot Discord Communautaire

Bot Discord complet orienté gestion de serveur gaming, construit avec `discord.py 2.3+` et déployable sur **Railway**.

---

## 📁 Arborescence

```
discord-bot/
├── main.py                    # Point d'entrée — charge les Cogs, gère les signaux
├── database.py                # Couche SQLite (config, tickets, transcripts)
├── cogs/
│   ├── __init__.py
│   ├── cog_welcome.py         # Bienvenue / au revoir avec placeholders
│   ├── cog_announcements.py   # Système d'annonces avec ping de rôle
│   ├── cog_tickets.py         # Tickets : open/close/add/remove + transcript
│   ├── cog_utils.py           # ping, serverinfo, userinfo, clear, setup
│   └── cog_logs.py            # Logs : joins, leaves, delete, edit, ban
├── requirements.txt
├── Procfile                   # Pour Railway : worker: python main.py
├── .env.example               # Template des variables d'env
├── .gitignore
└── README.md
```

---

## ⚙️ Discord Developer Portal — Configuration

### 1. Créer l'application

1. Allez sur [discord.com/developers/applications](https://discord.com/developers/applications)
2. Cliquez **New Application** → donnez un nom
3. Onglet **Bot** → cliquez **Add Bot**

### 2. Activer les Intents (OBLIGATOIRE)

Dans l'onglet **Bot**, activez :
- ✅ **PRESENCE INTENT**
- ✅ **SERVER MEMBERS INTENT** ← requis pour on_member_join/remove
- ✅ **MESSAGE CONTENT INTENT** ← requis pour lire les messages (clear, logs)

### 3. Récupérer le Token

Onglet **Bot** → **Reset Token** → copiez-le (une seule fois visible).

### 4. Inviter le bot sur votre serveur

Onglet **OAuth2 > URL Generator** :
- Scopes : `bot`, `applications.commands`
- Bot Permissions : `Administrator` (ou permissions granulaires selon vos besoins)

Copiez l'URL générée et ouvrez-la dans votre navigateur.

> **Note** : Les slash commands sont globales par défaut (jusqu'à 1h de propagation).
> Pour un dev rapide, synchronisez sur un seul serveur dans `setup_hook` :
> ```python
> await self.tree.sync(guild=discord.Object(id=VOTRE_GUILD_ID))
> ```

---

## 🚀 Déploiement sur Railway — Guide pas-à-pas

### Étape 1 — Préparer le dépôt GitHub

```bash
git init
git add .
git commit -m "feat: initial bot setup"
git remote add origin https://github.com/VOTRE_USER/VOTRE_REPO.git
git push -u origin main
```

### Étape 2 — Créer le projet Railway

1. Allez sur [railway.app](https://railway.app) → **New Project**
2. Choisissez **Deploy from GitHub repo**
3. Sélectionnez votre dépôt

### Étape 3 — Variables d'environnement

Dans **Settings > Variables**, ajoutez :

| Variable | Valeur |
|---|---|
| `DISCORD_TOKEN` | Votre token Discord |
| `OWNER_ID` | Votre ID Discord |
| `DB_PATH` | `/data/bot.db` (si Volume activé) |

### Étape 4 — Volume persistant (IMPORTANT)

> ⚠️ Railway a un **système de fichiers éphémère** : sans Volume, la base de données SQLite est réinitialisée à chaque redéploiement.

Pour activer la persistance :
1. Dans votre service Railway → onglet **Volumes**
2. Cliquez **New Volume**
3. **Mount Path** : `/data`
4. Définissez `DB_PATH=/data/bot.db` dans vos variables

### Étape 5 — Vérifier le Procfile

Railway lit automatiquement votre `Procfile`. Vérifiez que le service est en mode **Worker** (pas Web) dans les paramètres Railway.

### Étape 6 — Premier déploiement

Poussez votre code → Railway démarre automatiquement. Consultez les logs en temps réel dans l'onglet **Deployments**.

---

## 🎮 Commandes disponibles

### 🎉 Bienvenue
| Commande | Description |
|---|---|
| `/welcome set-channel #salon` | Définit le salon de bienvenue |
| `/welcome set-join-message <msg>` | Personnalise le message d'arrivée |
| `/welcome set-leave-message <msg>` | Personnalise le message de départ |
| `/welcome test` | Prévisualise le message |

**Placeholders** : `{user}`, `{user_mention}`, `{username}`, `{server}`, `{member_count}`

### 📢 Annonces
| Commande | Description |
|---|---|
| `/announce <message>` | Envoie une annonce |
| `/announce-setup channel #salon` | Configure le salon d'annonces |

### 🎫 Tickets
| Commande | Description |
|---|---|
| `/ticket open [raison]` | Ouvre un ticket |
| `/ticket close` | Ferme le ticket (avec transcript) |
| `/ticket add @user` | Ajoute un membre au ticket |
| `/ticket remove @user` | Retire un membre |
| `/ticket-setup category` | Configure la catégorie |

### 🛠️ Utilitaires
| Commande | Description |
|---|---|
| `/ping` | Latence du bot |
| `/serverinfo` | Infos du serveur |
| `/userinfo [@user]` | Infos d'un membre |
| `/clear <n> [@user]` | Supprime des messages |
| `/avatar [@user]` | Affiche un avatar |

### ⚙️ Setup (Admin)
| Commande | Description |
|---|---|
| `/setup staff-role @role` | Définit le rôle staff |
| `/setup log-channel #salon` | Définit le salon de logs |
| `/setup view` | Affiche toute la configuration |

---

## 🔧 Développement local

```bash
# Cloner et installer
git clone https://github.com/VOTRE_USER/VOTRE_REPO.git
cd discord-bot

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# Configurer
cp .env.example .env
# Éditez .env avec votre token

# Lancer
python main.py
```

---

## 📝 Notes techniques

- **SQLite WAL mode** activé pour de meilleures performances concurrentes
- **Arrêt gracieux** sur SIGTERM/SIGINT (Railway l'envoie avant de tuer le conteneur)
- **Cogs chargés dynamiquement** : ajoutez un fichier `cog_*.py` dans `/cogs`, il est détecté automatiquement
- **Gestion d'erreurs globale** : toutes les erreurs de slash commands sont catchées dans `on_app_command_error`
- **Transcripts** stockés en BDD SQLite et envoyés en fichier `.txt` dans le salon de logs
