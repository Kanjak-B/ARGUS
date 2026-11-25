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
| `ARGUS_DEVICES` | Adresses des équipements, séparées par des virgules | obligatoire |
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
├── config.py       # chargement et validation du .env
├── collector.py    # ping, SSH, analyse LLDP, parallélisme
├── exporters.py    # journal, JSON, Excel, graphe
└── ssh_compat.py   # algorithmes SSH obsolètes
tests/              # tests unitaires, sans équipement réseau
```

## Développement

```powershell
pip install -e ".[dev]"
ruff check .
ruff format .
python -m unittest discover -s tests -v
```

La CI GitHub Actions (`.github/workflows/ci.yml`) exécute le lint, le contrôle du format et les tests avec Python 3.10 et 3.13.

## Sécurité

- L'authentification se fait par **mot de passe**, avec les mêmes identifiants pour tous les équipements. L'authentification par clé SSH n'est pas prise en charge.
- `.env` contient des secrets en clair : il est ignoré par Git et doit le rester.
- `ARGUS_ALLOW_LEGACY_SSH=true` active `diffie-hellman-group1-sha1`, `ssh-rsa`, `aes128-cbc` et `hmac-sha1`. À réserver à un lab isolé.
- Les exports décrivent le réseau (adresses, liaisons) : à traiter comme des données sensibles.

## Limites connues

- Cisco IOS uniquement.
- Une sortie LLDP non reconnue par `ntc-templates` place l'équipement en échec.
- Un voisin qui n'annonce pas de nom est identifié par son Chassis ID.
- Le graphe ne dessine qu'une liaison par paire d'équipements.
- La distinction distribution/accès repose seulement sur le nombre de connexions.
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
