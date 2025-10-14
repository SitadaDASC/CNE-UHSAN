# CNE-UHSAN — Auto GeoJSON from Google Sheets

Este repositorio genera y publica automáticamente un **GeoJSON** llamado **`CNE-UHSAN.geojson`** a partir de una hoja de cálculo de Google Sheets publicada como **TSV**.

- **Fuente (TSV):** configurada en el workflow (ver más abajo).
- **Salida:** `docs/CNE-UHSAN.geojson` (sirve directo con GitHub Pages).
- **Frecuencia:** diaria (CRON) y bajo demanda (Run workflow).

## ¿Cómo funciona?
1. Un workflow de GitHub Actions descarga el TSV de Google Sheets.
2. `update_geojson.py` convierte las filas en puntos GeoJSON.
3. Si hay cambios, se hace commit automático al repositorio.
4. GitHub Pages sirve el archivo desde `/docs`.

## Enlaces esperados
Una vez habilites **GitHub Pages** (branch `main`, carpeta `/docs`), podrás consumir el GeoJSON en:
```
https://<TU-USUARIO>.github.io/CNE-UHSAN-auto/CNE-UHSAN.geojson
```

## Coordinadas esperadas
El script detecta automáticamente columnas de coordenadas en cualquiera de estos nombres (no sensibles a mayúsculas):
- Latitud: `lat`, `latitude`, `latitud`, `latitud_decimal`, `y`
- Longitud: `lon`, `lng`, `long`, `longitud`, `x`

Acepta coma decimal (`1,234`) y punto decimal (`1.234`).  
Por defecto asume **WGS84 (EPSG:4326)**. Si tus columnas son coordenadas proyectadas, puedes definir `INPUT_EPSG` (p. ej., `5367` para Lambert Norte CR) y se reproyectarán a 4326.

## Variables de entorno (workflow)
- `SHEET_TSV_URL`: URL pública del TSV de Google Sheets.
- `OUTPUT_PATH`: Ruta de salida (por defecto `docs/CNE-UHSAN.geojson`).
- `INPUT_EPSG` *(opcional)*: EPSG de entrada si no está en WGS84.
- `POINT_LON_FIELD` y `POINT_LAT_FIELD` *(opcionales)*: forzar nombres de columnas.

## Ejecutar localmente
```bash
python -m venv .venv && source .venv/bin/activate  # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
export SHEET_TSV_URL="https://docs.google.com/spreadsheets/d/e/.../pub?gid=0&single=true&output=tsv"
python update_geojson.py
```

---

### Créditos
Hecho con ❤️ para automatizar datos geográficos desde Google Sheets.
