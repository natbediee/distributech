import os
import mysql.connector
import pandas as pd

from mysql.connector import Error
from dotenv import load_dotenv
from datetime import datetime

#---------------
# CONFIGURATION
#---------------
load_dotenv()

DATA_LOG = os.getenv("DATA_LOG")

MYSQL_CONF = {
    'host':     os.getenv('DB_HOST'),
    'user':     os.getenv('DB_USER'),
    'password': os.getenv('DB_PSWD'),
    'database': os.getenv('DB_NAME'),
}

EQUIVALENT_TABLES = {
    'region': 'regions',
    'revendeur' : 'revendeurs',
    'produit' : 'produits',   
}

COLUMN_EQUIVALENTS = {
    'regions': {'region_id':'id','region_name':'nom'},
    'revendeurs':{'revendeur_id':'id','revendeur_name':'nom','region_id':'id_region'},
    'produits':{'product_id':'id_src','product_name':'nom','cout_unitaire':'cout_unitaire'},
    'production' :{'production_id':'id','product_id':'id_pdt','quantity':'quantite','date_production':'date'},
}

#---------------
# FONCTIONS
#---------------

def log_etl(type_evenement, source, message, data_log=DATA_LOG):
    now       = datetime.now()
    ts        = now.strftime("%Y-%m-%d %H:%M:%S")
    date_str  = now.strftime("%Y-%m-%d")
    log_file  = os.path.join(data_log, f"log_etl_{date_str}.csv")

    os.makedirs(data_log, exist_ok=True)
    header = not os.path.exists(log_file)

    row = pd.DataFrame([{
        "timestamp":      ts,
        "type_evenement": type_evenement,
        "source":         source,
        "message":        message
    }])
    row.to_csv(log_file, mode="a", index=False, header=header)

def database_exists():
    try:
        DB_NAME = MYSQL_CONF["database"]
        conn = mysql.connector.connect(**MYSQL_CONF)
        cur = conn.cursor()
        cur.execute(f"SHOW DATABASES LIKE '{DB_NAME}'")
        return cur.fetchone() is not None
    except:
        return False
    finally:
        try:
            conn.close()
        except:
            pass

def rename_tables(dict_data):
    dict_dict_renamed ={}
    for name, df in dict_data.items():
        target_name=EQUIVALENT_TABLES.get(name,name)
        if name != target_name:
            log_etl("table renommée", name, f"{name} -> {target_name}",DATA_LOG)
        dict_dict_renamed[target_name]= df
    return dict_dict_renamed

def rename_columns(df,table):
    mapping=COLUMN_EQUIVALENTS.get(table)
    if not mapping:
        return df
    used_mapping={}
    changes=[]
    for old_col, new_col in mapping.items():
        if old_col in df.columns:
            df = df.rename(columns={old_col:new_col})
            used_mapping[old_col]=new_col
            changes.append(f"{old_col} -> {new_col},")
    log_etl("colonnes_renommees",table,' '.join(changes),DATA_LOG)
    return df