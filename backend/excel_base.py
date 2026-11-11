"""Normalize the verified COES annex layout without inventing zeros or technology."""
from datetime import datetime, date, time
from io import BytesIO
import json
from openpyxl.utils import get_column_letter

from .parser import open_excel, normalized, number, slot, SLOTS
from . import store


def extract(raw, requested_day):
    workbook = open_excel(raw)
    result, warnings = [], []
    try:
        for sheet in workbook:
            if (sheet.max_row or 0) > 20000 or (sheet.max_column or 0) > 2000:
                raise ValueError("La hoja supera los límites de lectura de la base.")
            rows = list(sheet.values)
            for ri, row in enumerate(rows[:30]):
                time_columns = [ci for ci, value in enumerate(row) if normalized(value) == "DIA HORA"]
                if not time_columns:
                    continue
                ti = time_columns[0]
                # Reprograms are truncated to their publication window (e.g. G starts 21:00).
                periods, indexes, source_rows, raw_times = [], [], [0]*48, [""]*48
                energy_row = None
                last_2359 = False
                for rindex in range(ri+1, len(rows)):
                    r = rows[rindex]
                    label = r[ti] if ti < len(r) else None
                    if normalized(label) == "MWH":
                        energy_row = r
                        break
                    if label is None:
                        continue
                    last_2359 = str(label).strip() in ("23:59", "23:59:00")
                    idx = 47 if last_2359 else slot(label)
                    if idx is None:
                        raise ValueError("Se encontró una hora no reconocida antes del resumen MWh.")
                    periods.append(r)
                    indexes.append(idx)
                    raw_times[idx] = str(label)
                    source_rows[idx] = rindex+1
                if not indexes or indexes != list(range(indexes[0],48)):
                    raise ValueError("Las horas publicadas no forman una secuencia continua hasta el cierre del día.")
                # Verify the explicit operation date, not the remote filename alone.
                source_date = rows[2][ti] if len(rows) > 2 and len(rows[2]) > ti else None
                if isinstance(source_date, datetime):
                    actual_date = source_date.date()
                elif isinstance(source_date, date):
                    actual_date = source_date
                else:
                    try:
                        actual_date = datetime.strptime(str(source_date).strip(), "%d/%m/%Y").date()
                    except ValueError as e:
                        raise ValueError("No se encontró una fecha de operación verificable en el anexo.") from e
                if actual_date.isoformat() != requested_day:
                    raise ValueError(f"El Excel corresponde a {actual_date}, no a {requested_day}.")
                if last_2359:
                    warnings.append("El COES rotula el último bloque como 23:59; se conserva hora_original y se normaliza fin_intervalo a 24:00 para la media hora final.")
                pre = rows[ri-3] if ri >= 3 else []
                groups = rows[ri-2] if ri >= 2 else []
                codes = rows[ri-1] if ri >= 1 else []
                boundary = next((ci for ci, c in enumerate(row) if normalized(c) == "TOTAL COGENERACION"), None)
                section, group = "Despacho y variables del sistema", ""
                seen = set()
                for ci in range(ti+1, len(row)):
                    if ci < len(pre) and pre[ci] is not None:
                        p = normalized(pre[ci])
                        if any(s in p for s in ("RENOVABLES", "COGENERACION", "NO INTEGRANTES")):
                            section = str(pre[ci]).strip()
                    if ci < len(groups) and groups[ci] is not None:
                        group = str(groups[ci]).strip()
                    name = str(row[ci] or "").strip()
                    if not name:
                        continue
                    n = normalized(name)
                    code = str(codes[ci]).strip() if ci < len(codes) and codes[ci] is not None else ""
                    role, unit = "other", None
                    if boundary is not None and ci < boundary:
                        role, unit = "dispatch", "MW"
                    elif "NO INTEGRANTES" in normalized(section):
                        role, unit = "non_members", "MW"
                    elif "COGENERACION" in normalized(section):
                        role, unit = "cogeneration", "MW"
                    elif "RENOVABLES" in normalized(section):
                        role, unit = "renewables", "MW"
                    elif "US$/MWH" in n:
                        role, unit = "marginal_cost", "USD/MWh"
                    elif n == "NIVEL DE DEMANDA":
                        role, unit = "demand_level", None
                    elif n == "NIVEL TABLACHACA":
                        role, unit = "reservoir_level", None
                    elif n == "DEMANDA COES":
                        role, unit = "demand_total", "MW"
                    elif n == "DEMANDA YUPANA":
                        role, unit = "model_demand", "MW"
                    elif n.startswith("DEMANDA "):
                        role, unit = "demand_area", "MW"
                    elif n == "TOTAL GENERACION COES":
                        role, unit = "generation_total", "MW"
                    elif n.startswith("TOTAL "):
                        role, unit = "other_total", "MW"
                    elif n.startswith("FLUJO "):
                        role, unit = "flow", "MW"
                    elif n.startswith("RESERVA ") or n in ("OFERTA", "PERDIDAS YUPANA", "DEFICIT YUPANA"):
                        role, unit = "system_power", "MW"
                    key = role + ":" + code + ":" + n
                    if key in seen:
                        raise ValueError(f"Columna duplicada en el anexo: {name}.")
                    seen.add(key)
                    values, texts = [None]*48, [None]*48
                    for idx, r in zip(indexes, periods):
                        value = r[ci] if ci < len(r) else None
                        values[idx] = number(value)
                        texts[idx] = str(value) if value is not None and number(value) is None else None
                    source_summary = None
                    if energy_row is not None:
                        source_summary = number(energy_row[ci]) if ci < len(energy_row) else None
                    result.append({"key": key, "sheet": sheet.title, "column": get_column_letter(ci+1), "name": name,
                                   "source_code": code, "group_label": group, "section": section, "role": role,
                                   "unit": unit, "values": values, "texts": texts, "raw_times": raw_times,
                                   "source_rows": source_rows, "first_interval_index": indexes[0],
                                   "first_data_row": source_rows[indexes[0]], "source_summary": source_summary})
                break
    finally:
        workbook.close()
    if not result:
        raise ValueError("El Excel se descargó pero no coincide con el anexo COES validado (columna Día Hora). Se conserva el original.")
    return {"day": requested_day, "times": SLOTS, "series": result, "warnings": warnings}


