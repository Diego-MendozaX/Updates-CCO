from datetime import date, datetime
from pathlib import Path
import re
import threading
from zoneinfo import ZoneInfo

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import store
from .comparison import code_number, compare, predecessor
from .coes import synchronize, LIMIT
from .parser import read_workbook

app = FastAPI(title="CCO · Monitor de reprogramas", version="1.0.0")
sync_lock = threading.Lock()


def valid_day(value):
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise HTTPException(422, "Fecha inválida. Usa AAAA-MM-DD.")


def valid_code(value):
    if not re.fullmatch(r"PDO|[A-Z]{1,2}", value):
        raise HTTPException(422, "Versión inválida: usa PDO, A, B… Z, AA…")
    return value


@app.get("/api/health")
def health():
    return {"status": "ok", "today": datetime.now(ZoneInfo("America/Lima")).date().isoformat()}


@app.get("/api/catalog")
def catalog():
    items = store.all_versions()
    days = sorted({(v["day"], v["family"]) for v in items}, reverse=True)
    return {"today": health()["today"], "days": [{"day": d, "family": f, "count": sum(v["current"] for v in items if v["day"] == d and v["family"] == f)} for d, f in days]}


@app.get("/api/versions")
def versions(day: str, family: str = Query("official", pattern="^(official|reference)$")):
    items = store.all_versions(valid_day(day), family)
    items.sort(key=lambda v: (-1 if v["code"] in ("PDO", "ANTERIOR") else 0 if v["code"] == "ACTUAL" else code_number(v["code"]), -v["id"]))
    for v in items:
        try:
            v["previous"] = predecessor(v["code"], family)
        except ValueError:
            v["previous"] = None
    return items


@app.get("/api/comparison")
def comparison(day: str, code: str, family: str = Query("official", pattern="^(official|reference)$"),
               group: str = Query("generation", pattern="^(generation|termica|hidro|rer|demanda)$"),
               threshold: float = Query(100, gt=0, le=100000), start: int = Query(0, ge=0, le=47), end: int = Query(48, ge=1, le=48)):
    if start >= end:
        raise HTTPException(422, "El final del período debe ser posterior al inicio.")
    if family == "official":
        valid_code(code)
    try:
        return compare(valid_day(day), code, family, group, threshold, start, end)
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.post("/api/sync")
def sync(day: str):
    day = valid_day(day)
    if day > health()["today"]:
        raise HTTPException(422, "Selecciona hoy o una fecha anterior (hora de Perú).")
    if not sync_lock.acquire(blocking=False):
        raise HTTPException(409, "Ya hay una sincronización en curso. Espera a que termine.")
    try:
        return synchronize(day)
    finally:
        sync_lock.release()


@app.post("/api/upload")
def upload(day: str = Form(...), code: str = Form(...), file: UploadFile = File(...)):
    day, code = valid_day(day), valid_code(code.upper())
    filename = Path(file.filename or "programa.xlsx").name
    if Path(filename).suffix.lower() not in (".xlsx", ".xlsm"):
        raise HTTPException(422, "Selecciona un archivo .xlsx o .xlsm.")
    raw = file.file.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise HTTPException(413, "El tamaño máximo por archivo es 35 MB.")
    try:
        payload, error = read_workbook(raw), None
    except Exception as e:
        # Unsupported documents remain downloadable and do not silently enter comparisons.
        payload, error = None, str(e) if isinstance(e, ValueError) else "No se pudo leer el Excel; revisa que no esté dañado o cifrado."
    identifier, created = store.save(day, code, raw, filename, "Carga manual", payload, error)
    return {"id": identifier, "created": created, "ready": payload is not None, "error": error}


@app.get("/api/files/{identifier}")
def original(identifier: int):
    try:
        item = store.get_version(identifier)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return FileResponse(store.DATA / "originals" / item["digest"], filename=item["filename"], media_type="application/octet-stream")


dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="dashboard")
