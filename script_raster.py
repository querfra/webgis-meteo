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

lons, lats, precip_vals, temp_vals = [], [], [], []
for feature in data.get("features", []):
    props = feature.get("properties", {})
    geometry = feature.get("geometry", {})
    coords = geometry.get("coordinates", [])
    
    if len(coords) >= 2:
        lon, lat = coords[0], coords[1]
        precip = props.get("precip_rate")
        temp = props.get("temp")
        
        lons.append(lon)
        lats.append(lat)
        precip_vals.append(float(precip) if precip is not None else 0.0)
        temp_vals.append(float(temp) if temp is not None else np.nan)

if len(lons) < 3:
    print("Dati insufficienti per l'interpolazione raster.")
    exit()

lons = np.array(lons)
lats = np.array(lats)
precip_vals = np.array(precip_vals)
temp_vals = np.array(temp_vals)

# --- MODIFICA: Calcolo UNICO di griglia ed extent ---
# Calcoliamo i confini comuni basati sui dati totali
data_lon_min = lons.min() - 0.05
data_lon_max = lons.max() + 0.05
data_lat_min = lats.min() - 0.05
data_lat_max = lats.max() + 0.05

# Definiamo la griglia geografica comune
grid_lon = np.linspace(data_lon_min, data_lon_max, 200)
grid_lat = np.linspace(data_lat_min, data_lat_max, 200)
GRID_LON, GRID_LAT = np.meshgrid(grid_lon, grid_lat)

# Questo è l'EXTENT che useremo per ENTRAMBE le immagini
common_extent = [data_lon_min, data_lon_max, data_lat_min, data_lat_max]
# ---------------------------------------------------

os.makedirs("data/raster", exist_ok=True)

# 3. Generazione Raster Precipitazioni (usa common_extent e la griglia comune)
GRID_PRECIP = griddata((lons, lats), precip_vals, (GRID_LON, GRID_LAT), method='linear', fill_value=0)
fig, ax = plt.subplots(figsize=(6, 6), frameon=False)
ax.set_axis_off()
# Impostiamo l'extent calcolato sopra
ax.imshow(GRID_PRECIP, extent=common_extent, origin='lower', cmap='Blues', alpha=0.6, vmin=0, vmax=max(5, np.nanmax(precip_vals)))
plt.savefig("data/raster/precip_raster.png", bbox_inches='tight', pad_inches=0, transparent=True)
plt.close()

# 4. Generazione Raster Temperatura (usa lo STESSO common_extent)
valid_temp_mask = ~np.isnan(temp_vals)
if np.sum(valid_temp_mask) >= 3:
    GRID_TEMP = griddata((lons[valid_temp_mask], lats[valid_temp_mask]), temp_vals[valid_temp_mask], (GRID_LON, GRID_LAT), method='linear', fill_value=np.nan)
    
    # Calcolo dinamico dei limiti temperatura (opzionale ma consigliato)
    t_min = np.nanmin(temp_vals[valid_temp_mask]) - 1.0
    t_max = np.nanmax(temp_vals[valid_temp_mask]) + 1.0
    if t_min == t_max: t_min -= 1.0; t_max += 1.0

    fig, ax = plt.subplots(figsize=(6, 6), frameon=False)
    ax.set_axis_off()
    # Impostiamo l'IDENTICO extent usato per le precipitazioni
    ax.imshow(GRID_TEMP, extent=common_extent, origin='lower', cmap='RdBu_r', alpha=0.6, vmin=t_min, vmax=t_max)
    plt.savefig("data/raster/temp_raster.png", bbox_inches='tight', pad_inches=0, transparent=True)
    plt.close()

# 5. Salvataggio dei confini geografici (bounds) comuni per Leaflet
bounds = {
    "bounds": [
        [data_lat_min, data_lon_min], # Angolo Sud-Ovest
        [data_lat_max, data_lon_max]  # Angolo Nord-Est
    ],
    "generated_at": datetime.now().isoformat(),
    "note": "I limiti sono stati allineati tra temperatura e precipitazioni."
}
with open("data/raster/raster_bounds.json", "w") as f:
    json.dump(bounds, f)

print("Raster di precipitazioni e temperatura generati con successo e perfettamente allineati.")