def schema(db):
    db.executescript("""
      CREATE TABLE IF NOT EXISTS excel_series (
        version_id INTEGER NOT NULL, series_key TEXT NOT NULL, metadata TEXT NOT NULL,
        PRIMARY KEY(version_id,series_key));
      CREATE TABLE IF NOT EXISTS excel_values (
        version_id INTEGER NOT NULL, series_key TEXT NOT NULL, interval_index INTEGER NOT NULL,
        normalized_time TEXT NOT NULL, raw_time TEXT NOT NULL, source_row INTEGER NOT NULL,
        numeric_value REAL, text_value TEXT, present_in_source INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY(version_id,series_key,interval_index));
      CREATE TABLE IF NOT EXISTS acquisition_runs (
        id INTEGER PRIMARY KEY, day TEXT NOT NULL, checked_at TEXT NOT NULL, report TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS publication_listings (
        day TEXT NOT NULL, code TEXT NOT NULL, metadata TEXT NOT NULL, checked_at TEXT NOT NULL,
        PRIMARY KEY(day,code));
    """)
    names = {r[1] for r in db.execute("PRAGMA table_info(excel_values)")}
    if "end_time" in names and "normalized_time" not in names:
        db.execute("ALTER TABLE excel_values RENAME COLUMN end_time TO normalized_time")
    if "present_in_source" not in names:
        db.execute("ALTER TABLE excel_values ADD COLUMN present_in_source INTEGER NOT NULL DEFAULT 1")


def ingest(identifier):
    version = store.get_version(identifier)
    raw = (store.DATA / "originals" / version["digest"]).read_bytes()
    payload = extract(raw, version["day"])
    with store.connection() as db:
        schema(db)
        db.execute("DELETE FROM excel_values WHERE version_id=?", (identifier,))
        db.execute("DELETE FROM excel_series WHERE version_id=?", (identifier,))
        for series in payload["series"]:
            meta = {k:v for k,v in series.items() if k not in ("values", "texts", "raw_times", "source_rows")}
            meta["warnings"] = payload["warnings"]
            db.execute("INSERT INTO excel_series VALUES(?,?,?)", (identifier, series["key"], json.dumps(meta, ensure_ascii=False)))
            db.executemany("INSERT INTO excel_values VALUES(?,?,?,?,?,?,?,?,?)", [(identifier, series["key"], i, SLOTS[i], series["raw_times"][i], series["source_rows"][i], series["values"][i], series["texts"][i], int(series["source_rows"][i] > 0)) for i in range(48)])
    return payload


def read_series(identifier):
    with store.connection() as db:
        schema(db)
        series = db.execute("SELECT * FROM excel_series WHERE version_id=? ORDER BY rowid", (identifier,)).fetchall()
        values = db.execute("SELECT * FROM excel_values WHERE version_id=? ORDER BY series_key,interval_index", (identifier,)).fetchall()
    by_key = {}
    for r in series:
        meta = json.loads(r["metadata"])
        meta.update(values=[None]*48, texts=[None]*48)
        by_key[r["series_key"]] = meta
    for r in values:
        by_key[r["series_key"]]["values"][r["interval_index"]] = r["numeric_value"]
        by_key[r["series_key"]]["texts"][r["interval_index"]] = r["text_value"]
    return list(by_key.values())
