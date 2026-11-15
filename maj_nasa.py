import os
import json
from datetime import datetime, timedelta
import pandas as pd
import xarray as xr
import earthaccess

os.environ["EARTHDATA_USERNAME"] = os.environ.get("EARTHDATA_USERNAME", "")
os.environ["EARTHDATA_PASSWORD"] = os.environ.get("EARTHDATA_PASSWORD", "")
auth = earthaccess.login(strategy="environment")

MAP_KEY = os.environ.get("FIRMS_MAP_KEY", "")
bukavu_bbox = (28.80, -2.56, 28.92, -2.45)
zone_firms = "28.80,-2.56,28.92,-2.45"

# 1. Feux en quasi temps réel (NASA FIRMS - dernières 24h)
feux_detectes = []
try:
    serveur = "firms.modaps.eosdis.nasa.gov"
    url_firms = f"https://{serveur}/api/area/csv/{MAP_KEY}/VIIRS_SNPP_NRT/{zone_firms}/1"
    df_firms = pd.read_csv(url_firms)
    for _, row in df_firms.iterrows():
        feux_detectes.append({
            "Type_Alerte": "Combustion_Active",
            "Latitude": round(float(row["latitude"]), 5),
            "Longitude": round(float(row["longitude"]), 5),
            "Puissance_MW": round(float(row["frp"]), 1),
            "Date_Satellite": f"{row['acq_date']} {row['acq_time']} UTC"
        })
except Exception as e:
    print("Info FIRMS :", e)

# 2. Dernière mesure de pluie (NASA GPM IMERG)
pluie_max = 0.0
try:
    date_fin = datetime.utcnow().strftime("%Y-%m-%d")
    date_debut = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")
    res_gpm = earthaccess.search_data(short_name="GPM_3IMERGHHE", bounding_box=bukavu_bbox, temporal=(date_debut, date_fin))
    if res_gpm:
        fichiers = earthaccess.download(res_gpm[-1:], local_path="./temp_nasa")
        ds = xr.open_dataset(fichiers[0], group="Grid", decode_times=False)
        p_buk = ds["precipitation"].sel(lon=slice(28.80, 28.92), lat=slice(-2.56, -2.45))
        pluie_max = round(float(p_buk.max().values), 2)
except Exception as e:
    print("Info GPM :", e)

# 3. Mise à jour du fichier JSON lu par votre tableau de bord
with open("donnees_base_bukavu.json", "r", encoding="utf-8") as f:
    donnees = json.load(f)

donnees["derniere_mise_a_jour"] = datetime.utcnow().strftime("%d/%m/%Y à %H:%M UTC")
donnees["pluie_max_mmh"] = pluie_max
donnees["statut_alerte"] = "ALERTE ROUGE" if pluie_max >= 15 else ("ALERTE ORANGE" if pluie_max >= 3 else "VIGILANCE VERTE")
if feux_detectes:
    donnees["feux_temps_reel"] = feux_detectes

with open("donnees_live.json", "w", encoding="utf-8") as f:
    json.dump(donnees, f, ensure_ascii=False, indent=2)

print("Mise à jour NASA terminée !")
