# ARGUS — Surveillance de topologie réseau

ARGUS est une application web qui découvre la topologie d'un réseau en interrogeant les équipements Cisco IOS en SSH, à partir de leurs voisins LLDP. Elle l'affiche sous forme de graphe, la surveille et signale en direct chaque changement.

> **Statut : prototype.** Destiné à un lab (testé sur GNS3), pas à la production.

L'interface est en anglais ; la documentation est en français.

## Fonctionnalités

- Gestion des équipements à surveiller depuis l'interface.
- **Graphe hiérarchique** (cœur, distribution, accès) avec les noms des interfaces et les détails au clic.
- **Temps réel** : l'écran se met à jour dès que le serveur détecte un changement.
- **Historique** : équipement en panne ou rétabli, lien perdu ou ajouté, équipement ajouté, retiré ou renommé.
- Deux onglets de graphe, **Full view** et **Online**, avec des exports **image PNG**, **Excel** et **JSON** correspondant à l'onglet ouvert.
- Découverte LLDP analysée avec `ntc-templates`, collecte en parallèle.

## Prérequis

- Python 3.10 ou plus récent.
- Node.js 20.19+ ou 22.12+, pour construire l'interface.
- Équipements Cisco IOS avec SSH et LLDP activés, répondant au ping.

## Installation

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -e .
Copy-Item .env.example .env   # puis renseigner les valeurs

cd frontend
npm install
npm run build
cd ..
```

Sous Linux : `source venv/bin/activate` et `cp .env.example .env`.

Après une mise à jour du projet, relancer `pip install -e .` et `npm run build`, puis redémarrer l'application.

## Utilisation

```powershell
argus serve
```

Ouvrir `http://127.0.0.1:8000` et se connecter avec `ARGUS_ADMIN_PASSWORD`.

| Écran | Contenu |
|---|---|
| **Topology** | Graphe, compteurs, scan à la demande, exports |
| **Devices** | Ajout et suppression des adresses IP, choix de la couche |
| **History** | Les 200 changements les plus récents |

Le réseau est interrogé à intervalle régulier (`ARGUS_MONITOR_INTERVAL`), à l'ajout ou à la suppression d'un équipement, et avec le bouton **Scan now**. « Temps réel » désigne l'affichage : une panne apparaît après le scan qui la détecte. Le premier scan sert de référence et ne produit aucune entrée d'historique.

La couche d'un équipement suit cet ordre de priorité : le choix fait dans la page **Devices**, puis le nom (`CORE`, `DIST` ou `DST`, `ACC`), puis le nombre de liaisons. Ce dernier critère ne désigne jamais un cœur.

La page **Topology** propose deux onglets :

| Onglet | Contenu |
|---|---|
| **Full view** | Tous les équipements (en ligne, en attente, en échec, non gérés) et toutes les liaisons connues |
| **Online** | Les équipements qui répondent et les liaisons dont les deux extrémités sont en ligne |

Les trois exports suivent l'onglet ouvert, et le nom du fichier se termine par `_full` ou `_online` :

- **Image PNG** : le graphe de l'onglet, avec la disposition à l'écran.
- **Excel** : une feuille « Devices » (nom, IP, couche, statut) et une feuille « Links » (une ligne par câble).
- **JSON** : `view`, `scanned_at`, `devices` (`name`, `ip`, `layer`, `status`, `model`) et `links` (`device_a`, `interface_a`, `device_b`, `interface_b`).

La documentation de l'API est disponible sur `/docs`. Les journaux sont écrits sur la sortie d'erreur ; en `DEBUG`, ARGUS journalise les réponses brutes des équipements : à ne pas partager sans relecture.

## Configuration

Toute la configuration se trouve dans `.env`. Une variable d'environnement déjà définie dans le terminal prime sur ce fichier.

