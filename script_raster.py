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
# 5. RITAGLIO SEQUENZIALE CORRETTO CON LO SHAPEFILE
# =====================================================================
shp_path = "data/boundary/prov_BR.shp"

out_transform_precip = None
out_transform_temp = None

if os.path.exists(shp_path):
    print("Applicazione ritaglio geometrico con Shapefile...")
    
    gdf = gpd.read_file(shp_path)
    if gdf.crs is None:
        gdf.set_crs("EPSG:32632", inplace=True)
    
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
        
    shapes = [geom for geom in gdf.geometry]
    
    # --- Ritaglio Precipitazioni ---
    with rasterio.open(temp_precip_path) as src:
        out_image, out_transform_precip = rasterio.mask.mask(src, shapes, crop=True, all_touched=True, nodata=np.nan)
        out_meta = src.meta.copy()
        out_meta.update({
            "height": out_image.shape[1], 
            "width": out_image.shape[2], 
            "transform": out_transform_precip
        })
        
        clipped_precip_tif = "data/raster/precip_raster.tif"
        with rasterio.open(clipped_precip_tif, "w", **out_meta) as dest:
            dest.write(out_image)
        GRID_PRECIP_CLIPPED = out_image[0]

    # --- Ritaglio Temperatura ---
    with rasterio.open(temp_temp_path) as src:
        out_image, out_transform_temp = rasterio.mask.mask(src, shapes, crop=True, all_touched=True, nodata=np.nan)
        out_meta = src.meta.copy()
        out_meta.update({
            "height": out_image.shape[1], 
            "width": out_image.shape[2], 
            "transform": out_transform_temp
        })
        
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
    os.rename(temp_precip_path, "data/raster/precip_raster.tif")
    os.rename(temp_temp_path, "data/raster/temp_raster.tif")
    GRID_PRECIP_CLIPPED = GRID_PRECIP
    GRID_TEMP_CLIPPED = GRID_TEMP
    out_transform_precip = rasterio.transform.from_bounds(common_extent[0], common_extent[2], common_extent[1], common_extent[3], GRID_PRECIP.shape[1], GRID_PRECIP.shape[0])
    out_transform_temp = out_transform_precip

# 6. Esportazione delle immagini PNG finali con corretto extent geografico
h_p, w_p = GRID_PRECIP_CLIPPED.shape
extent_precip = [
    out_transform_precip[2], 
    out_transform_precip[2] + w_p * out_transform_precip[0], 
    out_transform_precip[5] + h_p * out_transform_precip[4], 
    out_transform_precip[5]
]

h_t, w_t = GRID_TEMP_CLIPPED.shape
extent_temp = [
    out_transform_temp[2], 
    out_transform_temp[2] + w_t * out_transform_temp[0], 
    out_transform_temp[5] + h_t * out_transform_temp[4], 
    out_transform_temp[5]
]

# PNG Precipitazioni
fig, ax = plt.subplots(figsize=(6, 6), frameon=False)
ax.set_axis_off()
ax.imshow(GRID_PRECIP_CLIPPED, extent=extent_precip, origin='upper', cmap='Blues', alpha=0.8, vmin=0, vmax=max(5, np.nanmax(precip_vals) if len(precip_vals) > 0 else 5))
plt.savefig("data/raster/precip_raster.png", bbox_inches='tight', pad_inches=0, transparent=True)
plt.close()

# PNG Temperatura
fig, ax = plt.subplots(figsize=(6, 6), frameon=False)
ax.set_axis_off()
