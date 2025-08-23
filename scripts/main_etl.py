from db_sql import init_database
from extract import extract
from transform import transform
from load import load
from post_etl import run_post_etl
from commun import log_etl
from commun import rename_tables
from commun import rename_columns
from commun import database_exists
from commun import DATA_LOG

import subprocess
import os

#-------
# MAIN
#-------

def main():
    
    # 0. Vérification base cible existe
    print("***** Vérification base cible *****")
    if not database_exists():
        for fname in os.listdir(DATA_LOG):
            if fname.startswith("last_") and fname.endswith("_id.txt"):
                path = os.path.join(DATA_LOG, fname)
                try:
                    os.remove(path)
                except Exception as e:  
                    print(f"[ERREUR] Suppression impossible pour {fname} : {e}")
        print("[INFO] Base à créer.")
        init_database()
        
    else:
        print(f"[INFO] Base déjà existante.\n")

    # 1. Extraction
    print("***** 1. Extraction des données *****")
    dict_data = extract()
    if not dict_data:
        print("Aucune donnée trouvée, fin du process.")
        return
    print("Extraction terminée :")
    for table,df in dict_data.items():
        print(f"-> {table} : {len(df)} lignes.")
        log_etl("extract_ok", table, f"{len(df)} lignes", data_log=DATA_LOG)  

    # 2 Renommage des noms de tables et colonnes
    dict_data=rename_tables(dict_data)
    for table,df in dict_data.items():
        renamed_df=rename_columns(df,table)
        dict_data[table]=renamed_df
    print(f"-> Renommage noms tables et colonnes(voir log)\n")
    log_etl("rename_ok", "global", "Tables et colonnes renommees", data_log=DATA_LOG)
    
    # 3 Transformation
    print("***** 2. Transformation des données ******")
    dict_transformed, rejected_indices = transform(dict_data)
    print("Transformation terminée :")
    for table,df in dict_transformed.items():
        if len(df) > 0 :
            print(f"-> {table} : {len(df)} ligne(s) nettoyée(s).")
            log_etl("transform_ok", table, f"{len(df)} lignes nettoyees", data_log=DATA_LOG) 
    for table, indices in rejected_indices.items():
        if len(indices) > 0:
            print(f"[ALERTE] {table} : {len(indices)} ligne(s) rejetée(s) (voir log)")
    # vérification qu'il y a toujours des données
    non_empty_dict= {
        table:df for table,df in dict_transformed.items()
        if df is not None and not df.empty 
    }
    if not non_empty_dict :
        print(f"[INFO] Aucune donnée à charger.")
        return
   
    # 4 Chargement dans la base cible
    print(f"\n***** 3 : Chargement dans la BDD centrale *****")
    load_results=load(non_empty_dict)
    for table,count in load_results.items():
        print(f"-> {table} : {count} ligne(s) ajoutée(s).")
        log_etl("load_ok", table, f"{count} lignes inserees", data_log=DATA_LOG)
    print(f"Chargement terminé.\n")

    # 5 génération de l'état du stock
    run_post_etl()
    


if __name__ == "__main__":
    main()