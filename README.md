# Kallpa · Monitor de operación RDO

Ejecuta `actualizar_base.py` para descargar los anexos oficiales del COES, conservar la base histórica, regenerar **`base_coes/index.html`** y abrirlo en tu navegador. El HTML contiene sus datos, gráficas, estilos y logo; funciona sin Power BI, React, Node ni servidor de aplicación.

La versión 3 incorpora las **nueve páginas del PBIX aportado**, con sus 18 gráficas adaptadas a las fuentes disponibles, tarjetas, tablas y la identidad visual Kallpa. Conserva **Variaciones** y **Archivo de programas**, la selección de emisiones y la comparación de cada reprograma con su predecesor exacto. Añade matrices editables, revisión de parámetros, inventario de unidades y actualización manual de la página.

Lee la [guía de matrices, avisos y mantenimiento](docs/MANTENIMIENTO_CATALOGOS.md) y el [análisis del PBIX y correspondencia de visuales](docs/PBIX-COES.md) para conocer las fuentes, medidas y adaptaciones. La actualización utiliza únicamente anexos COES: no necesita Consolidado_PDO ni resultados YUPANA adicionales.

## Descargar o actualizar el código

En [GitHub](https://github.com/Diego-MendozaX/Updates-CCO), pulsa **Code → Download ZIP** y descomprime. Si ya usabas una versión anterior, conserva tu carpeta `base_coes` y cópiala dentro de la nueva carpeta del proyecto antes de ejecutar. Así mantienes los originales y el historial.

El repositorio distribuye código, documentación, recursos gráficos y las cuatro matrices técnicas aportadas en `catalogos/fuentes/`. Los anexos Excel operativos, el PBIX y las bases generadas se conservan localmente y están excluidos de Git.

## Ejecutar con Spyder

1. Abre `actualizar_base.py` en Spyder.
2. En la consola IPython consulta el Python que utiliza Spyder:

   ```python
   import sys
   print(sys.executable)
   ```

3. Abre **Anaconda Prompt o CMD**, entra a la carpeta que contiene `actualizar_base.py` e instala las dependencias con ese mismo Python. Por ejemplo, reemplazando la ruta por la que imprimió Spyder:

   ```bat
   "C:\ruta\al\python.exe" -m pip install -r requirements-base.txt
   ```

   Este comando se ejecuta en la terminal del sistema. Spyder desaconseja instalar paquetes desde su consola IPython.

4. Vuelve a Spyder y ejecuta el archivo con **F5**, usando el directorio del archivo como carpeta de trabajo. Se consulta hoy en hora de Perú, se actualiza la base y se abre el HTML automáticamente.
5. Si el navegador no se abre, la consola imprime la ruta completa. Abre manualmente **`base_coes/index.html`**.

Para una fecha concreta puedes ejecutar en la consola de Spyder:

```python
%run actualizar_base.py --fecha 2026-11-03
```

Para reconstruir el HTML con los archivos ya descargados:

```python
%run actualizar_base.py --sin-descargar
```

### Si faltan pypdf o xlrd en Spyder

`No module named 'pypdf'` impide leer el PDF eléctrico; `No module named 'xlrd'` impide leer intervenciones en XLS. Los Excel de despacho y el HTML pueden haberse generado igualmente. El código 2 de esa ejecución significa que el resultado fue parcial.

En la consola de Spyder imprime el comando para su propio intérprete:

```python
import sys
print(f'"{sys.executable}" -m pip install pypdf==6.10.0 xlrd==2.0.2')
```

Copia **la línea que imprime** y ejecútala en **Anaconda Prompt o CMD**. Después reinicia el kernel de Spyder, abre `actualizar_base.py` y pulsa F5. Ejecuta una actualización normal para leer los anexos que antes fallaron; `--sin-descargar` solo reconstruye lo que ya se había leído.

La entrada actual comprueba los paquetes antes de comenzar y muestra un comando de instalación con las rutas del Python y de `requirements-base.txt`. En Spyder una ejecución incompleta muestra un mensaje claro sin el traceback `SystemExit: 2`; desde terminal conserva el estado de salida 2 para detectar fallos en tareas programadas.

## Ejecutar desde una terminal

Se verificó con Python 3.12. Instala las cuatro dependencias del flujo estático:

```bash
python -m pip install -r requirements-base.txt
python actualizar_base.py
```

En Windows puedes usar `py -3.12` en lugar de `python`; en Linux, `python3` si ese es el nombre del intérprete. Usa siempre el intérprete donde instalaste las dependencias. El funcionamiento en Windows utiliza las interfaces estándar de Python; las pruebas automatizadas de esta entrega se ejecutaron en Linux.

```bash
python actualizar_base.py --fecha 2026-11-03
python actualizar_base.py --fecha 2026-11-03 --fecha 2026-11-11
python actualizar_base.py --desde 2026-11-03 --hasta 2026-11-11
python actualizar_base.py --sin-descargar
python actualizar_base.py --no-abrir
python actualizar_base.py --solo-despacho
```

- Sin fechas: consulta **hoy en Perú** y conserva lo anterior.
- `--sin-descargar`: regenera Excel, catálogo y HTML sin consultar Internet.
- `--no-abrir`: omite la apertura del navegador; útil para ejecuciones programadas.
- `--solo-despacho`: omite nuevas consultas de anexos complementarios. Las fuentes ya archivadas conservan sus fechas.
- `--base /ruta/carpeta`: elige otra carpeta persistente de salida.

No ejecutes dos procesos sobre la misma base. El archivo `.actualizacion.lock` evita reemplazos simultáneos; si una ejecución se interrumpe, comprueba que haya terminado antes de retirarlo.

## Qué contiene el dashboard

| Sección | Contenido |
| --- | --- |
| Resumen ejecutivo | Demanda, energía, participación INKIA, despacho por tecnología, empresas, CMg y motivo del reprograma |
| Despacho INKIA | Térmica, hidráulica, RER, potencia media, potencia de referencia y factor de uso |
| Hidrología y embalses | Caudales y factores INKIA/otras empresas; todos los embalses COES, filtros por empresa, volúmenes y variación |
| Otras empresas · 1/2 y 2/2 | Despacho, potencia/factor y ranking energético convencional y RER |
| RPF / RSF | UP/DOWN por URS, participación y tablas de delegaciones/vinculaciones |
| Mantenimientos | Categorías, ranking por MW del evento, indicadores, restricciones y tabla de detalle |
| Análisis eléctrico | Cargabilidades tabulares extraídas, páginas de origen, PDF y flujos del despacho |
| Apuntes operativos | Bitácora por emisión, guardado local e importación/exportación |
| Variaciones | Curvas actual/anterior, umbral, mapa de cambios, detalle y celda de origen |
| Catálogos y alertas | Matrices editables, referencias, unidades nuevas, alias, ausencias, parámetros pendientes e historial |
| Archivo de programas | Originales, revisiones, motivos, vigencias y todos los anexos descargables |

Los filtros se habilitan según la fuente de cada sección. Las leyendas de gráficas ocultan series, las tablas tienen paginación independiente y los datos de cada vista se exportan a CSV.

**Últimos dos publicados** sigue la emisión más reciente después de regenerar y recargar la página. Si eliges una emisión manualmente, se conserva esa selección hasta volver a activar el botón. La comparación exige el predecesor exacto: PDO → A → B → C → …; si falta B, C no se compara con A.

Cada ejecución reemplaza el HTML. Si ya estaba abierto, pulsa **Refrescar página**. La recarga es manual y conserva fecha, emisión y filtros; para descargar nuevos programas debes ejecutar el script. No hay recarga periódica ni planificador.

## Matrices y mantenimiento

Las cuatro matrices se leen automáticamente en cada ejecución: 180 referencias de generación, 37 hidráulicas y 19 URS. Para actualizar un parámetro o agregar una central, edita la matriz correspondiente y ejecuta el script. Los cambios conservan original, SHA-256, vigencia y revisión anterior. La pestaña **Catálogos y alertas** muestra el resultado y sus pendientes.

Los alias inequívocos por código COES se incorporan automáticamente. Los retiros comerciales requieren fecha y evidencia en `catalogos/ajustes.json`; una ausencia solo se marca como no observada. Consulta la [guía de mantenimiento](docs/MANTENIMIENTO_CATALOGOS.md) para los detalles y el tratamiento de correcciones históricas.

## Fuentes y límites de los datos

- Despacho: anexo 1 PDO y anexos de cada reprograma, descubiertos mediante el listado oficial; no se limita a A–E.
- Hidrología: anexo 2 diario, con extremos de volumen y caudales diarios. **No hay curva horaria de volumen** en este anexo.
- RSF: anexo 6 PDO o `RS_Reprog` de la emisión. RPF: anexos 8A/8B diarios.
- Restricciones: anexo 5 PDO. Intervenciones: anexo 1 del Programa Diario de Intervenciones (PDI), en XLS/XLSX/XLSM dentro del ZIP.
- Análisis eléctrico: anexo 2 PDI; el informe no contiene la misma imagen Base/N−1 del PBIX. El monitor muestra resultados publicados con su PDF y **no ejecuta simulaciones**.
- CMg: se muestran las barras que existen en el anexo; las fuentes verificadas contienen tres, frente a ocho en el PBIX.
- Tecnologías, capacidades instaladas, potencia efectiva hidráulica y Qmáx.: matrices del usuario, con fila, archivo y revisión. Las unidades nuevas se incorporan al inventario; los parámetros no confirmados generan aviso y no se inventan. Un cero o una ausencia no confirman retiro comercial.

Cambiar de reprograma no modifica los anexos diarios. Cada sección identifica su fuente PDO/PDI o REP y la fecha. Las cifras históricas del PBIX no se presentan como datos actuales.

La demanda se lee de su columna real, sin sustituirla por generación. Los cogeneradores repetidos se deduplican y no se añaden los no integrantes al total COES. Las reservas se presentan como medias y picos MW. Los MW de mantenimiento son valores por evento y no una suma de indisponibilidad simultánea.

Los 48 intervalos normalizados son `00:30`…`24:00`; el rótulo original `23:59` se conserva. Los reprogramas pueden publicar una ventana parcial: **las horas anteriores permanecen nulas**, sin rellenarse con ceros ni con el predecesor. La energía se calcula sobre los valores disponibles en la ventana elegida, a media hora por registro. Solo se restan valores numéricos presentes en ambos programas.

## Base y originales

```text
base_coes/
  index.html                    Dashboard regenerado y autocontenido
  base_excel.xlsx               Datos consolidados y procedencia
  archive.sqlite3               Despacho, revisiones y consultas
  manifest.json                 Catálogo, estado, metodología y fuentes
  excel/FECHA/VERSION/SHA/       Originales de despacho descargables
  originals/SHA                 Originales inmutables de SQLite
  listados/FECHA/SHA/            Listados oficiales archivados
  anexos/FECHA/VERSION/SHA/      Excel, ZIP y PDF complementarios
  complementos/FECHA.json        Anexos normalizados y procedencia
  catalogos/                    Revisiones, matrices originales, inventario y avisos
```

El Excel conserva las cinco hojas de la primera versión: **Programas, Publicaciones, Columnas, Datos y Consultas**. Con anexos complementarios agrega **Anexos, Hidrologia_Embalses, Hidrologia_Centrales, Hidrologia_INKIA, RSF, RPF, Intervenciones, Restricciones, Analisis_Electrico y Clasificacion**, según existan registros. Los datos complementarios indican fecha, versión y SHA-256 de la fuente. También se exportan `Hidrologia_Referencias`, `Catalogo_Matrices`, `Catalogo_Hidrologico`, `Catalogo_URS`, `Inventario`, `Alertas_Catalogo` e `Historial_Catalogo`.

`Datos` distingue una hora no publicada de una celda publicada vacía y conserva hoja/celda de origen. `Columnas.resumen_fila_MWh_original` guarda el resumen original: no se interpreta como energía si la variable tiene otra unidad.

Los archivos idénticos no crean revisiones duplicadas. Un despacho modificado para la misma emisión crea una revisión y conserva las anteriores. Los anexos también conservan originales por huella; los paneles muestran la última lectura válida de cada fuente.

Conserva la carpeta completa para abrir los Excel y PDF enlazados. El HTML solo permite explorar sus datos incorporados; los enlaces relativos necesitan los archivos acompañantes. Un navegador administrado que bloquee `file://` puede servir la misma carpeta con `python -m http.server 8000 --directory base_coes`.

## Fallos y recuperación

Un fallo de red o lectura no borra los originales anteriores. Se genera el HTML con lo disponible, se muestran los errores y la consulta parcial termina con código **2**. El código **0** indica éxito. La fecha de consulta y la fecha de generación son distintas: regenerar sin descargar no aparenta una consulta nueva al COES.

Las respuestas de despacho se validan como Excel y por fecha interna. Los ZIP tienen límites de lectura; no se ejecutan macros ni enlaces externos. HTTP conserva la verificación TLS.

## Validación y código

Se verificaron 15 emisiones de dos fechas (03/11 y 11/11/2026), 27 anexos complementarios y la correspondencia entre las unidades deduplicadas y el total oficial. El listado es dinámico: otra ejecución puede encontrar nuevas emisiones.

Pruebas de la base y del informe con las dependencias mínimas:

```bash
python -m unittest discover -s tests -p test_base.py -v
python -m unittest discover -s tests -p test_report.py -v
```

En el repositorio completo, con `requirements.txt` instalado:

```bash
python -m unittest discover -s tests -v
```

La suite reúne 45 pruebas de adquisición, persistencia, comparación, exportación, lectura de anexos, dependencias en Spyder, catálogos versionados, alias, estados de observación y recuperación de fallos. El smoke test del HTML necesita Playwright y Chromium como herramientas de desarrollo:

```bash
python tests/smoke_static.py --base base_coes --chromium /usr/bin/chromium
```

Comprueba las 12 secciones, todos los embalses, las matrices y el refresco manual, las 18 gráficas del PBIX, filtros, paginación, CSV, apuntes, recarga, funcionamiento incorporado y móvil. No consulta el COES ni cambia la base.

Archivos principales:

- `actualizar_base.py`: entrada para terminal y Spyder.
- `backend/launcher.py`: comprobación de paquetes e instrucciones para el intérprete activo, antes de descargar.
- `backend/coes.py`, `excel_base.py`, `store.py`: adquisición y archivo de despacho.
- `backend/supplements.py`: descubrimiento y lectura de anexos complementarios.
- `backend/dashboard.py`: clasificación, procedencia y criterios del informe.
- `backend/pipeline.py`: exportación Excel/JSON/HTML y apertura del navegador.
- `backend/templates/base.html`, `backend/assets/dashboard.js` y `dashboard.css`: interfaz.
- `catalogos/fuentes/*.xlsx` y `catalogos/ajustes.json`: referencias técnicas editables.
- `backend/matrices.py` y `catalog_audit.py`: validación, revisiones, identidades y avisos.

La aplicación React/API anterior permanece como trabajo previo en `frontend/` y `backend/main.py`; no es necesaria para este flujo. La entrega del código en GitHub permite descargarlo y ejecutarlo localmente; no implica alojar públicamente los datos del dashboard.
