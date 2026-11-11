import argparse
import base64
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from urllib.parse import quote

from openpyxl import Workbook

from . import store
from .comparison import predecessor, code_number
from .coes import synchronize
from .excel_base import ingest, read_series, schema
from .parser import SLOTS

ROOT = Path(__file__).resolve().parents[1]
PERU = timezone(timedelta(hours=-5))


def write_atomic(path, content):
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(content, encoding="utf-8")
    os.replace(temp, path)


def acquire(day, include_supplements=False):
    now = datetime.now(PERU).isoformat()
    report = synchronize(day)
    report.update(day=day, checked_at=now, normalized=[], normalization_errors=[])
    with store.connection() as db:
        schema(db)
        for p in report.get("publications", []):
            db.execute("INSERT INTO publication_listings VALUES(?,?,?,?) ON CONFLICT(day,code) DO UPDATE SET metadata=excluded.metadata,checked_at=excluded.checked_at", (day, p["code"], json.dumps(p, ensure_ascii=False), now))
    if report["listing_verified"]:
        original = store.DATA / "listings" / (day + ".bin")
        digest = hashlib.sha256(original.read_bytes()).hexdigest()
        folder = store.DATA / "listados" / day / digest
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, folder / "Reprogramas.xlsx")
        report["listing_file"] = (folder / "Reprogramas.xlsx").relative_to(store.DATA).as_posix()
    for result in report["results"]:
        try:
            parsed = ingest(result["id"])
            result["series_count"] = len(parsed["series"])
            report["normalized"].append(result["id"])
        except ValueError as e:
            report["normalization_errors"].append({"code": result["code"], "message": str(e)})
    report["complete"] = report["listing_verified"] and not report["errors"] and not report["normalization_errors"]
    # Acquisition completeness is separate from missing predecessors in an official listing.
    expected = {"PDO", *report["discovered"]}
    obtained = {r["code"] for r in report["results"]}
    report["missing_downloads"] = sorted(expected - obtained)
    gaps = []
    for code in report["discovered"]:
        before = predecessor(code)
        if before not in expected:
            gaps.append({"code": code, "previous": before})
    report["sequence_gaps"] = gaps
    if include_supplements and report["results"]:
        from .supplements import update
        supplemental = update(day, report["discovered"])
        report["supplemental_files"] = len(supplemental["files"])
        report["supplemental_errors"] = supplemental["errors"]
        report["complete"] = report["complete"] and not supplemental["errors"]
    with store.connection() as db:
        schema(db)
        db.execute("INSERT INTO acquisition_runs(day,checked_at,report) VALUES(?,?,?)", (day, now, json.dumps(report, ensure_ascii=False)))
    return report


