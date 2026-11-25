# ARGUS — Documentation automatisée de réseau

ARGUS découvre la topologie d'un réseau (couches accès et distribution) en interrogeant les équipements Cisco IOS en SSH, à partir de leurs voisins LLDP, puis génère la documentation correspondante. Il peut surveiller le réseau et la regénérer à chaque changement.

> **Statut : prototype.** Destiné à un lab (testé sur GNS3), pas à la production.

## Fonctionnalités

- Découverte des liaisons via LLDP, analysées avec `ntc-templates`.
- Collecte en parallèle sur plusieurs équipements.
- Export en JSON, Excel et graphe PNG (Graphviz).
- Surveillance périodique : nouvel équipement, équipement disparu, liaison modifiée, équipement en échec ou rétabli.

## Prérequis

- Python 3.10 ou plus récent.
- [Graphviz](https://graphviz.org/download/) installé, avec `dot` dans le `PATH` (nécessaire au PNG uniquement).
- Équipements Cisco IOS avec SSH et LLDP activés, répondant au ping.

## Installation

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -e .
Copy-Item .env.example .env
```

Sous Linux : `source venv/bin/activate` et `cp .env.example .env`.

## Configuration

Toute la configuration se trouve dans `.env`. Une variable d'environnement déjà définie dans le terminal prime sur ce fichier.

| Variable | Description | Défaut |
|---|---|---|
| `ARGUS_ADMIN_PASSWORD` | Mot de passe administrateur de l'application web | obligatoire pour `argus serve` |
| `ARGUS_HOST` | Adresse d'écoute de l'application web | `127.0.0.1` |
| `ARGUS_PORT` | Port de l'application web | `8000` |
| `ARGUS_DB_PATH` | Base SQLite de l'application web | `data/argus.db` |
| `ARGUS_DEVICES` | Adresses des équipements, séparées par des virgules (`generator` et `monitor` uniquement) | obligatoire pour ces commandes |
| `ARGUS_USERNAME` | Utilisateur SSH | obligatoire |
| `ARGUS_PASSWORD` | Mot de passe SSH | obligatoire |
| `ARGUS_SECRET` | Mot de passe du mode *enable* | vide |
| `ARGUS_TIMEOUT` | Délai de connexion et de lecture (s) | `20` |
| `ARGUS_SESSION_TIMEOUT` | Délai de session Netmiko (s) | `20` |
| `ARGUS_MONITOR_INTERVAL` | Pause entre deux vérifications (s) | `60` |
| `ARGUS_MAX_WORKERS` | Équipements interrogés en parallèle | `10` |
| `ARGUS_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` ou `ERROR` | `INFO` |
| `ARGUS_OUTPUT_DIR` | Dossier des exports | `topologies` |
| `ARGUS_ALLOW_LEGACY_SSH` | Autorise les algorithmes SSH obsolètes | `false` |

## Application web (en cours de développement)

Construire l'interface une première fois, puis après chaque mise à jour du frontend (Node.js 20.19+ ou 22.12+) :

```powershell
cd frontend
npm install
npm run build
cd ..
argus serve
```

Ouvrir `http://127.0.0.1:8000` et se connecter avec `ARGUS_ADMIN_PASSWORD`.

- **Équipements** : ajouter ou supprimer les adresses IP à surveiller. Elles sont enregistrées en base, indépendamment de `ARGUS_DEVICES`.
- **Topologie** : graphe hiérarchique (cœur, distribution, accès), détails au clic, scan à la demande, exports Excel et JSON. L'écran est rafraîchi toutes les 3 secondes.
- **Image PNG** : ne contient que les équipements qui répondent et les liaisons entre eux, avec leur disposition à l'écran. Les équipements en échec, en attente ou non gérés en sont exclus.

La couche d'un équipement suit cet ordre de priorité : le choix fait dans la page **Équipements**, puis le nom (`CORE`, `DIST` ou `DST`, `ACC`), puis le nombre de liaisons. Ce dernier critère ne désigne jamais un cœur. La couche d'un voisin non géré ne peut pas être choisie.

Un équipement qui n'a jamais répondu n'a pas de nom connu : il apparaît par son adresse IP, et les liens annoncés par ses voisins restent rattachés à un nœud « non géré ».

L'historique est disponible via l'API (`GET /api/changes`), pas encore dans l'interface. Documentation de l'API : `/docs`.

Pour développer le frontend, lancer `argus serve`, puis `npm run dev` dans `frontend/` et ouvrir l'adresse affichée par Vite.

## Utilisation

Depuis la racine du projet :

```powershell
python -m argus.generator   # documentation, une seule fois
python -m argus.monitor     # surveillance continue (Ctrl+C pour arrêter)
```

Les fichiers `topology_<horodatage>.{json,xlsx,png}` sont écrits dans le dossier des exports. Excel et PNG ne sont produits que si au moins une liaison est découverte.

Le moniteur prend pour référence le dernier export JSON et n'écrit de nouveaux fichiers que lorsqu'un changement est détecté.

Les journaux sont écrits sur la sortie d'erreur. En `DEBUG`, ARGUS journalise les réponses brutes des équipements : à ne pas partager sans relecture.

## Structure

```
argus/
├── generator.py    # commande : collecte puis export
├── monitor.py      # commande : surveillance et détection des changements
├── app.py          # initialisation commune et journalisation
├── cli.py          # commande argus serve
├── web.py          # API FastAPI, sessions, flux temps réel
├── scanner.py      # surveillance en tâche de fond de l'application web
├── db.py           # SQLite : équipements, dernier état, historique
├── graph.py        # nœuds et liens pour l'interface
├── changes.py      # détection des changements
├── config.py       # chargement et validation du .env
├── collector.py    # ping, SSH, analyse LLDP, parallélisme
├── exporters.py    # journal, JSON, Excel, graphe
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

La CI GitHub Actions (`.github/workflows/ci.yml`) exécute le lint, le contrôle du format et les tests avec Python 3.10 et 3.13, et construit le frontend.

## Sécurité

- L'authentification se fait par **mot de passe**, avec les mêmes identifiants pour tous les équipements. L'authentification par clé SSH n'est pas prise en charge.
- `.env` contient des secrets en clair : il est ignoré par Git et doit le rester.
- `ARGUS_ALLOW_LEGACY_SSH=true` active `diffie-hellman-group1-sha1`, `ssh-rsa`, `aes128-cbc` et `hmac-sha1`. À réserver à un lab isolé.
- Les exports décrivent le réseau (adresses, liaisons) : à traiter comme des données sensibles.

## Limites connues

- Cisco IOS uniquement.
- Une sortie LLDP non reconnue par `ntc-templates` place l'équipement en échec.
- Un voisin qui n'annonce pas de nom est identifié par son Chassis ID.
- Commandes `generator` et `monitor` : leur graphe ne dessine qu'une liaison par paire d'équipements et distingue distribution et accès par le seul nombre de connexions.
- Si le détail LLDP n'indique pas le port local, il est lu dans `show lldp neighbors` ; une correspondance ambiguë (noms identiques sur leurs 20 premiers caractères et même port distant) place l'équipement en échec.
- Le champ `model` contient le début de la ligne de version logicielle, pas le modèle matériel.

## Auteur

### Kanjak

**Network & Software Engineer** · IT Professional

`DevOps` `GCP` `AWS` `IaC` `Agentic AI Workflow`

*On the road to cybersecurity* 🔐

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logoColor=white)](https://www.linkedin.com/in/mardochee-mukoj/)
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/Kanjak-B)

## Licence

[MIT](LICENSE)
