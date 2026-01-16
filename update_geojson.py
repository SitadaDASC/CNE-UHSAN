#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import io
import json
import pathlib
import re

import requests
import pandas as pd


def norm(s: object) -> str:
    """Normaliza strings para comparar: minúsculas, sin símbolos/espacios."""
    return re.sub(r"\W+", "", str(s).strip().lower())


def coerce_float(v):
    """Convierte a float limpiando comas decimales, espacios y texto."""
    if pd.isna(v):
        return None
    s = str(v).strip()
    s = s.replace("\u00A0", "")          # NBSP
    s = s.replace(" ", "")              # espacios
    s = s.replace(",", ".")             # coma decimal -> punto
    s = re.sub(r"[^0-9.\-]", "", s)     # quita letras/símbolos raros
    try:
        return float(s)
    except:
        return None


def find_col(df: pd.DataFrame, desired: str) -> str | None:
    """
    Busca una columna por:
    - match exacto (con strip)
    - match normalizado (sin símbolos/espacios)
    """
    if not desired:
        return None
    desired = str(desired).strip()
    nd = norm(desired)

    for c in df.columns:
        if str(c).strip() == desired:
            return c

    for c in df.columns:
        if norm(c) == nd:
            return c

    # fallback: empieza con (por ejemplo X -> "X (m)")
    for c in df.columns:
        if norm(c).startswith(nd):
            return c

    return None


def autodetect_xy_or_lonlat(cols):
    """
    Detecta columnas típicas.
    - Primero intenta X/Y (CRTM05 o similares)
    - Luego lon/lat
    """
    # Posibles nombres para X/Y
    x_keys = {
        "x", "este", "easting", "coordx", "coordenadax", "crtm05x", "xcrtm05", "longitudx"
    }
    y_keys = {
        "y", "norte", "northing", "coordy", "coordenaday", "crtm05y", "ycrtm05", "latitudy"
    }

    # Posibles nombres para lon/lat
    lon_keys = {"lon", "lng", "long", "longitud", "longitude"}
    lat_keys = {"lat", "latitude", "latitud", "latituddecimal", "latitud_decimal"}

    norm_map = {norm(c): c for c in cols}

    # 1) X/Y
    x_col = next((norm_map[k] for k in norm_map if k in {norm(k2) for k2 in x_keys}), None)
    y_col = next((norm_map[k] for k in norm_map if k in {norm(k2) for k2 in y_keys}), None)
    if x_col and y_col:
        return x_col, y_col, "xy"

    # 2) lon/lat
    lon_col = next((norm_map[k] for k in norm_map if k in {norm(k2) for k2 in lon_keys}), None)
    lat_col = next((norm_map[k] for k in norm_map if k in {norm(k2) for k2 in lat_keys}), None)
    if lon_col and lat_col:
        return lon_col, lat_col, "lonlat"

    return None, None, None


def read_table_robust(text: str) -> pd.DataFrame:
    """
    Lee contenido de Google Sheets publicado, soportando:
    - TSV (tabs)
    - CSV (comas)
    - separadores mixtos
    Usamos engine='python' para evitar el parser C (que fue el que explotó).
    """
    # sep=None autodetecta delimitador en engine python
    df = pd.read_csv(
        io.StringIO(text),
        dtype=str,
        sep=None,
        engine="python",
        on_bad_lines="skip",
    )
    # limpia nombres de columnas
    df.columns = [str(c).strip() for c in df.columns]
    return df


def main():
    # Mantengo nombres para compatibilidad:
    # - si tu workflow usa SHEET_TSV_URL no se rompe
    # - si cambiás a CSV, podés usar SHEET_CSV_URL
    url = (os.getenv("SHEET_CSV_URL") or os.getenv("SHEET_TSV_URL") or "").strip()
    out = (os.getenv("OUTPUT_PATH") or "docs/CNE-UHSAN.geojson").strip()

    # Campos forzados (si los ponés en env):
    force_lon = (os.getenv("POINT_LON_FIELD") or "").strip()
    force_lat = (os.getenv("POINT_LAT_FIELD") or "").strip()

    # EPSG entrada (si viene en CRTM05 5367)
    input_epsg = (os.getenv("INPUT_EPSG") or "").strip()  # ej: "5367"

    if not url:
        raise SystemExit("Falta SHEET_CSV_URL o SHEET_TSV_URL")

    r = requests.get(url, timeout=60)
    r.raise_for_status()

    df = read_table_robust(r.text)
    print("Columnas leídas:", list(df.columns))

    # 1) Si el usuario fuerza campos, buscarlos de forma robusta
    lat_col = find_col(df, force_lat) if force_lat else None
    lon_col = find_col(df, force_lon) if force_lon else None

    # 2) Si no están forzados o no se encontraron, autodetectar
    mode = None
    if not lat_col or not lon_col:
        a, b, mode = autodetect_xy_or_lonlat(df.columns)
        if mode == "xy":
            lon_col, lat_col = a, b   # OJO: aquí a=x y b=y, pero en coords es (x,y)
        elif mode == "lonlat":
            lon_col, lat_col = a, b
        else:
            lon_col = lon_col or None
            lat_col = lat_col or None

    if not lon_col or not lat_col:
        raise SystemExit(f"No encuentro columnas coordenadas. Columnas: {list(df.columns)}")

    # Convertir columnas a float
    df["_a"] = df[lon_col].apply(coerce_float)  # puede ser X o Lon
    df["_b"] = df[lat_col].apply(coerce_float)  # puede ser Y o Lat
    df = df.dropna(subset=["_a", "_b"])
    if df.empty:
        raise SystemExit("No hay filas válidas con coordenadas luego de limpiar.")

    # Preparar coords de entrada (x,y)
    coords = list(zip(df["_a"], df["_b"]))

    # Reproyección si INPUT_EPSG está definido y no es 4326
    # Si tus columnas eran X/Y (CRTM05 5367), esto es obligatorio.
    # Si tus columnas ya son lon/lat en grados, poné INPUT_EPSG=4326 o vacío.
    if input_epsg and input_epsg != "4326":
        from pyproj import Transformer
        tr = Transformer.from_crs(f"EPSG:{input_epsg}", "EPSG:4326", always_xy=True)
        coords = [tr.transform(x, y) for (x, y) in coords]  # -> (lon, lat)

    # Construir GeoJSON
    features = []
    for (_, row), (lon4326, lat4326) in zip(df.iterrows(), coords):
        props = {
            k: (None if pd.isna(v) else v)
            for k, v in row.items()
            if k not in ["_a", "_b"]
        }
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon4326, lat4326]},
                "properties": props,
            }
        )

    geojson = {"type": "FeatureCollection", "name": "CNE-UHSAN", "features": features}

    p = pathlib.Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)

    print(f"OK -> {p} (features={len(features)})")


if __name__ == "__main__":
    main()


