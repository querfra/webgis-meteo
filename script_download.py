import os
import json
from datetime import datetime
import requests

# --- CONFIGURAZIONE ---
API_KEY = "8231f09cfdc44e68b1f09cfdc46e686b"
# Inserisci qui l'elenco delle stazioni di Brindisi e dintorni che vuoi monitorare
STATION_IDS = [
 "IBRIND44", "IBRIND51", "IBRIND57", "IBRIND60", "IBRIND14",
    "IBRIND47", "IBRIND37", "IBRIND55", "IBRIND32", "ISANPI44",
    "IPUGLIAL9", "ISANVI152", "ICAROV30"
]

features = []

# Cicla le stazioni per scaricare i dati correnti
for station_id in STATION_IDS:
    url = f"https://api.weather.com/v2/pws/observations/current?stationId={station_id}&format=json&units=m&apiKey={API_KEY}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            observations = data.get("observations", [])
            
            if observations:
                obs = observations[0]
                lat = obs.get("lat")
                lon = obs.get("lon")
                
                # Se la stazione restituisce le coordinate valide
                if lat is not None and lon is not None:
                    # Estrazione metrica (gestione sicura dei dati metrici 'metric')
                    metric = obs.get("metric", {})
                    
                    feature = {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [lon, lat]
                        },
                        "properties": {
                            "station_id": station_id,
                            "neighborhood": obs.get("neighborhood", "N/D"),
                            "time": obs.get("obsTimeLocal", "N/D"),
                            "temp": metric.get("temp"),
                            "humidity": obs.get("humidity"),
                            "wind_speed": metric.get("windSpeed"),
                            "wind_gust": metric.get("windGust"),
                            "wind_dir": obs.get("winddir"),
                            "pressure": metric.get("pressure"),
                            "precip_rate": metric.get("precipRate"),
                            "precip_total": metric.get("precipTotal"),
                            "dewpt": metric.get("dewpt"), # Mappato come dewpoint nel popup
                            "dewpoint": metric.get("dewpt"),
                            "solar_radiation": obs.get("solarRadiation"),
                            "uv": obs.get("uv")
                        }
                    }
                    features.append(feature)
        else:
            print(f"Errore HTTP {response.status_code} per la stazione {station_id}")
    except Exception as e:
        print(f"Errore di connessione per la stazione {station_id}: {e}")

# 1. Creazione dell'oggetto GeoJSON corrente (latest)
latest_data = {
    "type": "FeatureCollection",
    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "features": features
}

# Assicurati che la cartella 'data' esista e salva il file latest
os.makedirs("data", exist_ok=True)
with open("data/meteo_latest.json", "w", encoding="utf-8") as f:
    json.dump(latest_data, f, ensure_ascii=False, indent=2)


# --- GESTIONE ARCHIVIO STORICO (OGNI 10 MINUTI) ---

if features:
    archive_dir = "archive"
    os.makedirs(archive_dir, exist_ok=True)

    oggi_str = datetime.now().strftime("%Y-%m-%d")
    archive_file = os.path.join(archive_dir, f"meteo_archive_{oggi_str}.json")

    archive_data = {"type": "FeatureCollection", "features": []}
    if os.path.exists(archive_file):
        try:
            with open(archive_file, "r", encoding="utf-8") as f:
                archive_data = json.load(f)
        except Exception as e:
            print(f"Errore lettura archivio esistente: {e}")

    timestamp_archiviazione = datetime.now().isoformat()
    for feature in features:
        archived_feature = json.loads(json.dumps(feature))
        archived_feature["properties"]["archived_at"] = timestamp_archiviazione
        archive_data["features"].append(archived_feature)

    with open(archive_file, "w", encoding="utf-8") as f:
        json.dump(archive_data, f, ensure_ascii=False, indent=2)

    print(f"Scaricati e archiviati con successo {len(features)} record.")
else:
    print("Nessun dato valido scaricato in questa esecuzione.")
