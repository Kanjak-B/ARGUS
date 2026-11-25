# Système de Documentation Automatisée de Réseau

## 📌 Description

Ce projet vise à automatiser la documentation d'un réseau informatique, notamment la couche d'accès et de distribution. Il permet de détecter la topologie réseau en temps réel à l’aide des protocoles LLDP et SSH, puis de générer des fichiers de documentation structurés (JSON, Excel, Graphviz, etc.).

Le système est conçu pour être modulaire, sécurisé, évolutif et facilement déployable dans un environnement réel ou simulé.

## 🧱 Architecture du Système

Le système est divisé en plusieurs modules (ou couches) :

1. **Agents** : Équipements réseau (switches, routeurs) configurés avec LLDP et SSH.
2. **Centre de Pilotage** : Serveur central (physique ou virtualisé) qui orchestre la collecte et le traitement des données.
3. **Connexion** : Interface SSH entre le centre et les agents.
4. **Interaction** : Commandes exécutées à distance via SSH.
5. **Extraction** : Données LLDP brutes récupérées depuis les équipements.
6. **T.A.S.** (Traitement, Analyse et Structuration) : Transformation des données brutes en structures exploitables.
7. **Génération** : Production automatique de fichiers de documentation.
8. **Sauvegarde** : Centralisation des fichiers dans un espace de stockage dédié.

## ⚙️ Fonctionnalités

- 🔍 Détection automatique de la topologie via LLDP.
- 📡 Connexion sécurisée aux équipements via SSH (authentification par clé).
- 📂 Export de la topologie sous plusieurs formats (JSON, CSV, Excel, Graphviz).
- 🔁 Surveillance continue de la topologie (script déclenché à intervalle régulier).
- ⚠️ Détection de changements de connectivité.
- 🧾 Journalisation des erreurs et logs détaillés.

## 🧰 Technologies utilisées

- **Python 3.x**
- **Modules** : `paramiko`, `netmiko`, `subprocess`, `os`, `json`, `xlsxwriter`, `graphviz`, `datetime`, etc.
- **SSH Key Auth** pour sécuriser l’accès aux équipements.
- **LLDP** comme protocole de découverte de voisin.

## 🏗️ Prérequis

- Switches/routeurs configurés avec LLDP et SSH.
- Python 3 installé sur le serveur.
- Clés SSH générées et copiées sur les équipements.
- Connexion réseau stable entre le centre et les agents.

## 🚀 Lancer le système

1. Cloner le dépôt :

Installer les dépendances :

Configurer les accès dans config.py :

Adresse IP des équipements

Nom d'utilisateur

Chemin de la clé SSH

Commandes personnalisées

Lancer la surveillance :

python monitor_topology.py

Pour les switches de lab qui n'acceptent que des algorithmes SSH obsolètes,
la compatibilité est activée par défaut. Pour la désactiver dans la session
PowerShell :

```powershell
$env:ALLOW_LEGACY_SSH = "false"
python monitor_topology.py
```

Cette option est réservée à un lab isolé. Pour revenir au comportement par
défaut dans la session, supprimez la variable avec
`Remove-Item Env:ALLOW_LEGACY_SSH`.

La génération automatique s’exécute en cas de détection de changement :

python ARGUS_network_topology_generator.py

📊 Résultats attendus
Fichiers .json représentant la topologie.

Tableaux Excel des connexions entre équipements.

Graphes visuels générés automatiquement.

🔒 Sécurité
Authentification par clé SSH uniquement.

Pas de mot de passe transmis en clair.

Journalisation des tentatives de connexion échouées.

📅 État du projet
✅ Fonctionnel et testé sur des réseaux simulés (GNS3)
🛠️ En cours de test en environnement de production

💡 Perspectives futures
Intégration SNMP pour équipements sans SSH

Interface web de visualisation de la topologie

Génération de rapports PDF

👨‍💻 Auteur
Kanjak
Étudiant en Sciences Informatiques, passionné de cybersécurité, réseaux, programmation et IA appliquée à la réalité augmentée.

📄 Licence
Ce projet est sous licence MIT.
