import os
import sqlite3
import pandas as pd
from commun import log_etl
from dotenv import load_dotenv
import unidecode

#---------------
# CONFIGURATION
#---------------
load_dotenv("../.env")
DATA_IN        = os.getenv("DATA_IN")
DATA_TREATED   = os.getenv("DATA_TREATED")
DATA_LOG       = os.getenv("DATA_LOG")

SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH")
TABLES_SQLITE  = ["produit", "region", "revendeur", "production"]
TABLE_ID_COLUMNS = {"produit": "product_id","region": "region_id","revendeur": "revendeur_id","production": "production_id"}

mapping_csv_to_cible = {
    # numéro de commande
    "numero_commande": "num_cmd","numéro_commande": "num_cmd","num_commande": "num_cmd","numero_de_commande": "num_cmd","numéro de commande": "num_cmd","n°_commande": "num_cmd",
    "n° commande": "num_cmd","commande_numero": "num_cmd","commande_num": "num_cmd","order_number": "num_cmd","cmd":"num_cmd",
    # date de commande
    "commande_date": "date","date_commande": "date","date_de_commande": "date","date de commande": "date","order_date": "date",
    # revendeur id
    "revendeur_id": "id_revendeur","id_revendeur": "id_revendeur","revendeur": "id_revendeur","id revendeur": "id_revendeur","reseller_id": "id_revendeur",
    # region id
    "region_id": "id_region","id_region": "id_region","region": "id_region","id region": "id_region","zone": "id_region",
    # produit id
    "product_id": "id_pdt","id_produit": "id_pdt","produit_id": "id_pdt","id_produit": "id_pdt","produit": "id_pdt","article_id": "id_pdt","article": "id_pdt",
    # quantité
    "quantity": "quantite","quantite": "quantite","qté": "quantite","qte": "quantite","qty": "quantite",
    # prix unitaire
    "unit_price": "prix_unitaire","prix_unitaire": "prix_unitaire","prix unitaire": "prix_unitaire","prix": "prix_unitaire","pu": "prix_unitaire","unit cost": "prix_unitaire"
}
SCHEMA_COLUMNS = {
            "num_cmd", "date", "id_revendeur", "id_pdt", "quantite", "prix_unitaire"
        }

#--------------------
# FONCTION PRINCIPALE
#--------------------
def extract():
    """
    Extraction :
     ▪︎ CSV → commandes
     ▪︎ SQLite → produit, region, revendeur, production
    Retourne un dict unique pour transform()
    """
    dict_data = {}
    
    # → Branche CSV
    df_csv = extract_from_csv(DATA_IN, DATA_TREATED, DATA_LOG)
    if not df_csv.empty:
        dict_data["commandes"] = df_csv

    # → Branche SQLite
    dict_sqlite = extract_from_sqlite(SQLITE_DB_PATH, DATA_LOG)
    for table, df in dict_sqlite.items():
        dict_data[table] = df

    if not dict_data:
        log_etl("extract", "global", "Aucune donnee exploitable trouvee (CSV + SQLite)",DATA_LOG)
        return None
    else:
        return dict_data

#-----------------
# BRANCHE 1 : CSV
#-----------------

def move_file(src, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, os.path.basename(src))
    os.replace(src, dest)

def get_csv_files(folder):
    try:
        return [f for f in os.listdir(folder) if f.lower().endswith(".csv")]
    except FileNotFoundError:
        return []
    
def clean_col(col):
    return unidecode.unidecode(col).replace(" ", "_").lower()

def extract_from_csv(data_in, data_treated, data_log):
    all_rows = []

    for file in get_csv_files(data_in):
        path = os.path.join(data_in, file)
        try:
            df = pd.read_csv(path)
        except Exception as e:
            log_etl("lecture_csv", file, str(e), data_log)
            move_file(path, data_treated)
            continue
        
        # 1. Normalisation des noms de colonnes
        df.columns = [clean_col(col) for col in df.columns]

        # 2. Mapping des colonnes
        df.rename(columns=mapping_csv_to_cible, inplace=True)
        df['source_file'] = file
        df['source_idx']=df.index+1
        all_rows.append(df)
        log_etl("lecture_ok", file, f"{len(df)} lignes a traiter", data_log)
        move_file(path, data_treated)
    if all_rows:
        return pd.concat(all_rows, ignore_index=True)
    else:
        return pd.DataFrame()

#--------------------
# BRANCHE 2 : SQLite
#--------------------

def get_last_id(table, data_log):
    path = os.path.join(data_log, f"last_{table}_id.txt")
    if not os.path.exists(path):
        return 0
    try:
        return int(open(path).read().strip())
    except:
        return 0
    
def extract_from_sqlite(db_path, data_log):
    sql_rows = {}

    if not os.path.exists(db_path):
        log_etl("sqlite_connexion", db_path, "Base SQLite introuvable", data_log)
        return sql_rows
    
    try:
        conn = sqlite3.connect(db_path)
    except Exception as e:
        log_etl("sqlite_connexion", db_path, f"Erreur connexion: {e}", data_log)
        return sql_rows

    for table in TABLES_SQLITE:
        last_id = get_last_id(table, data_log)
        id_col = TABLE_ID_COLUMNS.get(table, "id")
        try:
            query = f"SELECT * FROM {table} WHERE {id_col}> {last_id}"
            df = pd.read_sql_query(query, conn)
            if not df.empty:
                sql_rows[table] = df
            log_etl("sqlite_ok", table, f"{len(df)} lignes a traiter", data_log)
        except Exception as e:
            log_etl("sqlite_query", table, f"Erreur requete: {e}", data_log)

    conn.close()
    return sql_rows