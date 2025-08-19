import sqlite3
import os

sqlite_path = "../data/base_stock.sqlite"
conn = sqlite3.connect(sqlite_path)
cur = conn.cursor()

# Insertion des revendeurs
revendeurs = [
    (11, "DigitalShop", 3),
    (12, "ElectronikPro", 2),
    (13, "AtlantikTech", 4),
    (14, "ArmorDevices", 4),
    (15, "NordicStore", 1)
]
cur.executemany("INSERT INTO revendeur VALUES (?, ?, ?);", revendeurs)

# Insertion des produits
produits = [
    (111, "Routeur 4G", 49.00),
    (112, "Clé Zigbee", 17.50),
    (113, "Détecteur inondation", 14.80),
    (114, "Bande LED connectée", 21.90),
    (115, "Alarme intelligente", 60.00)
]
cur.executemany("INSERT INTO produit VALUES (?, ?, ?);", produits)

# Insertion de production (réapprovisionnement)
production = [
    (101, 50, "2025-07-15"),
    (108, 20, "2025-07-14"),
    (111, 40, "2025-07-25"),
    (112, 10, "2025-07-20"),
    (113, 40,"2025-07-25"),
    (114, 35, "2025-07-03"),
    (115, 25, "2025-07-04")
]
cur.executemany("INSERT INTO production (product_id, quantity, date_production) VALUES (?, ?, ?);", production)

conn.commit()
conn.close()

sqlite_path
print("Base utilisée :", os.path.abspath(sqlite_path))