def snapshot():
    with store.connection() as db:
        schema(db)
        publications = {(r["day"],r["code"]): json.loads(r["metadata"]) for r in db.execute("SELECT * FROM publication_listings")}
        runs = {}
        for r in db.execute("SELECT * FROM acquisition_runs ORDER BY id"):
            runs[r["day"]] = json.loads(r["report"])
    versions = store.all_versions(family="official")
    versions.sort(key=lambda v: (v["day"], -1 if v["code"] == "PDO" else code_number(v["code"]), v["id"]))
    for v in versions:
        original = store.DATA / "originals" / v["digest"]
        if hashlib.sha256(original.read_bytes()).hexdigest() != v["digest"]:
            raise ValueError(f"El original archivado {v['id']} no coincide con su huella SHA-256.")
        target = store.DATA / "excel" / v["day"] / v["code"] / v["digest"] / v["filename"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(original, target)
        v["file"] = quote(target.relative_to(store.DATA).as_posix())
        v["bytes"] = original.stat().st_size
        v["publication"] = publications.get((v["day"], v["code"]), {})
        v["series"] = read_series(v["id"])
        v["structured"] = bool(v["series"])
        v["series_count"] = len(v["series"])
        v["published_intervals"] = 48 - v["series"][0]["first_interval_index"] if v["series"] else 0
        v["comparison_ready"] = v.pop("ready", False)
        v.pop("asset_count", None)
        v["source"] = v["source"] if v["source"].startswith("https://www.coes.org.pe/") else "Carga local"
        v.pop("error", None)  # The old dashboard's separate technology reader is not this base's status.
        v.pop("warnings", None)
        v["previous"] = None if v["code"] == "PDO" else predecessor(v["code"])
    return {"generated_at": datetime.now(PERU).isoformat(), "times": SLOTS,
            "versions": versions, "runs": list(runs.values())}


def excel_export(data):
    w = Workbook(write_only=True)
    programs = w.create_sheet("Programas")
    programs.append(["fecha", "version", "anterior", "revision_actual", "archivo", "ruta_relativa", "descargado_hora_UTC", "bytes", "sha256", "columnas_normalizadas", "fuente"])
    pubs = w.create_sheet("Publicaciones")
    pubs.append(["fecha", "version", "vigente_desde_hora_Peru", "ultima_modificacion_COES", "motivo"])
    columns = w.create_sheet("Columnas")
    columns.append(["id_archivo", "fecha", "version", "serie_id", "hoja", "columna", "codigo_COES", "nombre_original", "grupo_original", "seccion_original", "rol", "unidad", "resumen_fila_MWh_original"])
    points = w.create_sheet("Datos")
    points.append(["id_archivo", "fecha", "version", "revision_actual", "serie_id", "posicion_horaria", "hora_normalizada", "hora_original", "hoja", "celda_origen", "valor_numerico", "valor_texto", "unidad", "celda_vacia", "publicado_en_emision"])
    runs = w.create_sheet("Consultas")
    runs.append(["fecha", "consultado_hora_Peru", "listado_verificado", "emisiones_detectadas", "descargas_obtenidas", "ejecucion_completa", "errores"])
    for v in data["versions"]:
        programs.append([v["day"],v["code"],v["previous"],v["current"],v["filename"],v["file"],v["saved_at"],v["bytes"],v["digest"],len(v["series"]),v["source"]])
        if v["current"] and v["publication"]:
            p = v["publication"]
            pubs.append([v["day"],v["code"],p["effective_from"],p["modified_at_source"],p["cause"]])
        with store.connection() as db:
            original_times = {(r["series_key"], r["interval_index"]): (r["raw_time"], r["source_row"]) for r in db.execute("SELECT * FROM excel_values WHERE version_id=? ORDER BY series_key,interval_index", (v["id"],))}
        for s in v["series"]:
            columns.append([v["id"],v["day"],v["code"],s["key"],s["sheet"],s["column"],s["source_code"],s["name"],s["group_label"],s["section"],s["role"],s["unit"],s.get("source_summary",s.get("source_energy"))])
            for i in range(48):
                raw_time, source_row = original_times[(s["key"], i)]
                points.append([v["id"],v["day"],v["code"],v["current"],s["key"],i+1,SLOTS[i],raw_time,s["sheet"],s["column"]+str(source_row) if source_row else None,s["values"][i],s["texts"][i],s["unit"],source_row > 0 and s["values"][i] is None and s["texts"][i] is None,source_row > 0])
    for r in data["runs"]:
        runs.append([r["day"],r["checked_at"],r["listing_verified"],len(r["discovered"]),len(r["results"]),r["complete"],json.dumps(r["errors"]+r.get("normalization_errors",[])+r.get("supplemental_errors",[]),ensure_ascii=False)])
    if data.get("supplements"):
        annexes = w.create_sheet("Anexos")
        annexes.append(["fecha", "tipo", "version_fuente", "archivo", "ruta_relativa", "sha256", "consultado_hora_Peru", "leido", "url"])
        tables = {}

        def rows(sheet, day, code, records, source):
            for record in records:
                if sheet not in tables:
                    fields = list(record)
                    table = w.create_sheet(sheet)
                    table.append(["fecha", "version_fuente", "sha256_fuente", *fields])
                    tables[sheet] = (table, fields)
                table, fields = tables[sheet]
                table.append([day, code, source["digest"], *[record.get(k) for k in fields]])

        for day, extra in sorted(data["supplements"].items()):
            for f in extra.get("files", []):
                annexes.append([day, f["kind"], f["code"], f["filename"], f["file"], f["digest"], f.get("checked_at"), f.get("parsed"), f["url"]])
            for kind, bundle in extra.get("daily", {}).items():
                source, records = bundle["source"], bundle["data"]
                if kind == "hydrology":
                    rows("Hidrologia_Embalses", day, source["code"], records["reservoirs"], source)
                    rows("Hidrologia_Centrales", day, source["code"], records["plants"], source)
                    rows("Hidrologia_INKIA", day, source["code"], records.get("inkia_plants", []), source)
                    rows("Hidrologia_Referencias", day, source["code"], records.get("reference_plants", []), source)
                elif kind == "electrical":
                    rows("Analisis_Electrico", day, source["code"], records["loadings"], source)
                else:
                    sheet = {"maintenance": "Intervenciones", "restrictions": "Restricciones", "links": "RPF", "delegations": "RPF"}[kind]
                    rows(sheet, day, source["code"], records, source)
            for code, bundle in extra.get("reserves", {}).items():
                records = ({"URS": u["urs"], "nombre": u["name"], "empresa": u["company"], "hora": SLOTS[i], "UP_MW": u["up"][i], "DOWN_MW": u["down"][i]}
                           for u in bundle["units"] for i in range(48))
                rows("RSF", day, code, records, bundle["source"])
        classification = w.create_sheet("Clasificacion")
        classification.append(["fecha", "version", "serie_id", "nombre_COES", "central", "empresa", "tecnologia", "categoria", "potencia_referencia_MW", "origen_clasificacion", "incluir_total_COES"])
        for v in data["versions"]:
            for s in v["series"]:
                if s["role"] in ("dispatch", "renewables", "cogeneration"):
                    classification.append([v["day"], v["code"], s["key"], s["name"], s["plant"], s["company"], s["technology"], s["category"], s["capacity"], s["classification_basis"], s["generation"]])
    if data.get("catalog"):
        catalog = data["catalog"]
        for sheet, records in [
            ("Catalogo_Matrices", catalog["references"]["plants"]),
            ("Catalogo_Hidrologico", catalog["references"]["hydrology"]),
            ("Catalogo_URS", catalog["references"]["units"]),
            ("Inventario", catalog["inventory"]),
            ("Alertas_Catalogo", catalog["alerts"]),
            ("Historial_Catalogo", catalog["events"]),
        ]:
            table = w.create_sheet(sheet)
            fields = list(dict.fromkeys(k for record in records for k in record))
            table.append(fields or ["Sin registros"])
            for record in records:
                table.append([json.dumps(record.get(k), ensure_ascii=False) if isinstance(record.get(k), (dict, list)) else record.get(k) for k in fields])
    temp = store.DATA / "base_excel.tmp.xlsx"
    w.save(temp)
    os.replace(temp, store.DATA / "base_excel.xlsx")


def export():
    data = snapshot()
    from .dashboard import enrich
    data = enrich(data)
    excel_export(data)
    manifest = {"generated_at": data["generated_at"], "runs": data["runs"], "versions": [{k:v for k,v in r.items() if k != "series"} for r in data["versions"]]}
    manifest["report"] = data["report"]
    manifest["catalog"] = {k: data["catalog"][k] for k in ("revision", "sources", "alerts", "errors")}
    manifest["annexes"] = {day: {"files": x.get("files", []), "errors": x.get("errors", [])} for day, x in data["supplements"].items()}
    write_atomic(store.DATA / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    template = (Path(__file__).parent / "templates" / "base.html").read_text(encoding="utf-8")
    embedded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    assets=Path(__file__).parent/'assets'
    replacements={"__CCO_DATA__":embedded,"__CCO_CSS__":(assets/'dashboard.css').read_text(encoding='utf-8'),
                  "__CCO_JS__":(assets/'dashboard.js').read_text(encoding='utf-8').replace('</script','<\\/script'),
                  "__CHART_JS__":(assets/'chart.umd.min.js').read_text(encoding='utf-8').replace('</script','<\\/script'),
                  "__KALLPA_LOGO__":base64.b64encode((assets/'kallpa-icon.png').read_bytes()).decode('ascii')}
    for placeholder,content in replacements.items():template=template.replace(placeholder,content)
    write_atomic(store.DATA / "index.html", template)
    return data


def parse_days(args, today):
    if args.fecha and (args.desde or args.hasta):
        raise ValueError("Usa --fecha o un rango --desde/--hasta.")
    if args.fecha:
        days = sorted({date.fromisoformat(d) for d in args.fecha})
    elif args.desde or args.hasta:
        start, end = date.fromisoformat(args.desde or args.hasta), date.fromisoformat(args.hasta or today.isoformat())
        if end < start or (end-start).days > 365:
            raise ValueError("El rango debe ser creciente y de un máximo de 366 días.")
        days = [start+timedelta(days=i) for i in range((end-start).days+1)]
    else:
        days = [today]
    if any(d > today for d in days):
        raise ValueError("No se pueden consultar fechas futuras (hora de Perú).")
    return [d.isoformat() for d in days]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Descarga los Excel del COES y actualiza la base Excel, SQLite y HTML sin servidor.")
    parser.add_argument("--fecha", action="append", help="AAAA-MM-DD; se puede repetir. Por defecto: hoy en Perú.")
    parser.add_argument("--desde", help="Primer día de un rango incluido")
    parser.add_argument("--hasta", help="Último día de un rango incluido; por defecto hoy")
    parser.add_argument("--base", type=Path, default=ROOT / "base_coes", help="Carpeta persistente de salida")
    parser.add_argument("--sin-descargar", action="store_true", help="Regenera Excel/HTML usando solo la base archivada")
    parser.add_argument("--solo-despacho", action="store_true", help="Omite la consulta de anexos complementarios")
    parser.add_argument("--no-abrir", action="store_true", help="Genera la página sin abrir el navegador (servidores/ejecución programada)")
    args = parser.parse_args(argv)
    try:
        days = parse_days(args, datetime.now(PERU).date())
    except ValueError as e:
        parser.error(str(e))
    store.DATA = args.base.resolve()
    store.DATA.mkdir(parents=True, exist_ok=True)
    # Avoid concurrent script executions replacing one another's snapshots.
    lock = store.DATA / ".actualizacion.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        print(f"Ya existe una ejecución activa o interrumpida: {lock}. Verifica que terminó antes de retirar ese archivo.", file=sys.stderr)
        return 2
    try:
        with os.fdopen(fd, "w") as f:
            f.write(str(os.getpid()))
        reports = []
        if not args.sin_descargar:
            for day in days:
                print(f"Consultando COES: {day}…", flush=True)
                report = acquire(day, include_supplements=not args.solo_despacho)
                reports.append(report)
                print(f"  Listado {'verificado' if report['listing_verified'] else 'NO verificado'} · {len(report['discovered'])} reprogramas · {len(report['results'])} Excel · {len(report['normalized'])} normalizados", flush=True)
                for e in report["errors"] + report["normalization_errors"]:
                    print(f"  {e['code']}: {e['message']}", file=sys.stderr, flush=True)
                if "supplemental_files" in report:
                    print(f"  {report['supplemental_files']} anexos complementarios archivados",flush=True)
                    for e in report.get("supplemental_errors",[]):
                        print(f"  {e['code']}: {e['message']}",file=sys.stderr,flush=True)
        try:
            data = export()
        except ValueError as error:
            print(f"No se pudo generar la salida: {error}", file=sys.stderr, flush=True)
            return 2
        for error in data["catalog"].get("errors", []):
            print(f"CATÁLOGO: {error}", file=sys.stderr, flush=True)
        print(f"HTML: {store.DATA / 'index.html'}\nExcel: {store.DATA / 'base_excel.xlsx'}\nSQLite: {store.DATA / 'archive.sqlite3'}", flush=True)
        print(f"{len(data['versions'])} originales/revisiones conservados. Usa «Refrescar página» en el HTML para ver la actualización.")
        print(f"Catálogo: {data['catalog']['pending']} avisos para revisar en «Catálogos y alertas».")
        return 2 if any(not r["complete"] for r in reports) or data["catalog"].get("errors") else 0
    finally:
        lock.unlink(missing_ok=True)


def run(argv=None):
    args=list(sys.argv[1:] if argv is None else argv)
    result=main(args)
    html=store.DATA/'index.html'
    if '--no-abrir' not in args and html.is_file():
        import webbrowser
        try:
            opened=webbrowser.open(html.resolve().as_uri())
        except (webbrowser.Error,OSError):opened=False
        if not opened:print(f"No se pudo abrir el navegador automáticamente. Abre este archivo: {html.resolve()}",flush=True)
    return result


if __name__ == "__main__":
    code=run()
    if code:raise SystemExit(code)
