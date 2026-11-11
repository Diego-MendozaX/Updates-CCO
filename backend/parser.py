"""Read cached Excel values, never execute VBA, formulas or external links."""
from datetime import datetime, time, timedelta
from io import BytesIO
import math
import re
import unicodedata
from zipfile import ZipFile, BadZipFile

from openpyxl import load_workbook

CATEGORIES = {"termica": "Térmica", "hidro": "Hidro", "rer": "RER", "demanda": "Demanda"}
SLOTS = [f"{i // 2:02d}:{'30' if i % 2 else '00'}" for i in range(1, 49)]


def normalized(value):
    return " ".join(unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().upper().split())


def category(text):
    text = normalized(text)
    if any(s in text for s in ("DEMANDA", "CARGA POR BARRA")):
        return "demanda"
    if any(s in text for s in ("TERMICA", "TERMOELECT", "TERMIC")):
        return "termica"
    if any(s in text for s in ("RER", "RENOVABLE", "EOLIC", "SOLAR", "NO COES")):
        return "rer"
    if any(s in text for s in ("HIDRO", "HIDRAUL")):
        return "hidro"
    return None


def slot(value):
    if isinstance(value, datetime):
        # Excel's end-of-day value in the supplied comparator is 1900-01-01.
        minutes = value.hour * 60 + value.minute or 1440
    elif isinstance(value, time):
        minutes = value.hour * 60 + value.minute or 1440
    elif isinstance(value, timedelta):
        minutes = round(value.total_seconds() / 60)
    elif isinstance(value, (float, int)) and not isinstance(value, bool) and 0 <= value <= 1:
        minutes = round(value * 1440) or 1440
    elif isinstance(value, str) and re.fullmatch(r"\s*\d{1,2}:\d{2}(:\d{2})?\s*", value):
        h, m, *_ = [int(p) for p in value.strip().split(":")]
        if m > 59:
            return None
        minutes = h * 60 + m or 1440
    else:
        return None
    return minutes // 30 - 1 if minutes in range(30, 1441, 30) else None


def number(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, str):
        try:
            result = float(value.strip().replace(",", "."))
            return result if math.isfinite(result) else None
        except ValueError:
            pass
    return None


def open_excel(raw):
    try:
        with ZipFile(BytesIO(raw)) as z:
            if sum(i.file_size for i in z.infolist()) > 150_000_000:
                raise ValueError("El Excel supera el límite de contenido descomprimido (150 MB).")
        return load_workbook(BytesIO(raw), data_only=True, read_only=True, keep_links=False)
    except (BadZipFile, OSError, KeyError) as e:
        raise ValueError("El archivo no es un Excel .xlsx/.xlsm válido.") from e


def read_workbook(raw, suffix=None):
    workbook = open_excel(raw)
    assets, warnings, used = {}, [], []
    try:
        for sheet in workbook:
            if suffix and not sheet.title.lower().endswith(suffix):
                continue
            if not suffix and sheet.title.lower().endswith(("_old", "_new")):
                continue
            if (sheet.max_row or 0) > 20000 or (sheet.max_column or 0) > 2000:
                warnings.append(f"Hoja {sheet.title}: excede los límites de lectura.")
                continue
            rows = list(sheet.values)
            context = category(sheet.title)
            parsed = []
            # YUPANA: ETAPA / named assets in columns / 48 period-end rows.
            for ri, row in enumerate(rows[:35]):
                if not row or normalized(row[0]) not in ("ETAPA", "HORA", "HORAS", "PERIODO", "INTERVALO"):
                    continue
                times = [(slot(r[0]), r) for r in rows[ri + 1:] if r and slot(r[0]) is not None]
                if len(times) != 48 or {t for t, _ in times} != set(range(48)):
                    continue
                if not context:
                    warnings.append(f"Hoja {sheet.title}: categoría no identificada.")
                    break
                for ci in range(1, len(row)):
                    name = str(row[ci] or "").strip()
                    if not name or "TOTAL" in normalized(name):
                        continue
                    values = [None] * 48
                    for t, r in times:
                        values[t] = number(r[ci]) if ci < len(r) else None
                    parsed.append((context, name, values))
                break
            # COES tables: 48 period-end columns, named assets in rows.
            if not parsed:
                for ri, row in enumerate(rows[:60]):
                    times = [(ci, slot(c)) for ci, c in enumerate(row) if slot(c) is not None]
                    if len(times) != 48 or [t for _, t in times] != list(range(48)):
                        continue
                    first = times[0][0]
                    group = context or category(" ".join(str(c or "") for r in rows[:ri] for c in r[:first]))
                    for r in rows[ri + 1:]:
                        label = " ".join(str(c).strip() for c in r[:first] if c is not None and str(c).strip())
                        if not label:
                            continue
                        label_norm = normalized(label)
                        vals = [number(r[ci]) if ci < len(r) else None for ci, _ in times]
                        new_group = category(label)
                        if new_group and not any(v is not None for v in vals):
                            group = new_group
                            continue
                        if "TOTAL" in label_norm or not group or not any(v is not None for v in vals):
                            continue
                        parsed.append((group, label, vals))
                    break
            if parsed:
                used.append(sheet.title)
            for group, name, values in parsed:
                if not any(v is not None for v in values):
                    continue
                key = group + ":" + normalized(name)
                if key in assets:
                    raise ValueError(f"Serie duplicada: {name}. Se requiere revisar la estructura para evitar sumar dos veces.")
                if any(v is None for v in values):
                    warnings.append(f"{name}: contiene celdas sin valor numérico; no se consideran cero.")
                assets[key] = {"id": key, "name": name, "category": group, "values": values}
    finally:
        workbook.close()
    if not assets:
        raise ValueError("No se identificaron series de 48 intervalos de 30 minutos. Se admiten hojas Térmica, Hidro, RER y Demanda con ETAPA/HORA, o tablas con 48 horas en columnas. El formato de este archivo necesita un adaptador; el original se conserva.")
    return {"assets": list(assets.values()), "warnings": warnings, "sheets": used, "times": SLOTS}
