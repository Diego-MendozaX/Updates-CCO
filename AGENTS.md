# Updates-CCO

El flujo vigente es `actualizar_base.py` → base histórica local → HTML autocontenido. La API/React anterior se mantiene como trabajo previo y no es necesaria para usar el dashboard.

Para trabajar con nombres, tecnologías, potencias, URS, hidrología o estados de centrales, lee `docs/MANTENIMIENTO_CATALOGOS.md`. Las fuentes técnicas editables son los cuatro Excel de `catalogos/fuentes/`; los alias, grupos hidráulicos y estados confirmados están en `catalogos/ajustes.json`. Evita crear catálogos paralelos en assets o reemplazar datos actuales por cifras históricas del PBIX.

Conserva procedencia, vigencias y revisiones. No infieras un retiro comercial de un cero o de una ausencia: necesita fecha y evidencia. Los alias automáticos requieren código COES, empresa coherente y referencia inequívoca. Los parámetros no conocidos permanecen pendientes y visibles.

Pruebas: `.venv/bin/python -m unittest discover -s tests -v`. Para cambios de interfaz, `.venv/bin/python tests/smoke_static.py --base base_coes --chromium /usr/bin/chromium`. Usa la base archivada para verificar totales, intervalos, filtros y fuentes reales; no conviertas vacíos o horas no publicadas en ceros.

La recarga es manual mediante «Refrescar página». Se mantienen las 18 gráficas adaptadas del PBIX, las selecciones de reprogramas y su comparación consecutiva. No introduzcas una recarga periódica ni dependencias externas al abrir el HTML.

Los cuatro Excel de matrices técnicas están autorizados para este repositorio. Los anexos operativos, el PBIX, SQLite, `base_coes/` y las capturas permanecen fuera de Git.
