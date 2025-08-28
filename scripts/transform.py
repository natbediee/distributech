import pandas as pd
import mysql.connector

from commun import log_etl
from commun import MYSQL_CONF
from commun import DATA_LOG
from commun import SCHEMA_COLUMNS

#---------------
# CONFIGURATION
#---------------

SCHEMA_COLUMN_TYPES = {
    "production": (["date"], ["quantite"]),
    "commandes": (["date"], ["quantite", "prix_unitaire"]),
    "produits": ([], ["cout_unitaire"]),
    "revendeurs": ([], []),
    "regions": ([], []),
}
SCHEMA_REQUIRED_COLUMNS = {
    "regions": {"id", "nom"},
    "revendeurs": {"id", "nom", "id_region"},
    "produits": {"id_src", "nom", "cout_unitaire"},
    "production": {"id", "id_pdt", "date", "quantite"},
    "commandes": {"num_cmd", "date", "id_revendeur","id_pdt", "quantite", "prix_unitaire"}
}
SCHEMA_PK = {
        "produits": "id_src",
        "revendeurs": "id",
        "regions": "id",
        "production": "id",
        "commandes":"num_cmd"
    }
SCHEMA_FK = {
        "production": [("id_pdt", "produits", "id_src")],
        "commandes": [("id_revendeur", "revendeurs", "id"),("id_pdt", "produits", "id_src")],
        "revendeurs": [("id_region", "regions", "id")]
    }

