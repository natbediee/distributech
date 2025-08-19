#!/usr/bin/env python3
import mysql.connector
import os

from mysql.connector import Error
from dotenv import load_dotenv

#---------------
# CONFIGURATION
#---------------
load_dotenv("../.env")
DB_HOST = os.getenv("DB_HOST")
DB_ROOT = os.getenv("DB_ROOT")
DB_ROOT_PSWD = os.getenv("DB_ROOT_PSWD")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PSWD = os.getenv("DB_PSWD")

def main():
    try:
        # 1. Connexion en admin pour créer la base et l'utilisateur
        admin_cnx = mysql.connector.connect(
            host=DB_HOST,
            user=DB_ROOT,      
            password=DB_ROOT_PSWD
        )
        admin_cursor = admin_cnx.cursor()
        
        # Création de la base
        admin_cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        print(f"Base '{DB_NAME}' créée.")
        
        # Création de l'utilisateur et attribution des droits
        admin_cursor.execute(
            f"CREATE USER IF NOT EXISTS '{DB_USER}'@'%' "
            f"IDENTIFIED BY '{DB_PSWD}'"
        )
        admin_cursor.execute(
            f"GRANT ALL PRIVILEGES ON `{DB_NAME}`.* "
            f"TO '{DB_USER}'@'%'"
        )
        admin_cursor.execute("FLUSH PRIVILEGES")
        admin_cnx.commit()
        admin_cursor.close()
        admin_cnx.close()
        print(f"Utilisateur {DB_USER} créé.")

    except Error as err:
        print(f"[Erreur admin] {err}")
        return

    try:
        # 2. Connexion en tant que nouvel utilisateur sur la DB créée
        user_cnx = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PSWD,
            database=DB_NAME
        )
        user_cursor = user_cnx.cursor()

        # 3. Création des tables et insertion des données
        statements = [
            # Table régions
            """
            CREATE TABLE IF NOT EXISTS regions (
                id INT NOT NULL PRIMARY KEY,
                nom VARCHAR(50) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
            # Table revendeurs
            """
            CREATE TABLE IF NOT EXISTS revendeurs (
                id INT NOT NULL PRIMARY KEY,
                nom VARCHAR(50) NOT NULL,
                id_region INT NOT NULL,
                FOREIGN KEY (id_region) REFERENCES regions(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
            # Table produits
            """
            CREATE TABLE IF NOT EXISTS produits (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                id_src INT NOT NULL,
                nom VARCHAR(50) NOT NULL,
                cout_unitaire FLOAT NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
            # Table production
            """
            CREATE TABLE IF NOT EXISTS production (
                id INT NOT NULL PRIMARY KEY,
                id_pdt INT NOT NULL,
                quantite INT NOT NULL,
                date date NOT NULL,
                FOREIGN KEY (id_pdt) REFERENCES produits(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
             # Table commandes
            """
            CREATE TABLE IF NOT EXISTS commandes (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                num_cmd VARCHAR(30) NOT NULL,
                date date NOT NULL,
                id_revendeur INT NOT NULL,
                FOREIGN KEY (id_revendeur) REFERENCES revendeurs(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
            # Table lignes_cmd
            """
            CREATE TABLE IF NOT EXISTS lignes_cmd (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                id_cmd INT NOT NULL,
                id_pdt INT NOT NULL,
                quantite INT NOT NULL,
                prix_unitaire FLOAT NOT NULL,
                FOREIGN KEY (id_cmd) REFERENCES commandes(id),
                FOREIGN KEY (id_pdt) REFERENCES produits(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
        ]
        print("- Création des tables :")
        for stmt in statements:
            user_cursor.execute(stmt)
            print("→ OK :", stmt.strip().split()[5])  # affiche un mot-clé indicatif
        
        user_cnx.commit()
        user_cursor.close()
        user_cnx.close()
        print(f"Initialisation de la base terminée avec succès.\n")

    except Error as err:
        print(f"[Erreur user] {err}")


if __name__ == "__main__":
    main()