import os
import pandas as pd
import mysql.connector

from dotenv import load_dotenv
from datetime import datetime
from commun import MYSQL_CONF

load_dotenv("../.env")
DATA_STOCK = os.getenv("DATA_STOCK", "")

#---------------
# FONCTIONS
#---------------

def is_iso_date(input_date):
    """Vérifie le format et l'existance de la date (YYYY-MM-DD)."""
    try:
        datetime.strptime(input_date, "%Y-%m-%d")
        return True
    except ValueError:
        print(f"\n/!\\ La date '{input_date}' est invalide. Format attendu : YYYY-MM-DD.")
        return False

def ask_period_build_where():
    """
    Saisie + validation + normalisation + WHERE (sur c.date).
    Retour:
      (where_sql, title_tag, file_tag)  ou  None si erreur/saisie invalide.
    """
    start_date = input("Date début (YYYY-MM-DD, vide = commande jusqu'à date fin) : ").strip()
    end_date   = input("Date fin (YYYY-MM-DD, vide = commande à partir de date début) : ").strip()

    start_date = start_date if start_date else None
    end_date   = end_date   if end_date   else None

    # Au moins une date
    if not start_date and not end_date:
        print("\n/!\\ Vous devez saisir au moins une date (début ou fin).")
        return None

    # Validation format si fourni
    if start_date and not is_iso_date(start_date):
        return None
    if end_date and not is_iso_date(end_date):
        return None

    # Inversion si besoin (si les deux sont présentes)
    if start_date and end_date:
        d1 = datetime.strptime(start_date, "%Y-%m-%d").date()
        d2 = datetime.strptime(end_date,   "%Y-%m-%d").date()
        if d1 > d2:
            print(f"[INFO] Inversion des bornes (début {start_date} > fin {end_date}).")
            d1, d2 = d2, d1
            start_date = d1.strftime("%Y-%m-%d")
            end_date   = d2.strftime("%Y-%m-%d")

    # WHERE (fin inclusive, plus naturel pour l'utilisateur)
    parts = []
    if start_date:
        parts.append(f"c.date >= '{start_date}'")
    if end_date:
        parts.append(f"c.date <= '{end_date}'")
    where_sql = "WHERE " + " AND ".join(parts) if parts else ""

    # Tags pour titre + nom de fichier
    if start_date and not end_date:
        title_tag = f"à partir du {start_date}"
        file_tag  = f"sup_{start_date}"
    elif end_date and not start_date:
        title_tag = f"jusqu'au {end_date}"
        file_tag  = f"inf_{end_date}"
    else:
        title_tag = f"du {start_date} au {end_date}"
        file_tag  = f"{start_date}_{end_date}"

    return where_sql, title_tag, file_tag

def check_view_exists(view_name):
    query = f"SHOW FULL TABLES WHERE Table_type = 'VIEW' AND Tables_in_{MYSQL_CONF['database']} = '{view_name}';"
    df = run_sql(query)
    return not df.empty

def run_sql(query):
    """Exécute un SELECT et retourne un DataFrame (sans pd.read_sql)."""
    conn = mysql.connector.connect(**MYSQL_CONF)
    cur = conn.cursor()
    try:
        cur.execute(query)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        return pd.DataFrame(rows, columns=cols)
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()

def display_df(df, title):
    if df is None:
        return
    if title:
        star="*"*20
        print(f"\n{star} {title} {star}\n")
    if df.empty:
        print("[INFO] Aucun résultat.")
    else:
        print(df.to_string(index=False))
        print(f"\n{len(df)} ligne(s).")

def export_csv(df, filename):
    if df is None:
        return
    confirm = input("Exporter en CSV ? (o/n) : ").strip().lower()
    if confirm not in ("o", "oui"):
        print("[INFO] Export annulé.")
        return
    os.makedirs(DATA_STOCK, exist_ok=True)
    current_date = datetime.now().strftime("%Y-%m-%d_%H-%M")
    path = os.path.join(DATA_STOCK, f"{filename}_{current_date}.csv")
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"[INFO] Fichier exporté : {path}")

#---------------
# REQUETES
#---------------

def get_global_stock():
    """ menu choix 1 """
    if not check_view_exists("v_stock"):
        print(f"[ERREUR] La vue v_stock n'existe pas. Veuillez lancer l'ETL pour la créer.")
        return
    return run_sql("SELECT * FROM v_stock;")

def get_stock_at_date(target_date):
    """ menu choix 2 """
    if not is_iso_date(target_date):
        return

    query_stock_at_date = f"""
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
            WHERE date <= '{target_date}'
            GROUP BY id_pdt
        ) AS prod ON prod.id_pdt = p.id
        LEFT JOIN (
            SELECT lc.id_pdt, SUM(lc.quantite) AS total_cmds
            FROM lignes_cmd AS lc
            JOIN commandes AS c ON c.id = lc.id_cmd
            WHERE c.date <= '{target_date}'
            GROUP BY lc.id_pdt
        ) AS cmd ON cmd.id_pdt = p.id
        ORDER BY p.id_src;
    """
    return run_sql(query_stock_at_date)

