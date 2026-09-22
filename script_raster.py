import os
import json
import numpy as np
import geopandas as gpd
from scipy.interpolate import Rbf
import matplotlib.pyplot as plt
from datetime import datetime
import rasterio
import rasterio.mask
from rasterio.transform import from_bounds
import fiona

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

# Funzione di supporto per salvare un array numpy in GeoTIFF temporaneo
def salva_geotiff_temporaneo(filepath, array, extent):
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

temp_precip_path = "data/raster/precip_temp_full.tif"
salva_geotiff_temporaneo(temp_precip_path, GRID_PRECIP, common_extent)

# 4. Generazione Raster Temperatura (RBF)
valid_temp_mask = ~np.isnan(temp_vals)
if np.sum(valid_temp_mask) >= 3:
    rbf_temp = Rbf(lons[valid_temp_mask], lats[valid_temp_mask], temp_vals[valid_temp_mask], function='thin_plate', smooth=0.0)
    GRID_TEMP = rbf_temp(GRID_LON, GRID_LAT)
else:
    GRID_TEMP = np.full_like(GRID_LON, np.nan)

temp_temp_path = "data/raster/temp_temp_full.tif"
salva_geotiff_temporaneo(temp_temp_path, GRID_TEMP, common_extent)

# =====================================================================
# 5. RITAGLIO SEQUENZIALE CON LO SHAPEFILE
# =====================================================================
shp_path = "data/boundary/data/boundary/prov_BR.shp"  # Sostituisci con il percorso reale

if os.path.exists(shp_path):
    print("Applicazione ritaglio geometrico con Shapefile...")
    
    # Legge e allinea il CRS dello Shapefile a WGS84 (EPSG:4326)
    gdf = gpd.read_file(shp_path)
    if gdf.crs is None:
        gdf.set_crs("EPSG:32632", inplace=True)
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
        
    shapes = [geom for geom in gdf.geometry]
    
    # --- Ritaglio Precipitazioni ---
    with rasterio.open(temp_precip_path) as src:
        out_image, out_transform = rasterio.mask.mask(src, shapes, crop=True, nodata=np.nan)
        out_meta = src.meta.copy()
        out_meta.update({"height": out_image.shape[1], "width": out_image.shape[2], "transform": out_transform})
        
        clipped_precip_tif = "data/raster/precip_raster.tif"
        with rasterio.open(clipped_precip_tif, "w", **out_meta) as dest:
            dest.write(out_image)
        GRID_PRECIP_CLIPPED = out_image[0]

    # --- Ritaglio Temperatura ---
    with rasterio.open(temp_temp_path) as src:
        out_image, out_transform = rasterio.mask.mask(src, shapes, crop=True, nodata=np.nan)
        out_meta = src.meta.copy()
        out_meta.update({"height": out_image.shape[1], "width": out_image.shape[2], "transform": out_transform})
        
        clipped_temp_tif = "data/raster/temp_raster.tif"
        with rasterio.open(clipped_temp_tif, "w", **out_meta) as dest:
            dest.write(out_image)
        GRID_TEMP_CLIPPED = out_image[0]
        
    # Pulizia file temporanei intermedi
    for p in [temp_precip_path, temp_temp_path]:
        if os.path.exists(p):
            os.remove(p)
            
    print("Ritaglio GeoTIFF completato con successo.")
else:
    print("Attenzione: Shapefile non trovato. Vengono mantenuti i raster interi.")
    # Fallback se manca lo shapefile
    os.rename(temp_precip_path, "data/raster/precip_raster.tif")
    os.rename(temp_temp_path, "data/raster/temp_raster.tif")
    GRID_PRECIP_CLIPPED = GRID_PRECIP
    GRID_TEMP_CLIPPED = GRID_TEMP

# 6. Esportazione delle immagini PNG finali per la visualizzazione Web
# PNG Precipitazioni
fig, ax = plt.subplots(figsize=(6, 6), frameon=False)
ax.set_axis_off()
ax.imshow(GRID_PRECIP_CLIPPED, origin='lower', cmap='Blues', alpha=0.8, vmin=0, vmax=max(5, np.nanmax(precip_vals) if len(precip_vals) > 0 else 5))
plt.savefig("data/raster/precip_raster.png", bbox_inches='tight', pad_inches=0, transparent=True)
plt.close()

# PNG Temperatura
fig, ax = plt.subplots(figsize=(6, 6), frameon=False)
ax.set_axis_off()
ax.imshow(GRID_TEMP_CLIPPED, origin='lower', cmap='nipy_spectral', alpha=0.6, vmin=-5, vmax=45)
plt.savefig("data/raster/temp_raster.png", bbox_inches='tight', pad_inches=0, transparent=True)
plt.close()

# 7. Salvataggio metadati JSON dei confini
bounds = {
    "bounds": [
        [data_lat_min, data_lon_min],
        [data_lat_max, data_lon_max]
    ],
    "generated_at": datetime.now().isoformat(),
    "note": "Raster GeoTIFF e PNG generati e ritagliati sequenzialmente con Shapefile."
}
with open("data/raster/raster_bounds.json", "w") as f:
    json.dump(bounds, f)

print("Elaborazione completata: raster generati, ritagliati in GeoTIFF e convertiti in PNG.")

