import os
import json
from datetime import datetime
import requests

# --- CONFIGURAZIONE ---
# Inserisci qui la tua logica di download esistente dall'API di Weather Underground
# Assicurati che alla fine dello scaricamento tu abbia una lista di dizionari chiamata 'features'
# (ciascuna strutturata come GeoJSON Feature con "geometry" e "properties")

# ESEMPIO DELLA STRUTTURA CHE DEVI AVERE NEL TUO SCRIPT:
features = []

# (Qui dentro cicli le stazioni della tua zona e popoli 'features')
# Esempio fittizio del ciclo di popolamento:
# for station in stazioni:
#     feature = {
#         "type": "Feature",
#         "geometry": {
#             "type": "Point",
#             "coordinates": [lon, lat]
#         },
#         "properties": {
#             "station_id": station.get("stationID"),
#             "neighborhood": station.get("neighborhood"),
#             "time": station.get("obsTimeLocal"),
#             "temp": data_metric.get("temp"),
#             "humidity": data_metric.get("humidity"),
#             "wind_speed": data_metric.get("windSpeed"),
#             "wind_gust": data_metric.get("windGust"),
#             "wind_dir": data_metric.get("winddir"),
#             "pressure": data_metric.get("pressure"),
#             "precip_rate": data_metric.get("precipRate"),
#             "precip_total": data_metric.get("precipTotal"),
#             "dewpoint": data_metric.get("dewpoint"),
#             "solar_radiation": data.get("solarRadiation"),
#             "uv": data.get("uv")
#         }
#     }
#     features.append(feature)

# 1. Creazione dell'oggetto GeoJSON corrente (latest)
latest_data = {
    "type": "FeatureCollection",
    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "features": features
}

# Assicurati che la cartella 'data' esista
os.makedirs("data", exist_ok=True)

# Salva il file latest (sovrascritto ogni volta per la mappa in tempo reale)
with open("data/meteo_latest.json", "w", encoding="utf-8") as f:
    json.dump(latest_data, f, ensure_ascii=False, indent=2)


# --- GESTIONE ARCHIVIO STORICO (OGNI 10 MINUTI) ---

# 2. Crea la cartella 'archive' se non esiste
archive_dir = "archive"
os.makedirs(archive_dir, exist_ok=True)

# Organizza l'archivio creando un file JSON separato per ogni giorno (es. meteo_archive_2026-09-03.json)
oggi_str = datetime.now().strftime("%Y-%m-%d")
archive_file = os.path.join(archive_dir, f"meteo_archive_{oggi_str}.json")

# 3. Leggi l'archivio del giorno esistente o inizializzalo
archive_data = {"type": "FeatureCollection", "features": []}
if os.path.exists(archive_file):
    try:
        with open(archive_file, "r", encoding="utf-8") as f:
            archive_data = json.load(f)
    except Exception as e:
        print(f"Errore lettura archivio esistente: {e}")

# 4. Appendi i nuovi dati all'archivio aggiungendo un timestamp di registrazione
timestamp_archiviazione = datetime.now().isoformat()
for feature in features:
    # Creiamo una copia della feature per l'archivio
    archived_feature = json.loads(json.dumps(feature))
    archived_feature["properties"]["archived_at"] = timestamp_archiviazione
    archive_data["features"].append(archived_feature)

# 5. Salva il file di archivio aggiornato
with open(archive_file, "w", encoding="utf-8") as f:
    json.dump(archive_data, f, ensure_ascii=False, indent=2)

print("Dati correnti aggiornati e archiviati con successo!")