def transform(dict_data):
    """
    Transforme chaque DataFrame du dict_data selon les règles définies par l'organigramme.
    Retourne dict_transform (clé: nom table, valeur: DataFrame nettoyé)
    """

    dict_transformed = {}
    rejected_rows = {table: set() for table in dict_data.keys()}

    for table, df in dict_data.items():
        if df.empty:
            continue

        # 1. Nettoyage préliminaire (espace, minuscule)
        date_columns, numeric_columns = SCHEMA_COLUMN_TYPES.get(table, ([], []))
        text_cols = [col for col in df.select_dtypes(include="object").columns
             if col not in date_columns + numeric_columns]
        for col in text_cols:
            df[col] = df[col].astype(str).str.strip().str.lower()

        # 2. Vérification structure (colonnes attendus)
        expected_columns = SCHEMA_COLUMNS.get(table, set())
        if not expected_columns.issubset(df.columns):
            log_etl("structure", table, f"Colonnes manquantes: {sorted(expected_columns - set(df.columns))}",DATA_LOG)
            rejected_rows[table].update(df.index)
            continue
       
        # 3. Correction de format (dates, num)
        for col in date_columns:
            df[col] = pd.to_datetime(df[col], format="%Y-%m-%d",errors='coerce') #NaN sur erreur
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        # Log si correction (si valeur manquante ou conversion en échec)
        for col in date_columns + numeric_columns:
            nerr = df[col].isna().sum()
            if nerr:
                for idx in df[df[col].isna()].index:
                    source_file,source_idx = get_source_info(df, idx, table)
                    log_etl("format", source_file, f"Ligne {source_idx} : valeurs NaN apres correction dans '{col}'",DATA_LOG)
                    rejected_rows[table].add(idx)
                    
        # 4. Vérification valeurs interdites
        rejected_idx = set()
        # valeur négative
        for col in numeric_columns:
            rejected_idx.update(df.index[df[col] < 0].tolist())
        # données vides
        required_columns = SCHEMA_REQUIRED_COLUMNS.get(table, set())
        for col in required_columns:
            rejected_idx.update(df.index[df[col].isna()].tolist())
        # date > date du jour
        for col in date_columns:
            if col in df.columns:
                rejected_idx.update(df.index[df[col] > pd.Timestamp.today()].tolist())
        #log
        for idx in rejected_idx:
            source_file,source_idx = get_source_info(df, idx, table)
            log_etl("valeur_interdite", source_file, f"Ligne {source_idx} rejetee (valeur interdite)",DATA_LOG)
            rejected_rows[table].add(idx)
        df = df.drop(index=rejected_idx)
        

        # 5. Détection et suppression de doublons dans le df et en base
        unique_key = SCHEMA_PK.get(table)
        if unique_key is not None:
            if table != "commandes" and unique_key in df.columns:
                n_dups = df.duplicated(subset=unique_key, keep='first').sum()
                if n_dups > 0:
                    idx_dups = df[df.duplicated(subset=unique_key, keep='first')].index
                    for idx in idx_dups:
                        source_file,source_idx = get_source_info(df, idx, table)
                        log_etl("doublon", source_file, f"Ligne {source_idx} supprimee (doublon sur {unique_key})")
                        rejected_rows[table].add(idx)
                    df = df.drop_duplicates(subset=unique_key, keep='first')
            db_keys = get_ref_value_from_db(MYSQL_CONF, table, unique_key)
            idx_bdd = df[df[unique_key].isin(db_keys)].index
            if len(idx_bdd) > 0:
                for idx in idx_bdd:
                    source_file,source_idx = get_source_info(df, idx, table)
                    log_etl("doublon_bdd", source_file, f"Ligne {source_idx} supprimee (cle deja presente en base sur {unique_key})")
                    rejected_rows[table].add(idx)
                df = df.drop(index=idx_bdd).reset_index(drop=True)
                

        #5bis. suppresion des lignes strictement identique 
        cols_without_source = [c for c in df.columns if c not in ("source_file", "source_idx")]
        duplicated_mask = df.duplicated(subset=cols_without_source, keep='first')
        idx_duplicated = df[duplicated_mask].index
        for idx in idx_duplicated:
            source_file, source_idx = get_source_info(df, idx, table)
            log_etl("doublon strict", source_file, f"Ligne {source_idx} strictement identique supprimee", DATA_LOG)
            rejected_rows[table].add(idx)
        df = df.drop_duplicates(subset=cols_without_source, keep='first')

        # 6. Retirer lignes KO
        df = df.reset_index(drop=True)
        dict_transformed[table] = df
    
    #7.Vérification des FK
    for table, df in dict_transformed.items():
        fk_checks = SCHEMA_FK.get(table, [])
        for col, ref, ref_col in fk_checks:
            if col not in df.columns:
                continue

            local_values=set()
            # Valeurs autorisées presente dans le df ou bddcible
            if ref in dict_transformed and ref_col in dict_transformed[ref].columns:
                local_values=set(dict_transformed[ref][ref_col])
            else:
                local_values=set()
            db_values = get_ref_value_from_db(MYSQL_CONF, ref, ref_col)
            valid_values = local_values.union(db_values)
            if col in df.columns :
                rejected_idx_fk=~df[col].isin(valid_values)
                if rejected_idx_fk.any():
                    for idx in df[rejected_idx_fk].index:
                        source_file, source_idx = get_source_info(df, idx, table)
                        log_etl("cle_etrangere", source_file,f"Ligne {source_idx} rejetee ({col} absent de {ref})",DATA_LOG)
                        rejected_rows[table].add(source_idx)
                    df=df[~rejected_idx_fk].reset_index(drop=True)
                    

        # MAJ DataFrame après FK
        if "source_idx" in df.columns:
            dict_transformed[table] = df.drop(columns=["source_idx"])
    return dict_transformed,rejected_rows

#----------
# fonction
#----------

def get_ref_value_from_db(mysql_conf, table, col):
    """
    Récupère toutes les valeurs distinctes de la colonne 'col' dans la table cible MySQL.
    """
    conn = mysql.connector.connect(**mysql_conf)
    try:
        query = f"SELECT DISTINCT {col} FROM {table}"
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()  # Liste de tuples
        values = set()
        for row in rows:
            value = row[0]
            values.add(value)
        return values
    finally:
        conn.close()

def get_source_info(df, idx, table):
    if "source_file" in df.columns:
        try:
            source_file = df.at[idx, "source_file"]
        except Exception:
            source_file = table
    else:
        source_file = table

    # Récupère l'index source (ligne d'origine)
    if "source_idx" in df.columns:
        try:
            source_idx = df.at[idx, "source_idx"]
        except Exception:
            source_idx = idx
    else:
        source_idx = idx
    return source_file, source_idx