| Variable | Description | Défaut |
|---|---|---|
| `ARGUS_ADMIN_PASSWORD` | Mot de passe administrateur de l'application | obligatoire |
| `ARGUS_USERNAME` | Utilisateur SSH | obligatoire |
| `ARGUS_PASSWORD` | Mot de passe SSH | obligatoire |
| `ARGUS_SECRET` | Mot de passe du mode *enable* | vide |
| `ARGUS_HOST` | Adresse d'écoute | `127.0.0.1` |
| `ARGUS_PORT` | Port d'écoute | `8000` |
| `ARGUS_DB_PATH` | Base SQLite | `data/argus.db` |
| `ARGUS_TIMEOUT` | Délai de connexion et de lecture (s) | `20` |
| `ARGUS_SESSION_TIMEOUT` | Délai de session Netmiko (s) | `20` |
| `ARGUS_MONITOR_INTERVAL` | Pause entre deux scans (s) | `60` |
| `ARGUS_MAX_WORKERS` | Équipements interrogés en parallèle | `10` |
| `ARGUS_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` ou `ERROR` | `INFO` |
| `ARGUS_ALLOW_LEGACY_SSH` | Autorise les algorithmes SSH obsolètes | `false` |

## Structure

```
argus/
├── cli.py          # commande argus serve
├── app.py          # initialisation et journalisation
├── config.py       # chargement et validation du .env
├── web.py          # API FastAPI, sessions, flux temps réel
├── scanner.py      # surveillance en tâche de fond
├── collector.py    # ping, SSH, analyse LLDP, parallélisme
├── changes.py      # détection des changements
├── db.py           # SQLite : équipements, dernier état, historique
├── graph.py        # nœuds, liens et couches
├── exporters.py    # exports JSON et Excel
└── ssh_compat.py   # algorithmes SSH obsolètes
frontend/           # interface React, TypeScript, Vite, Tailwind, Cytoscape.js
tests/              # tests unitaires, sans équipement réseau
```

## Développement

```powershell
pip install -e ".[dev]"
ruff check .
ruff format .
python -m unittest discover -s tests -v
```

Pour le frontend, lancer `argus serve`, puis `npm run dev` dans `frontend/` et ouvrir l'adresse affichée par Vite.

La CI GitHub Actions (`.github/workflows/ci.yml`) exécute le lint, le contrôle du format et les tests avec Python 3.10 et 3.13, et construit le frontend.

## Sécurité

Les protections sont dimensionnées pour un **lab**.

- Un seul administrateur, protégé par mot de passe. Les sessions durent 12 heures au plus et sont perdues au redémarrage.
- L'application écoute sur `127.0.0.1` et n'offre pas de HTTPS : ne pas l'exposer sur un réseau non maîtrisé.
- ARGUS présente les **mêmes identifiants SSH** à chaque adresse enregistrée et ne vérifie pas l'identité des équipements. Une personne ayant accès à l'interface peut ajouter l'adresse de sa propre machine et récupérer ces identifiants. À corriger avant tout usage sur un vrai réseau.
- Choisir un mot de passe administrateur différent du mot de passe SSH.
- L'authentification SSH par clé n'est pas prise en charge.
- `.env` contient des secrets en clair : il est ignoré par Git et doit le rester.
- `ARGUS_ALLOW_LEGACY_SSH=true` active `diffie-hellman-group1-sha1`, `ssh-rsa`, `aes128-cbc` et `hmac-sha1`. À réserver à un lab isolé.
- La base et les exports décrivent le réseau : à traiter comme des données sensibles.

## Limites connues

- Cisco IOS uniquement.
- Une sortie LLDP non reconnue par `ntc-templates` place l'équipement en échec.
- Si le détail LLDP n'indique pas le port local, il est lu dans `show lldp neighbors` ; une correspondance ambiguë (noms identiques sur leurs 20 premiers caractères et même port distant) place l'équipement en échec.
- Un voisin qui n'annonce pas de nom est identifié par son Chassis ID.
- Un équipement qui n'a jamais répondu n'a pas de nom connu : il apparaît par son adresse IP, et les liens annoncés par ses voisins restent rattachés à un nœud « Unmanaged ».
- La couche d'un voisin non géré ne peut pas être choisie.
- Les positions des nœuds déplacés à la main sont perdues au rechargement de la page.
- Le champ `model` contient le début de la ligne de version logicielle, pas le modèle matériel.
- L'historique n'est jamais purgé en base.

## Auteur

### Kanjak

**Network & Software Engineer** · IT Professional

`DevOps` `GCP` `AWS` `IaC` `Agentic AI Workflow`

*On the road to cybersecurity* 🔐

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logoColor=white)](https://www.linkedin.com/in/mardochee-mukoj/)
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/Kanjak-B)

## Licence

[MIT](LICENSE)
