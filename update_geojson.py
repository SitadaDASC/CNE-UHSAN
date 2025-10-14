#!/usr/bin/env python3
import os
import io
import sys
import json
import math
import pathlib
import requests
import pandas as pd

try:
    import geopandas as gpd
    from shapely.geometry import Point
except Exception as e:
    print("Error importando geopandas/shapely:", e, file=sys.stderr)
    raise

def coerce_float(val):
    if pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if s == "":
        return None
    # Cambiar coma decimal a punto si existe
    s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

def autodetect_columns(columns):
    lat_candidates = ["lat", "latitude", "latitud", "latitud_decimal", "y"]
    lon_candidates = ["lon", "lng", "long", "longitud", "x"]
    lower = {c.lower(): c for c in columns}
    lat = next((lower[c] for c in lower if c in lat_candidates), None)
    lon = next((lower[c] for c in lower if c in lon_candidates), None)
    return lat, lon

def main():
    url = os.getenv("SHEET_TSV_URL", "").strip()
    if not url:
        print("Falta SHEET_TSV_URL", file=sys.stderr)
        sys.exit(1)

    output_path = os.getenv("OUTPUT_PATH", "docs/CNE-UHSAN.geojson")
    input_epsg = os.getenv("INPUT_EPSG", "").strip()
    force_lon = os.getenv("POINT_LON_FIELD", "").strip()
    force_lat = os.getenv("POINT_LAT_FIELD", "").strip()

    print(f"Descargando TSV desde: {url}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    # Leer TSV a DataFrame
    df = pd.read_csv(io.StringIO(r.text), sep="\t")

    # Detectar columnas de coordenadas
    if force_lat and force_lon and force_lat in df.columns and force_lon in df.columns:
        lat_col, lon_col = force_lat, force_lon
    else:
        lat_col, lon_col = autodetect_columns(df.columns)

    if not lat_col or not lon_col:
        print("No se detectaron columnas de lat/lon. Usa POINT_LAT_FIELD y POINT_LON_FIELD.", file=sys.stderr)
        print(f"Columnas disponibles: {list(df.columns)}", file=sys.stderr)
        sys.exit(2)

    # Coaccionar a float
    df["_lat"] = df[lat_col].apply(coerce_float)
    df["_lon"] = df[lon_col].apply(coerce_float)
    df = df.dropna(subset=["_lat", "_lon"])

    if df.empty:
        print("No hay filas válidas con coordenadas.", file=sys.stderr)
        sys.exit(3)

    # Construir GeoDataFrame
    gdf = gpd.GeoDataFrame(
        df.drop(columns=[c for c in ["_lat", "_lon"] if c in df.columns], errors="ignore"),
        geometry=[Point(xy) for xy in zip(df["_lon"], df["_lat"])],
        crs=f"EPSG:{input_epsg}" if input_epsg else "EPSG:4326"
    )

    # Reproyectar a WGS84 si es necesario
    if gdf.crs and str(gdf.crs).upper() not in ("EPSG:4326", "WGS 84"):
        print(f"Reproyectando de {gdf.crs} a EPSG:4326")
        gdf = gdf.to_crs(epsg=4326)

    # Asegurar carpeta
    out_path = pathlib.Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Guardar GeoJSON (FeatureCollection)
    gdf.to_file(out_path, driver="GeoJSON")
    print(f"Guardado GeoJSON en: {out_path.resolve()} (features={len(gdf)})")

if __name__ == "__main__":
    main()
