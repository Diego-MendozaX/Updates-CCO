from . import store
from .parser import SLOTS


def code_number(code):
    n = 0
    for c in code:
        n = n * 26 + ord(c) - 64
    return n


def number_code(number):
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def predecessor(code, family="official"):
    if family == "reference":
        if code != "ACTUAL":
            raise ValueError("Selecciona la versión Actual del comparador.")
        return "ANTERIOR"
    if code == "PDO":
        raise ValueError("El PDO es la base del día; selecciona un reprograma para comparar.")
    n = code_number(code)
    return "PDO" if n == 1 else number_code(n - 1)


def compare(day, code, family="official", group="generation", threshold=100.0, start=0, end=48):
    previous = predecessor(code, family)
    old, new = store.latest(day, previous, family), store.latest(day, code, family)
    if not old or not new:
        raise ValueError(f"Falta {previous if not old else code}. La comparación exige el programa inmediatamente anterior; no se saltan versiones.")
    if not old["payload"] or not new["payload"]:
        raise ValueError("Uno de los originales está pendiente de lectura. Revisa su estado en el archivo de programas.")
    a = {x["id"]: x for x in old["payload"]["assets"]}
    b = {x["id"]: x for x in new["payload"]["assets"]}
    assets = []
    for key in sorted(a.keys() | b.keys()):
        asset = b.get(key) or a[key]
        if group == "generation" and asset["category"] == "demanda":
            continue
        if group != "generation" and asset["category"] != group:
            continue
        av = a[key]["values"][start:end] if key in a else [None] * (end-start)
        bv = b[key]["values"][start:end] if key in b else [None] * (end-start)
        delta = [round(y - x, 6) if x is not None and y is not None else None for x, y in zip(av, bv)]
        valid = [(i, d) for i, d in enumerate(delta) if d is not None]
        peak_i, peak = max(valid, key=lambda x: abs(x[1]), default=(0, None))
        energy = round(sum(d for _, d in valid) * 0.5, 3) if len(valid) == end-start else None
        base = av[peak_i]
        pct = round(peak / abs(base) * 100, 2) if peak is not None and base else None
        assets.append({"id": key, "name": asset["name"], "category": asset["category"], "old": av, "new": bv, "delta": delta,
                       "peak": peak, "peak_time": SLOTS[start+peak_i] if valid else None, "percent": pct,
                       "energy": energy, "changed": any(abs(d) > 0.005 for _, d in valid),
                       "alerts": sum(abs(d) >= threshold for _, d in valid),
                       "coverage": len(valid), "status": "comparable" if key in a and key in b else "solo actual" if key in b else "solo anterior"})
    assets.sort(key=lambda x: abs(x["peak"] or 0), reverse=True)
    series = []
    for i, label in enumerate(SLOTS[start:end]):
        complete = bool(assets) and all(x["old"][i] is not None and x["new"][i] is not None for x in assets)
        av = sum(x["old"][i] for x in assets) if complete else None
        bv = sum(x["new"][i] for x in assets) if complete else None
        series.append({"time": label, "old": av, "new": bv, "delta": bv-av if complete else None})
    full = bool(assets) and all(a["energy"] is not None for a in assets)
    return {"day": day, "code": code, "previous": previous, "family": family, "threshold": threshold, "times": SLOTS[start:end],
            "assets": assets, "series": series, "warnings": old["payload"]["warnings"] + new["payload"]["warnings"],
            "metrics": {"peak": assets[0]["peak"] if assets else None, "peak_asset": assets[0]["name"] if assets else None,
                        "energy": sum(a["energy"] for a in assets) if full else None,
                        "changed": sum(a["changed"] for a in assets), "total": len(assets),
                        "alert_assets": sum(a["alerts"] > 0 for a in assets), "alert_periods": sum(a["alerts"] for a in assets),
                        "comparable": sum(a["coverage"] == end-start for a in assets)},
            "source": {"old_id": old["id"], "new_id": new["id"], "old_digest": old["digest"], "new_digest": new["digest"]}}
