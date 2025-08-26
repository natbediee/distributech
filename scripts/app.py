from flask import Flask, render_template, abort

from query_menu import get_global_stock, get_orders_by_region, get_sales_by_region


app = Flask(__name__) 

# 1) mapping label + fonction
VIEWS = {
    "v_stock": ("Vue du Stock global", get_global_stock),
    "v_cmds_par_region": ("Commandes par région", get_orders_by_region),
    "v_chiffre_affaires_par_region": ("Chiffre d’affaires par région", get_sales_by_region),
}

def df_to_table(df):
    if df is None or df.empty: return [], []
    return df.columns.tolist(), df.to_dict("records")

# 2) index: utiliser les labels
@app.route("/")
def index():
    vues = [(name, meta[0]) for name, meta in VIEWS.items()]
    return render_template("index.html", vues=vues)

# 3) show_table: passer le label comme title
@app.route("/table/<name>")
def show_table(name):
    meta = VIEWS.get(name)
    if not meta:
        abort(404, "Vue inconnue")
    label, func = meta
    df = func()
    cols, rows = df_to_table(df)
    return render_template("table.html", title=label, columns=cols, rows=rows)

if __name__ == "__main__": 
    app.run(debug=True)