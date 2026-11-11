"""Official COES annex discovery and bounded, read-only extraction."""
from datetime import datetime
from datetime import timezone, timedelta
from html.parser import HTMLParser
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlencode, urlparse, parse_qs
from zipfile import ZipFile

import httpx

from . import store
from .coes import BASE, download_url, fetch, remote_error
from .parser import open_excel, normalized, number, slot


class FileList(HTMLParser):
    def __init__(self, directory):
        super().__init__(); self.directory = directory; self.files = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "input" and a.get("value", "").startswith(self.directory):
            self.files.append(a["value"])


def directory_files(directory, base):
    with httpx.Client(timeout=httpx.Timeout(40, connect=15)) as client:
        response = client.post(BASE + "/Portal/browser/vistadatos", data={"url": directory, "baseDirectory": base,
                               "indicador": "S", "initialLink": "COES", "orderFolder": "D"})
        response.raise_for_status()
        if len(response.content) > 5_000_000:
            raise ValueError("El listado de anexos supera el tamaño permitido.")
    parser = FileList(directory); parser.feed(response.text)
    return list(dict.fromkeys(parser.files))


def safe_zip(raw):
    z = ZipFile(BytesIO(raw))
    if sum(i.file_size for i in z.infolist()) > 150_000_000 or len(z.infolist()) > 500:
        z.close(); raise ValueError("El ZIP supera los límites de lectura.")
    return z


def text(value):
    if value is None: return ""
    if isinstance(value, datetime): return value.isoformat(sep=" ", timespec="minutes")
    return str(value).strip()


def parse_hydrology(raw):
    w = open_excel(raw); reservoirs, plants = [], []
    try:
        for s in w:
            if normalized(s.title) not in ("EMBALSES", "GENERADORES"): continue
            for r in list(s.values)[9:]:
                if not r or not text(r[0]) or number(r[1] if len(r)>1 else None) is None: continue
                if normalized(s.title) == "EMBALSES":
                    reservoirs.append({"name":text(r[0]),"initial":number(r[1]),"final":number(r[2]),
                                       "natural":number(r[4]),"inflow":number(r[5]),"diverted":number(r[6]),"irrigation":number(r[7]),"spilled":number(r[8])})
                else:
                    plants.append({"name":text(r[0]),"natural":number(r[1]),"inflow":number(r[2]),"turbined":number(r[3]),"spilled":number(r[4])})
    finally: w.close()
    if not reservoirs or not plants: raise ValueError("El anexo de hidrología no contiene las tablas esperadas.")
    return {"reservoirs":reservoirs,"plants":plants,"frequency":"daily_endpoints"}


def parse_rsf(raw, day):
    w = open_excel(raw); units = {}; totals = {"up":[None]*48,"down":[None]*48}
    try:
        for s in w:
            title = normalized(s.title)
            direction = "down" if "DOWN" in title else "up" if "UP" in title else None
            if direction is None: continue
            if day not in s.title: raise ValueError("La fecha de la reserva no coincide con la solicitada.")
            rows = list(s.values); headers = rows[2]
            urss = [(i,text(c)) for i,c in enumerate(headers) if text(c).startswith("URS-")]
            for i,urs in urss:
                units.setdefault(urs,{"urs":urs,"up":[None]*48,"down":[None]*48})
            for r in rows[3:]:
                if not r: continue
                idx = 47 if text(r[0]) in ("23:59","23:59:00") else slot(r[0])
                if idx is None: continue
                for ci,urs in urss:
                    value = number(r[ci]) if ci<len(r) else None
                    units[urs][direction][idx] = abs(value) if value is not None else None
                # COES puts the authoritative system total immediately after the URS columns.
                last = max((i for i,_ in urss),default=0)
                extra = [number(v) for v in r[last+1:] if number(v) is not None]
                if extra: totals[direction][idx] = extra[0]
    finally: w.close()
    if not units: raise ValueError("No se identificaron columnas URS en el anexo de reserva.")
    return {"units":list(units.values()),"totals":totals}


def parse_restrictions(raw):
    w=open_excel(raw); result=[]
    try:
        for s in w:
            rows=list(s.values)
            header=next((i for i,r in enumerate(rows) if any(normalized(c)=="DESCRIPCION" for c in r) and any(normalized(c)=="EMPRESA" for c in r)),None)
            if header is None:continue
            names={normalized(c):i for i,c in enumerate(rows[header]) if c is not None}
            for r in rows[header+1:]:
                def v(k):return text(r[names[k]]) if k in names and names[k]<len(r) else ""
                if not v("EMPRESA") or not v("DESCRIPCION"):continue
                result.append({"company":v("EMPRESA"),"location":v("UBICACION"),"equipment":v("EQUIPO"),"start":v("INICIO"),"end":v("FINAL"),"description":v("DESCRIPCION"),"day":v("FECHA")})
    finally:w.close()
    return result


