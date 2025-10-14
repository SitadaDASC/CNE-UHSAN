#!/usr/bin/env python3
import os, io, json, pathlib, requests, pandas as pd

def coerce_float(v):
    if pd.isna(v): return None
    s = str(v).strip().replace(",", ".")
    try: return float(s)
    except: return None

def autodetect(columns):
    lat_cand = {"lat","latitude","latitud","latitud_decimal","y"}
    lon_cand = {"lon","lng","long","longitud","x"}
    lower = {c.lower(): c for c in columns}
    lat = next((lower[c] for c in lower if c in lat_cand), None)
    lon = next((lower[c] for c in lower if c in lon_cand), None)
    return lat, lon

def main():
    url = os.getenv("SHEET_TSV_URL","").strip()
    out = os.getenv("OUTPUT_PATH","docs/CNE-UHSAN.geojson")
    force_lon = os.getenv("POINT_LON_FIELD","").strip()
    force_lat = os.getenv("POINT_LAT_FIELD","").strip()

    if not url:
        raise SystemExit("Falta SHEET_TSV_URL")

    r = requests.get(url, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), sep="\t")

    if force_lat and force_lon and force_lat in df.columns and force_lon in df.columns:
        lat_col, lon_col = force_lat, force_lon
    else:
        lat_col, lon_col = autodetect(df.columns)

    if not lat_col or not lon_col:
        raise SystemExit(f"No encuentro columnas lat/lon. Columnas: {list(df.columns)}")

    df["_lat"] = df[lat_col].apply(coerce_float)
    df["_lon"] = df[lon_col].apply(coerce_float)
    df = df.dropna(subset=["_lat","_lon"])

    features = []
    for _, row in df.iterrows():
        props = {k: (None if pd.isna(v) else v) for k,v in row.items()
                 if k not in ["_lat","_lon"]}
        feat = {
            "type": "Feature",
            "geometry": {"type":"Point","coordinates":[row["_lon"], row["_lat"]]},
            "properties": props
        }
        features.append(feat)

    geojson = {"type":"FeatureCollection","name":"CNE-UHSAN","features":features}
    p = pathlib.Path(out); p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)
    print(f"OK -> {p} (features={len(features)})")

if __name__ == "__main__":
    main()

