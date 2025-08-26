import os
import pandas as pd
import mysql.connector

from datetime import datetime
from commun import log_etl
from commun import MYSQL_CONF
from commun import DATA_STOCK
from commun import DATA_LOG
from query_menu import query_menu

# -- VUES SQL --

SQL_V_STOCK = """
CREATE OR REPLACE VIEW v_stock AS
SELECT 
    p.id_src AS id_produit,
    p.nom    AS produit,
    COALESCE(prod.total_prod, 0) AS total_prod,
    COALESCE(cmd.total_cmds, 0)  AS total_cmds,
    COALESCE(prod.total_prod, 0) - COALESCE(cmd.total_cmds, 0) AS stock
FROM produits AS p
LEFT JOIN (
    SELECT id_pdt, SUM(quantite) AS total_prod
    FROM production
    GROUP BY id_pdt
) AS prod ON prod.id_pdt = p.id
LEFT JOIN (
    SELECT id_pdt, SUM(quantite) AS total_cmds
    FROM lignes_cmd
    GROUP BY id_pdt
) AS cmd ON cmd.id_pdt = p.id
ORDER BY p.id_src;
"""

SQL_V_ORDERS_BY_REGION = """
CREATE OR REPLACE VIEW v_cmds_par_region AS
SELECT 
    r.nom    AS region,
    p.id_src AS id_produit,
    p.nom    AS produit,
    SUM(lc.quantite) AS total_commande
FROM lignes_cmd lc
JOIN commandes  c ON lc.id_cmd      = c.id
JOIN revendeurs v ON c.id_revendeur = v.id
JOIN regions    r ON v.id_region    = r.id
JOIN produits   p ON lc.id_pdt      = p.id
GROUP BY r.nom, p.id_src, p.nom
ORDER BY r.nom, p.id_src;
"""

SQL_V_SALES_BY_REGION = """
CREATE OR REPLACE VIEW v_chiffre_affaires_par_region AS
SELECT
    r.id  AS id_region,
    r.nom AS region,
    ROUND(SUM(lc.quantite * lc.prix_unitaire), 2) AS chiffre_affaires,
    COUNT(DISTINCT c.num_cmd) AS nb_commandes
FROM lignes_cmd AS lc
JOIN commandes  AS c  ON lc.id_cmd = c.id
JOIN revendeurs AS re ON c.id_revendeur = re.id
JOIN regions    AS r  ON re.id_region = r.id
GROUP BY r.id, r.nom
ORDER BY r.nom;
"""

#---------------
# FONCTIONS
#---------------

def refresh_views():
    """Créé ou recréé v_stock, v_cmds_par_region, v_chiffre_affaires_par_region."""
    conn = mysql.connector.connect(**MYSQL_CONF)
    try:
        cur = conn.cursor()
        cur.execute(SQL_V_STOCK)
        cur.execute(SQL_V_ORDERS_BY_REGION)
        cur.execute(SQL_V_SALES_BY_REGION)
        conn.commit()
        print("[INFO] Vues (re)créées : v_stock, v_cmds_par_region, v_chiffre_affaires_par_region.")
    except Exception as e:
        conn.rollback()
        print(f"[ERREUR] Création des vues : {e}")
        raise
    finally:
        try:
            cur.close()
        finally:
            conn.close()    

def state_stocks():
    """
    Lit v_stock, affiche les alertes (stock < 0), exporte un CSV.
    """
    conn = mysql.connector.connect(**MYSQL_CONF)   
    cur = conn.cursor()
    query="""
            SELECT
                id_produit,
                produit AS nom_produit,
                total_prod,
                total_cmds,
                stock
            FROM v_stock;
        """
    try:
        cur.execute(query)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        df =pd.DataFrame(rows, columns=cols)
    except Exception as e :
        print(f"[ERREUR] Impossible de récupérer les données : {e}")
        raise
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()
    # Alerte lisible
    negatives = df[df["stock"] < 0][["id_produit", "nom_produit", "stock"]]
    if not negatives.empty:
        print(f"\n[ALERTE] {len(negatives)} produit(s) avec stock négatif :")
        print(negatives.to_string(index=False))
        log_etl("post_etl", "stock", f"{len(negatives)} produit(s) avec stock négatif", data_log=DATA_LOG)
    else:
        print("[INFO] Aucun stock négatif détecté.")

    """Export CSV avec timestamp (sans confirmation)."""
    os.makedirs(DATA_STOCK, exist_ok=True)
    current_date = datetime.now().strftime("%Y-%m-%d_%H-%M")
    path = os.path.join(DATA_STOCK, f"etat_stocks_{current_date}.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig", sep=";", decimal=",")
    print(f"\n[INFO] Export état des stocks terminé : {path}")

def run_post_etl() :
    """
    Refresh vues globales,création CSV, alertes stock
    """
    try:
        refresh_views()
        state_stocks()
        print("[OK] Fin ETL : vues à jour, CSV généré.")
        log_etl("post_etl", "global", "Vues mises a jour et CSV stock genere", data_log=DATA_LOG)
        query_menu()
    
    except Exception as e:
        log_etl("erreur", "post_etl", f"Post-ETL interrompu : {e}", data_log=DATA_LOG)