import os
import json
import numpy as np
from scipy.interpolate import griddata
import matplotlib.pyplot as plt
from datetime import datetime

# 1. Caricamento dati da meteo_latest.json
if not os.path.exists("data/meteo_latest.json"):
    exit("File dati non trovato.")

with open("data/meteo_latest.json", "r", encoding="utf-8") as f:
    data = json.load(f)

lons, lats, vals = [], [], []
for feature in data.get("features", []):
    props = feature.get("properties", {})
    geometry = feature.get("geometry", {})
    coords = geometry.get("coordinates", [])
    precip = props.get("precip_rate")
    
    if precip is not None and len(coords) >= 2:
        lons.append(coords[0])
        lats.append(coords[1])
        vals.append(float(precip))

if len(vals) < 3:
    print("Dati insufficienti per l'interpolazione raster.")
    exit()

lons = np.array(lons)
lats = np.array(lats)
vals = np.array(vals)

# 2. Definizione della griglia geografica (Area di Brindisi)
grid_lon = np.linspace(lons.min() - 0.05, lons.max() + 0.05, 200)
grid_lat = np.linspace(lats.min() - 0.05, lats.max() + 0.05, 200)
GRID_LON, GRID_LAT = np.meshgrid(grid_lon, grid_lat)

# Interpolazione IDW / Lineare tramite griddata
GRID_VALS = griddata((lons, lats), vals, (GRID_LON, GRID_LAT), method='linear', fill_value=0)

# 3. Esportazione come immagine PNG trasparente
os.makedirs("data/raster", exist_ok=True)
fig, ax = plt.subplots(figsize=(6, 6), frameon=False)
ax.set_axis_off()

im = ax.imshow(GRID_VALS, extent=[lons.min() - 0.05, lons.max() + 0.05, lats.min() - 0.05, lats.max() + 0.05],
               origin='lower', cmap='Blues', alpha=0.6, vmin=0, vmax=max(5, vals.max()))

plt.savefig("data/raster/precip_raster.png", bbox_inches='tight', pad_inches=0, transparent=True)
plt.close()

# Salva i confini (bounds) per il posizionamento in Leaflet
bounds = {
    "bounds": [
        [lats.min() - 0.05, lons.min() - 0.05],
        [lats.max() + 0.05, lons.max() + 0.05]
    ],
    "generated_at": datetime.now().isoformat()
}
with open("data/raster/raster_bounds.json", "w") as f:
    json.dump(bounds, f)

print("Raster di precipitazione generato con successo.")
