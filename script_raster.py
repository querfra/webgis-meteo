import os
import json
import numpy as np
from scipy.interpolate import Rbf
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from datetime import datetime
import rasterio
from rasterio.transform import from_bounds

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
        precip = props.get("precip_total")
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

# 2. Definizione griglia ed extent comune
data_lon_min = lons.min() - 0.01
data_lon_max = lons.max() + 0.01
data_lat_min = lats.min() - 0.01
data_lat_max = lats.max() + 0.01

grid_lon = np.linspace(data_lon_min, data_lon_max, 200)
grid_lat = np.linspace(data_lat_min, data_lat_max, 200)
GRID_LON, GRID_LAT = np.meshgrid(grid_lon, grid_lat)
common_extent = [data_lon_min, data_lon_max, data_lat_min, data_lat_max]

os.makedirs("data/raster", exist_ok=True)

# Funzione di supporto per salvare un array numpy in GeoTIFF
def salva_geotiff(filepath, array, extent):
    height, width = array.shape
    xmin, xmax, ymin, ymax = extent
    transform = from_bounds(xmin, ymin, xmax, ymax, width, height)
    
    meta = {
        'driver': 'GTiff',
        'height': height,
        'width': width,
        'count': 1,
        'dtype': 'float32',
        'crs': 'EPSG:4326',
        'transform': transform,
        'nodata': np.nan
    }
    
    with rasterio.open(filepath, 'w', **meta) as dst:
        dst.write(array.astype('float32'), 1)

# 3. Generazione Raster Precipitazioni (RBF)
valid_precip_mask = ~np.isnan(precip_vals)
if np.sum(valid_precip_mask) >= 3:
    rbf_precip = Rbf(lons[valid_precip_mask], lats[valid_precip_mask], precip_vals[valid_precip_mask], function='multiquadric', smooth=0.1)
    GRID_PRECIP = rbf_precip(GRID_LON, GRID_LAT)
    GRID_PRECIP = np.clip(GRID_PRECIP, 0, None)
else:
    GRID_PRECIP = np.zeros_like(GRID_LON)

precip_tif_path = "data/raster/precip_raster.tif"
salva_geotiff(precip_tif_path, GRID_PRECIP, common_extent)

# 4. Generazione Raster Temperatura (RBF)
valid_temp_mask = ~np.isnan(temp_vals)
if np.sum(valid_temp_mask) >= 3:
    rbf_temp = Rbf(lons[valid_temp_mask], lats[valid_temp_mask], temp_vals[valid_temp_mask], function='thin_plate', smooth=0.0)
    GRID_TEMP = rbf_temp(GRID_LON, GRID_LAT)
else:
    GRID_TEMP = np.full_like(GRID_LON, np.nan)

temp_tif_path = "data/raster/temp_raster.tif"
salva_geotiff(temp_tif_path, GRID_TEMP, common_extent)

# 5. Configurazione Colormap personalizzate
# Precipitazioni (stile meteo standard)
precip_colors = [
    "#e6f0ff", "#cce0ff", "#99c2ff", "#66a3ff", "#3385ff", # 0 - 10 mm
    "#0066cc", "#004d99",                                 # 10 - 20 mm
    "#00cc66", "#00994d", "#006633",                      # 20 - 40 mm
    "#66ff33", "#b3ff66", "#ffff66",                      # 40 - 80 mm
    "#ffcc00", "#ff9900", "#ff6600",                      # 80 - 150 mm
    "#ff3300", "#cc0000", "#800000"                       # 150 - 250+ mm
]
precip_cmap = mcolors.LinearSegmentedColormap.from_list("meteo_precip", precip_colors)

# Temperatura (da -25°C a +45°C basata sulla palette termica fornita)
temp_colors = [
    "#1a0033", "#330066", "#4b0082", "#6600cc", "#0033ff", "#0099ff", 
    "#00cccc", "#00ffcc", "#00ff66", "#66ff00", "#ccff00", "#ffff00", 
    "#ffcc00", "#ff9900", "#ff6600", "#ff3300", "#ff0000", "#cc0033", 
    "#990066", "#660066"
]
temp_cmap = mcolors.LinearSegmentedColormap.from_list("meteo_temp", temp_colors)

# PNG Precipitazioni
fig, ax = plt.subplots(figsize=(6, 6), frameon=False)
ax.set_axis_off()
ax.imshow(
    GRID_PRECIP, 
    extent=common_extent, 
    origin='lower', 
    cmap=precip_cmap, 
    alpha=0.85, 
    vmin=0, 
    vmax=250
)
plt.savefig("data/raster/precip_raster.png", bbox_inches='tight', pad_inches=0, transparent=True)
plt.close()

# PNG Temperatura (con scala termica aggiornata da -25 a 45)
fig, ax = plt.subplots(figsize=(6, 6), frameon=False)
ax.set_axis_off()
ax.imshow(
    GRID_TEMP, 
    extent=common_extent, 
    origin='lower', 
    cmap=temp_cmap, 
    alpha=0.6, 
    vmin=-25, 
    vmax=45
)
plt.savefig("data/raster/temp_raster.png", bbox_inches='tight', pad_inches=0, transparent=True)
plt.close()

# 6. Salvataggio metadati JSON dei confini
bounds = {
    "bounds": [
        [data_lat_min, data_lon_min],
        [data_lat_max, data_lon_max]
    ],
    "generated_at": datetime.now().isoformat(),
    "note": "Raster GeoTIFF e PNG generati con scale cromatiche personalizzate per pioggia e temperatura."
}
with open("data/raster/raster_bounds.json", "w") as f:
    json.dump(bounds, f)

print("Elaborazione completata: mappe di pioggia e temperatura aggiornate con le nuove palette.")
