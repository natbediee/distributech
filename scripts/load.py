import pandas as pd
import os
import mysql.connector

from dotenv import load_dotenv
from commun import log_etl
from commun import MYSQL_CONF
from commun import EQUIVALENT_TABLES


load_dotenv()
DATA_LOG = os.getenv("DATA_LOG")

def load(dict_transformed):

    results = {}
    mapping_produits = {}
    mapping_commandes = {}

    conn = mysql.connector.connect(**MYSQL_CONF)
    cursor = conn.cursor()

    # 1. Insérer d'abord les tables "racines" (sans dépendances)
    if 'regions' in dict_transformed:
        df_regions = dict_transformed['regions']
        if not df_regions.empty:
            results['regions'] = insert_dataframe(conn, cursor, df_regions, 'regions')
            max_id = df_regions["id"].max()
            save_last_id('regions', int(max_id))

    if 'revendeurs' in dict_transformed:
        df_revendeurs = dict_transformed['revendeurs']
        if not df_revendeurs.empty:
            results['revendeurs'] = insert_dataframe(conn, cursor, df_revendeurs, 'revendeurs')
            max_id = df_revendeurs["id"].max()
            save_last_id('revendeurs', int(max_id))

    if 'produits' in dict_transformed:
        df_produits = dict_transformed['produits']
        if not df_produits.empty:
            results['produits'] = insert_dataframe(conn, cursor, df_produits, 'produits')
            max_id = df_produits["id_src"].max()
            save_last_id('produits', int(max_id))

    # 2. Mettre à jour le mapping produits (id_src -> id auto)
    cursor.execute("SELECT id, id_src FROM produits")
    for new_id, id_src in cursor.fetchall():
        mapping_produits[id_src] = new_id

    # 3. Insérer commandes (doit être fait avant lignes_cmd)
    if 'commandes' in dict_transformed:
        df_commandes = dict_transformed['commandes']
        if not df_commandes.empty:
            commandes_cols = ['num_cmd', 'date', 'id_revendeur']
            commandes = df_commandes[commandes_cols].drop_duplicates()
            results['commandes'] = insert_dataframe(conn, cursor, commandes, 'commandes')

            # Mettre à jour le mapping commandes (num_cmd -> id auto)
            cursor.execute("SELECT id, num_cmd FROM commandes")
            for new_id, num_cmd in cursor.fetchall():
                mapping_commandes[num_cmd] = new_id

            # 4. lignes_cmd doit utiliser les id produits & commandes
            lignes_cmd_cols = ['num_cmd', 'id_pdt', 'quantite', 'prix_unitaire']
            lignes_cmd = df_commandes[lignes_cmd_cols].copy()
            lignes_cmd['id_cmd'] = lignes_cmd['num_cmd'].map(mapping_commandes)
            lignes_cmd['id_pdt'] = lignes_cmd['id_pdt'].map(mapping_produits)
            lignes_cmd = lignes_cmd.drop(columns=['num_cmd'])
            results['lignes_cmd'] = insert_dataframe(conn, cursor, lignes_cmd, 'lignes_cmd')

    # 5. production
    if 'production' in dict_transformed:
        df_production = dict_transformed['production']
        if not df_production.empty:
            # Remplacement id_pdt
            if 'id_pdt' in df_production.columns:
                df_production['id_pdt'] = df_production['id_pdt'].map(mapping_produits)
            results['production'] = insert_dataframe(conn, cursor, df_production, 'production')
            max_id = df_production["id"].max()
            save_last_id('production', int(max_id))

    # Commit & fermeture
    conn.commit()
    cursor.close()
    conn.close()
    return results

def insert_dataframe(conn,cursor, df, table):
    if df.empty:
        print(f"[INFO] Aucune donnée à insérer dans {table}")
        return
    columns = list(df.columns)
    rows_ok = 0

    for idx in range(len(df)):
        row = df.iloc[idx]
        # Construction des valeurs
        values = []
        
        for value in row:
            if pd.isna(value):
                values.append("NULL")
            elif isinstance(value,pd.Timestamp):
                values.append(f"'{value.strftime('%Y-%m-%d')}'")
            elif isinstance(value, str):
                value = value.replace("'", "\\'")
                values.append(f"'{value}'")
            else:
                values.append(str(value))

        # Construction de la requête
        columns_str = ", ".join(columns)
        values_str = ", ".join(values)
        
        query = f"INSERT INTO {table} ({columns_str}) VALUES ({values_str});"
        try : 
            cursor.execute(query)
            conn.commit()
            rows_ok+=1
        except Exception as e:
            log_etl("ERREUR_INSERT",{table},f"Erreur ligne {idx}: {e}",data_log=DATA_LOG)
    return rows_ok

def save_last_id(target_table, last_id):
    for src, target in EQUIVALENT_TABLES.items():
        if target == target_table:
            name_table=src
            break
        else:
            name_table=target_table
    path = f"{DATA_LOG}/last_{name_table}_id.txt"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(str(last_id))
    