# Distributech

## 📑 Sommaire
- [📖 Présentation](#-présentation)
- [📂 Sources de données](#-sources-de-données)
- [🛠️ Pipeline ETL](#️-pipeline-etl)
- [🗄️ Base relationnelle](#️-base-relationnelle)
- [📊 Résultats](#-résultats)
- [🚀 Installation](#-installation)
- [▶️ Utilisation](#️-utilisation)
- [📑 Documentation](#-documentation)
- [📌 Auteur](#-auteur)

## 📖 Présentation
Projet pédagogique consistant à mettre en place un processus **ETL en Python** pour centraliser les données de commandes et de stocks de l’entreprise fictive *Distributech*, grossiste en équipements électroniques.

## 📂 Sources de données
- **Fichiers CSV hebdomadaires** : commandes envoyées par les revendeurs.  
- **Base SQLite locale** : référentiels (produits, régions, revendeurs) et mouvements de production.  

## 🛠️ Pipeline ETL
- **Extract** : lecture des fichiers CSV et de la base SQLite.  
- **Transform** : nettoyage, normalisation, suppression des doublons, gestion des incohérences.  
- **Load** : intégration dans la base relationnelle MySQL.  

Un export CSV de l’état du stock est produit en fin de cycle.

## 🗄️ Base relationnelle
La base MySQL cible est organisée autour des tables :  
`regions`, `revendeurs`, `produits`, `commandes`, `lignes_cmd`, `production`.  

Trois vues principales facilitent l’analyse :  
- `v_stock` → état courant du stock  
- `v_cmds_par_region` → commandes par région  
- `v_chiffre_affaires_par_region` → chiffre d’affaires consolidé  

## 📊 Résultats
- Suivi des stocks globaux et par produit  
- Historique des commandes  
- Chiffre d’affaires par région  
- Export CSV et tableau de bord en ligne de commande  

## 🚀 Installation
Prérequis : **Python 3.12+**, **MySQL** installé et accessible.  
Configurer la base dans .env (non versionné) avec les accès MySQL.

▶️ Utilisation

Lancer le processus ETL :

python scripts/main_etl.py


Consulter les résultats :

Fichiers exportés dans data/stock/

Tableau de bord en ligne de commande (scripts/query_menu.py)

📑 Documentation

Cahier des charges

Dossier technique

Planning Gantt



📌 Auteur

Projet réalisé par Nathalie Bediee dans le cadre de la formation Développeur IA – ISEN Brest.

```bash
git clone https://github.com/natbediee/distributech.git
cd distributech
python3 -m venv .dtenv
source .dtenv/bin/activate
pip install -r requirements.txt
# Distributech