def get_orders_by_region():
    """ menu choix 3 """
    if not check_view_exists("v_cmds_par_region"):
        print(f"[ERREUR] La vue v_cmds_par_region n'existe pas. Veuillez lancer l'ETL pour la créer.")
        return
    return run_sql("SELECT * FROM v_cmds_par_region;")

def get_orders_by_region_date(where_sql):
    """ menu choix 4 """
    query_orders = f"""
        SELECT 
            r.nom    AS region,
            p.id_src AS id_produit,
            p.nom    AS produit,
            SUM(lc.quantite) AS total_commandes
        FROM lignes_cmd lc
        JOIN commandes  c ON lc.id_cmd      = c.id
        JOIN revendeurs v ON c.id_revendeur = v.id
        JOIN regions    r ON v.id_region    = r.id
        JOIN produits   p ON lc.id_pdt      = p.id
        {where_sql}
        GROUP BY r.nom, p.id_src, p.nom
        ORDER BY r.nom, p.id_src;
    """
    return run_sql(query_orders)

def get_sales_by_region():
    """ menu choix 5 """
    if not check_view_exists("v_chiffre_affaires_par_region"):
        print(f"[ERREUR] La vue v_chiffre_affaires_par_region n'existe pas. Veuillez lancer l'ETL pour la créer.")
        return
    return run_sql("SELECT * FROM v_chiffre_affaires_par_region;")

def get_sales_by_region_date(where_sql):
    """ menu choix 6 """
    query_orders = f"""
        SELECT
            r.nom AS region,
            ROUND(SUM(lc.quantite * lc.prix_unitaire), 2) AS total_chiffre_affaires,
            COUNT(DISTINCT c.num_cmd) AS nb_commandes
        FROM lignes_cmd lc
        JOIN commandes  c  ON lc.id_cmd = c.id
        JOIN revendeurs re ON c.id_revendeur = re.id
        JOIN regions    r  ON re.id_region   = r.id
        {where_sql}
        GROUP BY r.nom
        ORDER BY r.nom;
    """
    return run_sql(query_orders)

#--------
# MENU
#--------

def display_menu():
    print("\n" +"*"*10 +" TABLEAU DE BORD "+"*"*10+"\n")
    print("[ STOCK GLOBAL ]")
    print("   1. Actuel")
    print("   2. A une date précise")
    print("\n[ COMMANDES PAR REGION ]")
    print("   3. Globales")
    print("   4. Sur une période")
    print("\n[ CHIFFRE D'AFFAIRES PAR REGION ]")
    print("   5. Globales")
    print("   6. Sur une période")
    print("\n 0. Quitter\n")

def query_menu():
    while True:
        display_menu()
        choice = input("Votre choix : ").strip()
        try:

            if choice == "1":
                df = get_global_stock()
                display_df(df, "STOCK GLOBAL (actuel))")
                export_csv(df, "stock_global_actuel")

            elif choice == "2":
                d = input("Date (YYYY-MM-DD) : ").strip()
                df = get_stock_at_date(d)
                display_df(df, f"STOCK GLOBAL (à la date {d})")
                export_csv(df, f"stock_global_{d}")

            elif choice == "3":
                df = get_orders_by_region()
                display_df(df, "COMMANDES PAR REGION (globales)")
                export_csv(df, "commandes_par_region_global")

            elif choice == "4":
                res = ask_period_build_where()
                if res is None:
                    continue
                where_sql, title_tag, file_tag = res
                df = get_orders_by_region_date(where_sql)
                display_df(df, f"COMMANDES PAR REGION ({title_tag})")
                export_csv(df, f"commandes_par_region_{file_tag}")

            elif choice == "5":
                df = get_sales_by_region()
                display_df(df, "CHIFFRE D'AFFAIRES PAR REGION (global)")
                export_csv(df, "chiffre_affaires_par_region_global")

            elif choice == "6":
                res = ask_period_build_where()
                if res is None:
                    continue
                where_sql, title_tag, file_tag = res
                df = get_sales_by_region_date(where_sql)
                display_df(df, f"CHIFFRE D'AFFAIRES PAR REGION ({title_tag})")
                export_csv(df, f"chiffre_affaires_par_region_{file_tag}")
            elif choice == "0":
                print("[INFO] Fin du Tableau de bord.")
                break
            else:
                print(f"\n /!\\ Choix invalide.")
        except Exception as e:
            print(f"[ERREUR] Une erreur est survenue : {e}")

if __name__ == "__main__":
    query_menu()
