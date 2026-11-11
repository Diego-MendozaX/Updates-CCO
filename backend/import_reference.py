"""Explicit import of the user's comparator; source stays local and untracked."""
import argparse
from pathlib import Path

from .parser import read_workbook
from . import store


def main():
    p = argparse.ArgumentParser()
    p.add_argument("file", type=Path)
    p.add_argument("--day", required=True, help="Date documented in the comparator's source paths")
    args = p.parse_args()
    raw = args.file.read_bytes()
    for code, suffix in (("ANTERIOR", "_old"), ("ACTUAL", "_new")):
        payload = read_workbook(raw, suffix=suffix)
        identifier, created = store.save(args.day, code, raw, args.file.name, "Comparador adjunto · fecha indicada en sus rutas", payload, family="reference")
        print(f"{code}: {len(payload['assets'])} series · id {identifier} · {'importado' if created else 'ya archivado'}")


if __name__ == "__main__":
    main()
