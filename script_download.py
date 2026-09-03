import urllib.request
import urllib.parse
import json
import os
from datetime import datetime

API_KEY = "8231f09cfdc44e68b1f09cfdc46e686b"  # Sostituisci con la tua chiave

STATION_IDS = [
    "IBRIND44", "IBRIND51", "IBRIND57", "IBRIND60", "IBRIND14",
    "IBRIND47", "IBRIND37", "IBRIND55", "IBRIND32", "ISANPI44",
    "IPUGLIAL9", "ISANVI152", "ICAROV30"
]

geojson_features = []

for station_id in STATION_IDS:
    params = {
        "stationId": station_id,
        "format": "json",
        "units": "m",
        "numericPrecision": "decimal",
        "apiKey": API_KEY
    }
    url = f"https://api.weather.com/v2/pws/observations/current?{urllib.parse.urlencode(params)}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if 'observations' in data and data['observations']:
                obs = data['observations'][0]
                metric = obs.get('metric', {})
                
                lat = float(obs['lat'])
                lon = float(obs['lon'])
                temp = float(metric['temp']) if metric.get('temp') is not None else None
                wind_dir = int(obs['winddir']) if obs.get('winddir') is not None else 0
                
                if temp is not None:
                    feature = {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [lon, lat]
                        },
                        "properties": {
                            "station_id": station_id,
                            "neighborhood": obs.get('neighborhood', ''),
                            "temp": temp,
                            "humidity": obs.get('humidity'),
                            "wind_dir": wind_dir,
                            "wind_speed": metric.get('windSpeed'),
                            "time": obs.get('obsTimeLocal', '')
                        }
                    }
                    geojson_features.append(feature)
    except Exception as e:
        print(f"Errore nello scaricamento della stazione {station_id}: {e}")

geojson_data = {
    "type": "FeatureCollection",
    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "features": geojson_features
}

# Assicura che la cartella 'data' esista e salva il JSON
os.makedirs("data", exist_ok=True)
with open("data/meteo_latest.json", "w", encoding="utf-8") as f:
    json.dump(geojson_data, f, indent=2, ensure_ascii=False)

print(f"Aggiornamento completato: {len(geojson_features)} stazioni salvate in data/meteo_latest.json")