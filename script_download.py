import os
import json
from datetime import datetime
import requests

# --- CONFIGURAZIONE ---
API_KEY = "LA_TUA_API_KEY_DI_WEATHER_UNDERGROUND"
STATION_IDS = [
    "IBRINDISI2", # Sostituisci o aggiungi qui i codici delle tue stazioni
]

features = []

for station_id in STATION_IDS:
    url = "https://api.weather.com/v2/pws/observations/current"
    
    # Parametri completi con il parametro per forzare i decimali
    params = {
        "stationId": station_id,
        "format": "json",
        "units": "m",
        "numericPrecision": "decimal",
        "apiKey": API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            observations = data.get("observations", [])
            
            if observations:
                obs = observations[0]
                lat = obs.get("lat")
                lon = obs.get("lon")
                
                if lat is not None and lon is not None:
                    metric = obs.get("metric", {})
                    
                    # Funzione di utilità per convertire in float in modo sicuro
                    def to_float(val):
                        if val is not None:
                            try:
                                return float(val)
                            except (ValueError, TypeError):
                                return None
                        return None

                    feature = {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [float(lon), float(lat)]
                        },
                        "properties": {
                            "station_id": station_id,
                            "neighborhood": obs.get("neighborhood", "N/D"),
                            "time": obs.get("obsTimeLocal", "N/D"),
                            "temp": to_float(metric.get("temp")),
                            "humidity": to_float(obs.get("humidity")),
                            "wind_speed": to_float(metric.get("windSpeed")),
                            "wind_gust": to_float(metric.get("windGust")),
                            "wind_dir": to_float(obs.get("winddir")),
                            "pressure": to_float(metric.get("pressure")),
                            "precip_rate": to_float(metric.get("precipRate")),
                            "precip_total": to_float(metric.get("precipTotal")),
                            "dewpoint": to_float(metric.get("dewpt")),
                            "solar_radiation": to_float(obs.get("solarRadiation")),
                            "uv": to_float(obs.get("uv"))
                        }
                    }
                    features.append(feature)
        else:
            print(f"Errore HTTP {response.status_code} per la stazione {station_id}")
    except Exception as e:
        print(f"Errore di connessione per la stazione {station_id}: {e}")

# 1. Aggiornamento file latest (ogni 5 minuti via GitHub Actions)
latest_data = {
    "type": "FeatureCollection",
    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "features": features
}

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

    # Controllo temporale: archivia solo se sono trascorsi almeno 9 minuti dall'ultimo salvataggio
    esegui_archivio = True
    if archive_data["features"]:
        ultimo_record = archive_data["features"][-1]
        ultima_data_str = ultimo_record.get("properties", {}).get("archived_at")
        if ultima_data_str:
            ultima_data = datetime.fromisoformat(ultima_data_str)
            differenza_minuti = (datetime.now() - ultima_data).total_seconds() / 60
            if differenza_minuti < 9:
                esegui_archivio = False

    if esegui_archivio:
        timestamp_archiviazione = datetime.now().isoformat()
        for feature in features:
            archived_feature = json.loads(json.dumps(feature))
            archived_feature["properties"]["archived_at"] = timestamp_archiviazione
            archive_data["features"].append(archived_feature)

        with open(archive_file, "w", encoding="utf-8") as f:
            json.dump(archive_data, f, ensure_ascii=False, indent=2)
        print("Archivio storico aggiornato con successo con i decimali.")
    else:
        print("Saltato l'aggiornamento dell'archivio (intervallo di 10 minuti non ancora raggiunto).")
else:
    print("Nessun dato valido scaricato in questa esecuzione.")
