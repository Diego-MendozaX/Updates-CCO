# CCO · Base Excel y HTML actualizable

El flujo principal es **ejecutar un script → descargar los Excel oficiales → actualizar la base → regenerar un HTML interactivo**. El HTML incorpora sus datos y no requiere el servidor de la aplicación React de la primera versión.

El repositorio contiene únicamente código e instrucciones. Los Excel, las bases de datos, el adjunto y las salidas generadas se conservan localmente y están excluidos de Git.

Para obtenerlo desde GitHub, pulsa **Code → Download ZIP**, descomprime el archivo y abre una terminal dentro de la carpeta que contiene `actualizar_base.py`. Instala `requirements-base.txt` y ejecuta el script como se indica abajo. La primera ejecución descargará los datos en tu computadora.

## Base obtenida

Consultado el **11/11/2026, a las 11:43, hora de Perú**:

| Fecha de operación | Emisiones oficiales obtenidas | Excel |
| --- | --- | ---: |
| 03/11/2026 | PDO, A, B, C, D, E, F, G | 8 |
| 11/11/2026 | PDO, A, B, C, D | 5 |

Se descargaron y estructuraron **13 originales**, con 2.837 columnas en total (219 por emisión del 03/11 y 217 por emisión del 11/11). Se guardan 136.176 posiciones horarias, de las cuales **95.956 están publicadas en los archivos**; las demás se identifican expresamente como no publicadas. Una celda publicada puede estar vacía. Estas cifras describen la consulta, no garantizan que no se emitan más programas posteriormente.

La adquisición se ejecutó dos veces con los mismos 13 originales y no generó duplicados. La red del COES ya está habilitada y las descargas reales fueron verificadas; el bloqueo de la primera versión quedó resuelto.

## Ejecutar

Necesitas Python 3.12 e Internet para las nuevas descargas. Las únicas dependencias de este flujo son `openpyxl` y `httpx`.

```bash
python -m pip install -r requirements-base.txt
python actualizar_base.py
```

El script consulta **hoy, según la hora de Perú**, y conserva las fechas anteriores. En Windows puedes usar `py -3.12` en lugar de `python`; en Linux, `python3` si así se llama tu intérprete. Las pruebas se ejecutaron en Linux; los comandos Windows usan la interfaz estándar de Python.

Puedes usar un entorno virtual si lo prefieres. En el entorno de nube preparado:

```bash
cd /workspace/Updates-CCO
.venv/bin/python actualizar_base.py
```

Para una fecha específica, varias fechas o un rango incluido:

```bash
python actualizar_base.py --fecha 2026-11-03
python actualizar_base.py --fecha 2026-11-03 --fecha 2026-11-11
python actualizar_base.py --desde 2026-11-03 --hasta 2026-11-11
```

Cada fecha realiza una consulta al listado oficial y descarga el PDO y las letras detectadas. No se limita a A–E ni se detiene ante una letra no disponible. Las nuevas emisiones se archivan y un archivo idéntico no se duplica. Un Excel modificado para la misma emisión crea una revisión; las anteriores siguen disponibles.

Para regenerar las exportaciones sin consultar Internet:

```bash
python actualizar_base.py --sin-descargar
```

La opción `--base /ruta/carpeta` cambia la carpeta persistente de salida. No ejecutes dos procesos simultáneos sobre la misma base. Un archivo `.actualizacion.lock` evita que se reemplacen las salidas; si una ejecución se interrumpe, verifica que haya terminado antes de retirarlo.

## Abrir la página

Abre **`base_coes/index.html`** con tu navegador. El contenido está incorporado en ese archivo: no usa API, CDN, React, Node ni un servidor Python. Las curvas, selectores de fecha/versión/variable, buscador del archivo y exportación de la serie CSV funcionan con los datos de la última ejecución.

Cada vez que termina el script, reemplaza el HTML con la nueva instantánea. Si la página ya estaba abierta, recárgala o deja activada **Releer HTML cada 60 s**. Esa opción relee el archivo y conserva fecha/versión/variable en el fragmento de la dirección; no consulta el COES por sí sola.

Conserva la carpeta completa: los enlaces a Excel, JSON y originales son relativos. Copiar solo el HTML permite explorar sus series incorporadas, pero sus enlaces a otros archivos necesitan las carpetas acompañantes.

El Chromium administrado del entorno bloquea la navegación `file://`. Los controles se validaron sirviendo la misma carpeta estática y, adicionalmente, cargando todo el HTML incorporado sin un origen HTTP. En un navegador con esa restricción administrativa, puedes servir la carpeta con `python -m http.server 8000 --directory base_coes`; el diseño del archivo no depende de un servidor ni hace peticiones de datos.

## Salidas

```text
base_coes/
  index.html              Página interactiva regenerada
  base_excel.xlsx         Base consolidada para revisar en Excel
  archive.sqlite3         Base de datos y registro de ejecuciones
  manifest.json           Catálogo, fuentes, estados y huellas
  excel/FECHA/VERSION/SHA/NombreOriginal.xlsx
  originals/SHA           Originales inmutables utilizados por SQLite
  listados/FECHA/SHA/Reprogramas.xlsx
```

