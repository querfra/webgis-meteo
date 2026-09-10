import os
import json
from datetime import datetime

# Percorsi dei file
latest_path = "data/meteo_latest.json"
if not os.path.exists(latest_path):
    exit("File dati correnti non trovato.")

with open(latest_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Data odierna o estrapolata dall'ultimo aggiornamento del file
today_str = datetime.now().strftime("%Y-%m-%d")

stations_data = {}

for feature in data.get("features", []):
    props = feature.get("properties", {})
    station_id = props.get("station_id")
    if not station_id:
        continue
        
    temp = props.get("temp")
    # Prende l'ultimo valore disponibile per la pioggia (rate o total)
    precip = props.get("precip_total") if props.get("precip_total") is not None else props.get("precip_rate")
    
    if station_id not in stations_data:
        stations_data[station_id] = {
            "feature": feature,
            "temps": [],
            "last_precip": precip if precip is not None else 0.0
        }
    
    if temp is not None:
        stations_data[station_id]["temps"].append(float(temp))
    
    if precip is not None:
        stations_data[station_id]["last_precip"] = float(precip)

# Costruzione delle feature finali con Min, Max e Ultima Pioggia del giorno
archive_features = []
for station_id, info in stations_data.items():
    feat = info["feature"]
    temps = info["temps"]
    
    t_max = max(temps) if temps else None
    t_min = min(temps) if temps else None
    
    feat["properties"]["temp_max"] = t_max
    feat["properties"]["temp_min"] = t_min
    feat["properties"]["precip_final"] = info["last_precip"]
    feat["properties"]["archived_at"] = today_str
    
    archive_features.append(feat)

archive_data = {
    "type": "FeatureCollection",
    "date": today_str,
    "features": archive_features
}

# Salvataggio nella cartella archive richiesta da index.html
os.makedirs("archive", exist_ok=True)
archive_path = f"archive/meteo_archive_{today_str}.json"

with open(archive_path, "w", encoding="utf-8") as f:
    json.dump(archive_data, f, ensure_ascii=False, indent=2)

print(f"Archivio giornaliero salvato correttamente in: {archive_path}")