def parse_rpf(raw, kind):
    w=open_excel(raw); result=[]
    try:
        for s in w:
            rows=list(s.values)
            for r in rows[11:]:
                if len(r)<11 or number(r[1]) is None:continue
                result.append({"code":text(r[1]),"start_date":text(r[2]),"start":text(r[3]),"end_date":text(r[4]),"end":text(r[5]),
                               "from":text(r[7]),"to":text(r[9]),"percent":number(r[10]),"backup":text(r[11]) if len(r)>11 else "","kind":kind})
    finally:w.close()
    return result


def parse_maintenance(raw):
    with safe_zip(raw) as z:
        name=next((n for n in z.namelist() if n.lower().endswith(('.xlsm','.xlsx','.xls')) and 'agentes' in n.lower()),None)
        if not name:raise ValueError("No se encontró el Excel de intervenciones de agentes.")
        raw_excel=z.read(name)
    result=[]
    if raw_excel.startswith(b'PK'):
        w=open_excel(raw_excel)
        names=w.sheetnames
        get_rows=lambda name:list(w[name].values)
        close=w.close
    else:
        import xlrd
        w=xlrd.open_workbook(file_contents=raw_excel,on_demand=True)
        names=w.sheet_names()
        def get_rows(name):
            sheet=w.sheet_by_name(name)
            if sheet.nrows>30000 or sheet.ncols>100:raise ValueError('El XLS supera los límites de lectura.')
            return [[xlrd.xldate_as_datetime(c.value,w.datemode) if c.ctype==xlrd.XL_CELL_DATE else c.value for c in sheet.row(i)] for i in range(sheet.nrows)]
        close=w.release_resources
    try:
        if "MANTTOS" not in names:raise ValueError("El libro no contiene MANTTOS.")
        rows=get_rows("MANTTOS"); required={text(r[6]) for r in rows[9:] if len(r)>10 and number(r[1]) is not None}
        area={}
        if "EQUIPOS" in names:
            for r in get_rows("EQUIPOS"):
                if len(r)>9 and text(r[1]) in required:area[text(r[1])]=text(r[9])
        for r in rows[9:]:
            if len(r)<14 or number(r[1]) is None:continue
            kind=area.get(text(r[6]),"");mw=number(r[10]);equipment=text(r[5])
            group="Generación" if kind in ("C.H.","C.T.","C.S.","C.E.") or (mw is not None and mw>0) or "CENTRAL" in normalized(equipment) else "Transmisión" if kind in ("S.E.","L.T.","L.") else "Otros"
            result.append({"id":text(r[2]) or "fila-"+str(r[1]),"company":text(r[3]),"location":text(r[4]),"equipment":equipment,"code":text(r[6]),"start":text(r[7]),"end":text(r[8]),"description":text(r[9]),"mw":mw,"availability":text(r[11]),"interruption":text(r[12]),"type":text(r[13]),"category":group+" "+text(r[11]),"equipment_area":kind})
    finally:close()
    return result


def parse_electrical(raw):
    from pypdf import PdfReader
    with safe_zip(raw) as z:
        n=next((n for n in z.namelist() if n.lower().endswith('.pdf') and 'analisis electrico' in normalized(n).lower()),None)
        if not n:raise ValueError("No se encontró el PDF de análisis eléctrico.")
        pdf=z.read(n)
    reader=PdfReader(BytesIO(pdf)); records=[]; sections=[]
    for pi,page in enumerate(reader.pages):
        content=page.extract_text() or ""
        if "Contingencia:" in content:
            sections.append({"page":pi+1,"text":content[:16000]})
        for line in content.splitlines():
            clean=" ".join(line.split())
            if not re.match(r'^L\s*-\s*\d{4}',clean):continue
            # Only explicit table rows. Narrative percentages are not converted into simulated cases.
            match=re.match(r'^(L\s*-\s*\d{4}(?:\s*/\s*L\s*-\s*\d{4})*(?:\s*\([^)]*\))?)\s+(\d{1,3}(?:[.,]\d+)?\s*%(?:(?:\s*/\s*|\s+)\d{1,3}(?:[.,]\d+)?\s*%)*)\s*$',clean)
            if not match:continue
            values=[float(x.replace(',','.')) for x in re.findall(r'(\d{1,3}(?:[.,]\d+)?)\s*%',match.group(2))]
            records.append({"equipment":match.group(1),"loading":max(values),"reported":match.group(2),"page":pi+1,"context":"Fila explícita del anexo PDI; no representa una simulación nueva"})
    return {"loadings":records,"sections":sections,"pdf":pdf,"pdf_name":Path(n).name,"pages":len(reader.pages)}


