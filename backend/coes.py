from datetime import date
from io import BytesIO
import json
import re
from urllib.parse import urlencode

import httpx

from .parser import open_excel, read_workbook, normalized
from . import store
from .comparison import code_number

BASE = "https://www.coes.org.pe"
MONTHS = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
LIMIT = 35_000_000


def download_url(day, code):
    d = date.fromisoformat(day)
    directory = f"Operación/Programa de Operación/{'Programa Diario' if code == 'PDO' else 'Reprograma Diario Operación'}/{d.year}/{d.month:02d}_{MONTHS[d.month-1]}/Día {d.day:02d}/"
    filename = f"Anexo1_Despacho_{d:%Y%m%d}.xlsx" if code == "PDO" else f"Reprog_{d:%d%m}{code}.xlsx"
    path = directory + ("" if code == "PDO" else f"Reprog {d:%d%m}{code}/") + filename
    return BASE + "/portal/browser/download?" + urlencode({"url": path}), filename


def fetch(url):
    # Environment proxy and CA trust remain enabled. Do not follow redirects
    # to arbitrary destinations when handling download responses.
    with httpx.Client(timeout=httpx.Timeout(45, connect=15), follow_redirects=False) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > LIMIT:
                    raise ValueError("El archivo del COES supera 35 MB.")
                chunks.append(chunk)
            return b"".join(chunks)


def listing_records(raw, day):
    """Read the actual COES listing by its named columns, including zero emissions."""
    date.fromisoformat(day)
    if not raw.startswith(b"PK"):
        return None
    workbook = open_excel(raw)
    try:
        for sheet in workbook:
            rows = list(sheet.values)
            for i, row in enumerate(rows[:20]):
                headers = {normalized(c): j for j, c in enumerate(row) if c is not None}
                if "REPROGRAMA" not in headers or "FECHA" not in headers:
                    continue
                result = []
                for cells in rows[i+1:]:
                    if not any(c is not None for c in cells):
                        continue
                    fields = {name: cells[j] if j < len(cells) else None for name, j in headers.items()}
                    code = str(fields.get("REPROGRAMA") or "").strip().upper()
                    if not re.fullmatch(r"[A-Z]{1,2}", code):
                        raise ValueError(f"El listado contiene una emisión no reconocida: {code!r}.")
                    source_day = fields.get("FECHA")
                    from datetime import datetime
                    if isinstance(source_day, (date, datetime)):
                        parsed_day = source_day.date() if isinstance(source_day, datetime) else source_day
                    else:
                        try:
                            parsed_day = datetime.strptime(str(source_day).strip(), "%d/%m/%Y").date()
                        except ValueError as e:
                            raise ValueError("El listado contiene una fecha no reconocida.") from e
                    if parsed_day.isoformat() != day:
                        raise ValueError("La fecha del listado no coincide con la fecha solicitada.")
                    result.append({"code": code, "day": day, "cause": str(fields.get("CAUSA REPROGRAMA") or ""),
                                   "effective_from": str(fields.get("BLOQUE HORARIO") or ""),
                                   "modified_at_source": str(fields.get("ULTIMA MODIFICACION") or ""),
                                   "type": str(fields.get("TIPO") or "")})
                if len({r["code"] for r in result}) != len(result):
                    raise ValueError("Hay letras repetidas en el listado oficial; revisa el original.")
                return sorted(result, key=lambda x: code_number(x["code"]))
        return None
    finally:
        workbook.close()


def discover(raw, day):
    records = listing_records(raw, day)
    if records is not None:
        return [r["code"] for r in records]
    d = date.fromisoformat(day)
    if raw.startswith(b"PK"):
        w = open_excel(raw)
        try:
            text = "\n".join(" ".join(str(c or "") for c in row) for s in w for row in s.values)
        finally:
            w.close()
    else:
        text = raw.decode("utf-8-sig", errors="replace")
        try:
            text = json.dumps(json.loads(text), ensure_ascii=False)
        except ValueError:
            pass
    codes = set(re.findall(rf"(?<![A-Z0-9]){d:%d%m}[_\s-]*([A-Z]{{1,2}})\b", text, re.I))
    codes.update(re.findall(r"\b(?:REPROG(?:RAMA)?)[\s_:-]+([A-Z]{1,2})\b", text, re.I))
    codes = {c.upper() for c in codes if c.upper() not in {"DE", "EN", "EL", "DI"}}
    # Some listing workbooks contain a column with the letter only.
    if not codes and raw.startswith(b"PK"):
        codes = set(re.findall(r"(?:^|\n)\s*([A-Z]{1,2})\s*(?:\n|$)", text))
    if not codes:
        raise ValueError("No se pudieron identificar las letras en el listado del COES; no se presume que el día esté completo.")
    return sorted(codes, key=code_number)


def synchronize(day):
    codes, errors = [], []
    listing = BASE + "/Portal/Operacion/ProgOperacion/DescargarListadoDeReProgramasPorFecha?fecha=" + day.replace("-", "")
    verified = False
    publications = []
    try:
        raw = fetch(listing)
        publications = listing_records(raw, day) or []
        codes = discover(raw, day)
        verified = True
        (store.DATA / "listings").mkdir(parents=True, exist_ok=True)
        (store.DATA / "listings" / (day + ".bin")).write_bytes(raw)
    except (httpx.HTTPError, ValueError) as e:
        errors.append({"code": "LISTADO", "message": remote_error(e)})
        if day == "2026-11-03":
            codes = list("ABCDE")  # Explicitly supplied links, not assumed discovery.
    results = []
    for code in ["PDO"] + codes:
        url, filename = download_url(day, code)
        try:
            raw = fetch(url)
            # A successful HTTP response may contain an error page, not an Excel.
            check = open_excel(raw)
            check.close()
            try:
                payload, error = read_workbook(raw), None
            except Exception as e:
                payload = None
                error = str(e) if isinstance(e, ValueError) else "No se pudo leer el Excel del COES. El original se conserva para adaptar el lector."
            identifier, created = store.save(day, code, raw, filename, url, payload, error)
            results.append({"id": identifier, "code": code, "created": created, "ready": payload is not None})
        except (httpx.HTTPError, ValueError) as e:
            errors.append({"code": code, "message": remote_error(e)})
    return {"results": results, "errors": errors, "listing_verified": verified, "publications": publications,
            "discovered": codes, "message": "Listado consultado al COES." if verified else "Listado no verificado; no se puede confirmar que la fecha esté completa." + (" Se intentan los enlaces A–E del 03/11/2026 compartidos por el usuario; pueden existir otros." if day == "2026-11-03" else "")}


def remote_error(error):
    if isinstance(error, httpx.HTTPStatusError):
        return f"COES/proxy respondió HTTP {error.response.status_code}. Revisa el acceso a www.coes.org.pe y la disponibilidad del archivo."
    if isinstance(error, httpx.ProxyError):
        return "El proxy bloqueó la conexión al COES. Habilita www.coes.org.pe en los ajustes de red del entorno."
    if isinstance(error, httpx.HTTPError):
        return "No se pudo conectar al COES dentro del tiempo permitido. Los originales archivados siguen disponibles."
    return str(error)