El libro consolidado contiene:

- **Programas:** fecha, versión, predecesor, revisión, ruta, descarga, fuente y SHA-256.
- **Publicaciones:** vigencia, última modificación y motivo informados por COES.
- **Columnas:** nombre, código COES, hoja y columna de origen, grupo, sección, rol y unidad. `resumen_fila_MWh_original` conserva literalmente el valor de la fila rotulada MWh; no se interpreta como energía cuando la columna tiene otra unidad.
- **Datos:** posición horaria, hora original y normalizada, valor numérico/texto, celda de origen, indicador de celda vacía e indicador de publicación en la emisión.
- **Consultas:** hora de consulta, verificación del listado, cantidades, estado y errores.

Las tablas SQLite principales son `versions`, `publication_listings`, `excel_series`, `excel_values` y `acquisition_runs`. Las revisiones y consultas anteriores permanecen en SQLite; el catálogo y las exportaciones muestran la última consulta por fecha y todas las revisiones archivadas.

## Reglas de lectura

1. Se valida que la respuesta sea un Excel real y que su fecha interna coincida con la solicitada.
2. El listado se lee por encabezados: FECHA, REPROGRAMA, BLOQUE HORARIO, CAUSA REPROGRAMA y ÚLTIMA MODIFICACIÓN. Se conservan los originales de los listados.
3. Los anexos reales contienen una columna **Día Hora** y un encabezado de variables. Se admite que cada reprograma publique solo una ventana: el G del 03/11, por ejemplo, empieza a las 21:00.
4. Se alinean las horas sobre una malla de 48 posiciones: `00:30`…`24:00`. El rótulo original `23:59` se conserva junto a la hora normalizada `24:00`. La base no calcula energía a partir de esa normalización ni afirma que los programas parciales contengan 48 registros publicados.
5. **No se rellenan los intervalos previos con cero ni con el programa anterior.** En SQLite, `present_in_source=0` identifica una hora no publicada, con `source_row=0`; `present_in_source=1` y valor nulo identifica una celda publicada vacía.
6. Se separan roles: despacho, renovables, cogeneración, no integrantes, demanda total, demanda por áreas, demanda del modelo, totales, flujos, reservas y costos marginales. No se suman totales con sus componentes ni demanda con generación. Los costos conservan USD/MWh; no se muestran como MW.
7. El HTML compara una columna contra la misma columna normalizada del **predecesor exacto**. Si falta B, C no se compara con A. Los valores solo se restan donde ambos programas contienen datos numéricos comparables.
8. La clasificación individual térmica/hidro no viene explícita para todas las columnas del anexo; queda pendiente de un catálogo de equipos. Esta base tampoco sustituye la demanda por barra de los CSV de YUPANA que utiliza el comparador adjunto.
9. Se leen valores guardados; no se ejecutan macros, fórmulas o enlaces externos. La conexión conserva proxy y verificación TLS.

## Errores y actualización

Un fallo de red o lectura no borra los archivos anteriores. El script genera una salida parcial identificada como tal y termina con **código 2** si la consulta solicitada no se completó. El código 0 indica que la ejecución terminó correctamente. La fecha de consulta y la fecha de generación se presentan por separado, por lo que regenerar el HTML sin descargar no aparenta una nueva consulta al COES.

La página es una instantánea: si se emite otro reprograma, es necesario volver a ejecutar el script. No hay un proceso de descarga permanente ni un planificador instalado.

## Validación

En el repositorio completo, con `requirements.txt` instalado:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

La entrega enfocada en la base incluye sus siete pruebas específicas; se ejecutan con `python -m unittest discover -s tests -p test_base.py -v` y solo las dependencias de `requirements-base.txt`.

La suite tiene 17 pruebas: lectura del listado real por columnas y listado vacío, ventanas parciales, vacíos, fecha interna, unidades, procedencia de celdas, persistencia e idempotencia, exportaciones, respuesta HTML que no es Excel, salida parcial con error y las reglas del comparador previo.

Con los archivos reales se comprobaron las 13 descargas, los 13 lectores, los enlaces a originales, filtros de fecha y emisión, selección de variables, horas no publicadas, exportación CSV y vista móvil sin errores de JavaScript.

## Código

- `actualizar_base.py`: comando principal.
- `backend/coes.py`: consulta de listados y descarga.
- `backend/excel_base.py`: lectura de anexos y almacenamiento normalizado.
- `backend/pipeline.py`: adquisición y exportación Excel/JSON/HTML.
- `backend/templates/base.html`: página estática con datos incorporados.
- `backend/store.py`: archivo de versiones y revisiones.

En el repositorio completo, la aplicación React/API anterior permanece en `frontend/` y `backend/main.py` como trabajo previo. Sus categorías y el lector del comparador YUPANA son independientes de esta base oficial; no se necesitan para ejecutar este flujo. La subida del código a GitHub conserva el HTML como una salida local del script; el alojamiento del dashboard en una dirección pública es un paso separado.