def update(day, codes):
    pdo_url,_=download_url(day,"PDO");pdo_path=parse_qs(urlparse(pdo_url).query)["url"][0].rsplit('/',1)[0]+'/'
    base="Operación/Programa de Operación/Programa Diario/"
    paths=[("PDO",pdo_path,base)]
    for code in codes:
        u,_=download_url(day,code);folder=parse_qs(urlparse(u).query)["url"][0].rsplit('/',1)[0]+'/'
        paths.append((code,folder,"Operación/Programa de Operación/Reprograma Diario Operación/"))
    maintenance=pdo_path.replace("Programa de Operación/","Programa de Mantenimiento/")
    paths.append(("PDI",maintenance,"Operación/Programa de Mantenimiento/Programa Diario/"))
    folder=store.DATA/'complementos';folder.mkdir(parents=True,exist_ok=True)
    target=folder/(day+'.json')
    result=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {"day":day,"daily":{},"reserves":{},"files":[]}
    result['errors']=[]
    for code,directory,base in paths:
        try:files=directory_files(directory,base)
        except (httpx.HTTPError,ValueError) as e:
            result["errors"].append({"code":code,"message":remote_error(e)});continue
        for path in files:
            filename=path.rsplit('/',1)[-1];n=normalized(filename)
            kind=("hydrology" if n.startswith("ANEXO2_HIDROLOGIA") else "restrictions" if n.startswith("ANEXO5_RESTRICCIONES_OPERATIVAS") else "rsf" if n.startswith("ANEXO6_RESERVA") or n.startswith("RS_REPROG_") else "links" if n.startswith("ANEXO8A_") else "delegations" if n.startswith("ANEXO8B_") else "maintenance" if n.startswith("ANEXO1_INTERVENCIONES") and n.endswith('.ZIP') else "electrical" if n.startswith("ANEXO2_ANALISIS") and n.endswith('.ZIP') else None)
            if not kind:continue
            url=BASE+'/portal/browser/download?'+urlencode({"url":path})
            try:
                raw=fetch(url);digest=hashlib.sha256(raw).hexdigest();folder=store.DATA/'anexos'/day/code/digest;folder.mkdir(parents=True,exist_ok=True)
                (folder/filename).write_bytes(raw)
                source={"kind":kind,"code":code,"filename":filename,"file":(folder/filename).relative_to(store.DATA).as_posix(),"url":url,"digest":digest,"checked_at":datetime.now(timezone(timedelta(hours=-5))).isoformat(),"parsed":False}
                result['files']=[f for f in result['files'] if not (f['kind']==kind and f['code']==code and f['digest']==digest)]
                result['files'].append(source)
                parsed={"hydrology":parse_hydrology,"restrictions":parse_restrictions,"links":lambda b:parse_rpf(b,"Vinculación"),"delegations":lambda b:parse_rpf(b,"Delegación"),"maintenance":parse_maintenance,"electrical":parse_electrical,"rsf":lambda b:parse_rsf(b,day)}[kind](raw)
                if kind=="electrical":
                    name=parsed.pop('pdf_name');pdf=parsed.pop('pdf');(folder/name).write_bytes(pdf);parsed['pdf_file']=(folder/name).relative_to(store.DATA).as_posix()
                source['parsed']=True
                if kind=="rsf":result["reserves"][code]={**parsed,"source":source}
                else:result["daily"][kind]={"data":parsed,"source":source}
            except Exception as e:
                result["errors"].append({"code":code+":"+kind,"message":remote_error(e) if isinstance(e,httpx.HTTPError) else str(e)})
    temp=target.with_suffix('.tmp');temp.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');temp.replace(target)
    return result


def load_all():
    folder=store.DATA/'complementos'
    return {p.stem:json.loads(p.read_text(encoding='utf-8')) for p in folder.glob('*.json')} if folder.exists() else {}
