# Matrices, actualización y advertencias

El catálogo se construye en cada ejecución a partir de los cuatro Excel de **catalogos/fuentes/**. Estos cuatro adjuntos son matrices técnicas autorizadas por el usuario para integrarse al repositorio; no contienen las series operativas de los programas. Los anexos COES y las bases generadas continúan fuera de Git.

| Matriz | Filas | Uso |
| --- | ---: | --- |
| Matriz_Hidro y termicas INKIA.xlsx | 43 | Tecnología, nombre fuente, nombre de dashboard, empresa y capacidad instalada de hidráulicas y térmicas INKIA |
| Matriz_RER y otras termicas.xlsx | 137 | Las mismas referencias para RER y otras térmicas |
| Matriz_Anexo_Hidrologia.xlsx | 37 | Relación con el anexo hidráulico, potencia efectiva, eficiencia y Qmáx. |
| Matriz URS.xlsx | 19 | Código URS, central/unidad y empresa |

La capacidad instalada de generación y la potencia efectiva hidráulica conservan sus nombres y significados. La interfaz usa «potencia de referencia» cuando resume una matriz; no certifica una potencia nueva. Qmáx. se contrasta contra potencia efectiva / eficiencia con tolerancia del 0,1 %.

## Actualizar un parámetro o agregar una central

1. Edita la fila correspondiente o agrega una fila al Excel apropiado en `catalogos/fuentes/`. Conserva los encabezados. Guarda el libro con los resultados de sus fórmulas calculados por Excel.
2. Ejecuta `actualizar_base.py`. También puedes aplicar las matrices a la base existente mediante `--sin-descargar`.
3. Revisa **Catálogos y alertas**. Incluye las referencias, sus filas de origen, el inventario observado, los avisos pendientes y el historial de cambios. El Excel consolidado incorpora las mismas tablas.

No hace falta editar el código ni instalar nuevas dependencias. El lector detecta las hojas por sus columnas y admite nuevas filas o nuevos libros XLSX con el mismo esquema dentro de esa carpeta. Los encabezados rotos, referencias duplicadas, capacidades negativas o parámetros hidráulicos inconsistentes rechazan la revisión; si existe una revisión anterior válida, se conserva y el HTML muestra el error. La ejecución termina con código 2 en ese caso.

Las capacidades vacías o cero permanecen visibles y generan aviso, sin utilizarse como denominador de un factor. En los archivos proporcionados hay cuatro bloques de Punta Lomitas con capacidad cero. Esto **no indica retiro comercial**.

También se detectó que `CHAGLLA GP1` tiene nombres de dashboard distintos en las matrices de generación e hidrología. Para la gráfica se usa el nombre de generación de esa referencia exacta (`PCH CHAGLLA`), se conserva el nombre original de la matriz hidráulica y se muestra un aviso.

## Qué se actualiza automáticamente

- Toda unidad nueva del anexo se incorpora al inventario con código COES, nombre, empresa publicada, primera y última aparición y procedencia. También se registran nuevas URS y embalses.
- Las coincidencias exactas, los alias explícitos y las variantes inequívocas usan la matriz correspondiente. Los nombres romanos y arábigos se comparan sin cambiar el nombre original del anexo.
- Si una unidad cambia de nombre manteniendo un código COES positivo, una empresa coherente y una referencia anterior inequívoca, se incorpora el alias y se registra el cambio. No se heredan parámetros cuando hay ambigüedad de unidad, modo o empresa.
- Los grupos hidráulicos se agregan una sola vez por central según el conjunto explícito de `hydrology_groups`. Un total publicado prevalece sobre sus componentes y la ausencia de un grupo esperado impide calcular un factor parcial.
- Un dato técnico que no puede deducirse de las fuentes permanece pendiente. El programa no inventa potencia instalada, caudal máximo, combustible ni fecha de entrada comercial.

Estas actualizaciones se guardan en el catálogo local durante la ejecución; el script no hace commits ni subidas automáticas a GitHub desde tu computadora. Las matrices y los ajustes versionados en el repositorio son la fuente editable para futuras entregas.

## Cambios de nombre y ajustes explícitos

`catalogos/ajustes.json` contiene:

- `generation_aliases`: nombre publicado → referencia exacta de la matriz de generación.
- `hydrology_groups`: referencia hidráulica → lista completa de nombres de grupos del anexo.
- `commercial_status`: estados comerciales con fecha y evidencia.
- `effective_from` opcional: fecha `AAAA-MM-DD` desde la que debe aplicarse una revisión de matrices.

Las listas de grupos actuales se contrastaron con los anexos reales del 03/11 y 11/11/2026. Un grupo adicional requiere revisar el conjunto y su Qmáx.; no basta con sumar una unidad nueva a un denominador antiguo.

## Centrales ausentes y retiros comerciales

Una unidad que antes aparecía y falta en el PDO de una fecha posterior queda **no_observada**, con su última aparición. Esta comprobación exige un PDO estructurado y una consulta del listado y despacho verificada; un error de descarga no produce un retiro. Si vuelve a aparecer, recupera el estado observado y se registra su reaparición. Un despacho cero tampoco determina un retiro.

Un retiro confirmado debe registrarse en `commercial_status`, con código COES o referencia exacta, fecha y evidencia identificable. Ejemplo de estructura, usando un código y una fecha que deben reemplazarse por los reales:

```json
{
  "coes_code": "CODIGO_REAL",
  "status": "fuera_de_operacion_comercial",
  "effective_from": "2027-01-01",
  "evidence": "URL o identificación de la comunicación oficial del COES"
}
```

Se acepta `en_operacion` para registrar un estado confirmado de operación. Una unidad retirada no se elimina del archivo histórico. Si COES publica despacho positivo después de la fecha registrada, aparece una advertencia para revisar el estado y su evidencia; los valores originales siguen conservados.

## Revisión histórica y vigencia

Cada revisión de matrices guarda el contenido normalizado, los cuatro originales, sus SHA-256 y las diferencias de parámetros. La primera importación se considera la referencia de partida para las fechas ya archivadas, **sin afirmar una fecha técnica de vigencia que no figure en los Excel**.

Las revisiones posteriores se aplican desde el día de importación en hora de Perú. `effective_from` permite indicar una vigencia distinta, por ejemplo para una corrección histórica respaldada. Para cada día el dashboard selecciona la última revisión aplicable; los cálculos históricos anteriores conservan sus parámetros. Revertir a una matriz anterior se registra como otra aplicación, sin borrar el historial.

```text
base_coes/catalogos/
  referencias.json              Revisiones y vigencias
  versiones/REVISION.json       Parámetros normalizados inmutables
  fuentes/SHA/Archivo.xlsx      Originales de cada matriz
  inventario.json               Unidades observadas y eventos
  cambios.jsonl                 Bitácora de eventos sin duplicados
  revision_actual.json          Catálogo, inventario y avisos descargables
```

## Hidrología y actualización de la página

La vista conserva las dos gráficas hidráulicas del PBIX. El selector de centrales comienza en INKIA y permite elegir todas las empresas u otras empresas. El selector de embalses comienza con **todos los embalses del anexo**, con filtros por alcance y empresa; la tabla permite elegir uno pulsando su nombre. Los factores CQR/CDP/CDA siguen visibles como referencias INKIA.

El anexo publica extremos diarios de volumen; las matrices técnicas no añaden una curva de volumen por media hora. Se muestran los datos existentes, con su frecuencia y fuente.

Se eliminó la recarga de 60 segundos. **Refrescar página** relee el HTML generado y conserva fecha, emisión, alcance, empresa, central y las selecciones hidráulicas. Para descargar nuevos reprogramas, primero ejecuta `actualizar_base.py`. El HTML local no inicia Python ni consulta el COES por sí solo.

## Mantenimiento del código

Flujo principal: `launcher.py` → `pipeline.acquire` → `pipeline.snapshot` → `matrices.read_matrices/archive_references` → `dashboard.enrich` y `catalog_audit.CatalogAudit` → exportación Excel/JSON/HTML. La API/React anterior tiene un flujo independiente.

- `matrices.py` valida y versiona parámetros. No debe ejecutar macros ni fórmulas del Excel.
- `dashboard.py` resuelve correspondencias por día y mantiene generación, demanda y unidades separadas.
- `catalog_audit.py` administra identidades, altas, alias, ausencias y advertencias. Evita deducir estados comerciales de silencios o ceros.
- `dashboard.js` conserva las 18 gráficas adaptadas del PBIX, las vistas de comparación y archivo, y añade la pestaña del catálogo.

Antes de actualizar un alias o un parámetro, revisa el Excel y el encabezado real del anexo, el código COES, la empresa y la unidad física. Si falta evidencia, conserva el dato pendiente. Después ejecuta las pruebas de Python y, para cambios de interfaz, `tests/smoke_static.py` con la base real. No subas los datos de operación o la base local al repositorio.
