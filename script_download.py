import os
import json
from datetime import datetime
import requests

# --- CONFIGURAZIONE ---
API_KEY = "8231f09cfdc44e68b1f09cfdc46e686b"
STATION_IDS = [
    "IBRIND44", "IBRIND51", "IBRIND57", "IBRIND60", "IBRIND14",
    "IBRIND47", "IBRIND37", "IBRIND55", "IBRIND32", "ISANPI44",
    "IPUGLIAL9", "ISANVI152", "ICAROV30", "IBRIND35", "IBRIND72", "IPUGLIAB15", "ICAROV6", "IOSTUN15", "IOSTUN25", "IBRINDIS4",
    "ICAROV31", "ISANDO87", "IMESAG6", "ISANPA46", "ISANPA27", "IERCHI6", "IORIA40", "IFRANC85", "IFRANC108", "IFRANC86", "IFRANC38",
    "IFRANC119", "IFRANC101", "IFRANC80", "ISQUIN4", "ITREPU3", "ISAVA9"
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

# 1. Aggiornamento file latest
latest_data = {
    "type": "FeatureCollection",
    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "features": features
}

os.makedirs("data", exist_ok=True)
with open("data/meteo_latest.json", "w", encoding="utf-8") as f:
    json.dump(latest_data, f, ensure_ascii=False, indent=2)


# --- 2. GENERAZIONE SUMMARY GIORNALIERO (Max, Min e Ultima Pioggia) ---
if features:
    # Usa il percorso assoluto dello script per evitare problemi di directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    summary_dir = os.path.join(base_dir, "data", "summary")
    
    os.makedirs(summary_dir, exist_ok=True)
    print(f"Cartella summary verificata/creata in: {summary_dir}")
    
    oggi_str = datetime.now().strftime("%Y-%m-%d")
    summary_file = os.path.join(summary_dir, f"summary_{oggi_str}.json")
    
    existing_stations = {}
    if os.path.exists(summary_file):
        try:
            with open(summary_file, "r", encoding="utf-8") as f:
                old_summary = json.load(f)
                for feat in old_summary.get("features", []):
                    sid = feat.get("properties", {}).get("station_id")
                    if sid:
                        existing_stations[sid] = feat["properties"]
        except Exception as e:
            print(f"Errore lettura summary esistente: {e}")
            
    summary_features = []
    
    for feature in features:
        props = feature.get("properties", {})
        station_id = props.get("station_id")
        if not station_id:
            continue
            
        current_temp = props.get("temp")
        current_precip = props.get("precip_total") if props.get("precip_total") is not None else props.get("precip_rate")
        
        prev_props = existing_stations.get(station_id, {})
        
        # Calcolo Temperatura Max accumulata
        t_max = prev_props.get("temp_max")
        if current_temp is not None:
            if t_max is None or float(current_temp) > float(t_max):
                t_max = float(current_temp)
                
        # Calcolo Temperatura Min accumulata
        t_min = prev_props.get("temp_min")
        if current_temp is not None:
            if t_min is None or float(current_temp) < float(t_min):
                t_min = float(current_temp)
                
        # Ultimo dato utile di pioggia
        last_precip = current_precip if current_precip is not None else prev_props.get("precip_final", 0.0)
        
        summary_feature = {
            "type": "Feature",
            "geometry": feature.get("geometry"),
            "properties": {
                "station_id": station_id,
                "neighborhood": props.get("neighborhood"),
                "temp_max": t_max,
                "temp_min": t_min,
                "humidity": props.get("humidity"),
                "precip_final": last_precip,
                "archived_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        summary_features.append(summary_feature)
        
    summary_data = {
        "type": "FeatureCollection",
        "date": oggi_str,
        "features": summary_features
    }
    
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)
    print(f"File summary salvato correttamente in: {summary_file}")

# --- 3. GESTIONE ARCHIVIO STORICO GREZZO (OGNI 9 MINUTI) ---
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
            try:
                ultima_data = datetime.fromisoformat(ultima_data_str)
                differenza_minuti = (datetime.now() - ultima_data).total_seconds() / 60
                if differenza_minuti < 9:
                    esegui_archivio = False
            except Exception:
                pass

    if esegui_archivio:
        timestamp_archiviazione = datetime.now().isoformat()
        for feature in features:
            archived_feature = json.loads(json.dumps(feature))
            archived_feature["properties"]["archived_at"] = timestamp_archiviazione
            archive_data["features"].append(archived_feature)

        with open(archive_file, "w", encoding="utf-8") as f:
            json.dump(archive_data, f, ensure_ascii=False, indent=2)
        print("Archivio storico grezzo aggiornato con successo.")
    else:
        print("Saltato l'aggiornamento dell'archivio (intervallo di 9 minuti non ancora raggiunto).")
else:
    print("Nessun dato valido scaricato in questa esecuzione.")
