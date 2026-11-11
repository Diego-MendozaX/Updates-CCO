# Correspondencia del PBIX con el monitor Kallpa

Se analizó el archivo aportado **Resumen ejecutivo RDO - version beta.pbix**: nueve páginas, 117 contenedores visuales, 28 tablas del modelo, 42 medidas DAX y siete relaciones. Los contenedores incluyen fondos, imágenes, encabezados y segmentadores. Los visuales de datos son **18 gráficas, 21 tarjetas y cinco tablas**. Las páginas Análisis Eléctrico y Apuntes operativos utilizan una imagen de resultados y un espacio de notas, respectivamente.

El modelo contiene cifras del **01/09/2026** y consultas locales a Consolidado_PDO y otros insumos. El monitor usa su estructura, identidad visual y catálogos técnicos; las cifras operativas se obtienen de los **anexos oficiales del COES de la fecha seleccionada**. No hace falta Power BI, Consolidado_PDO ni resultados YUPANA adicionales para actualizarlo.

## Páginas, visuales y fuentes

| Página PBIX | Visuales de datos | Implementación HTML | Fuente actualizable |
| --- | --- | --- | --- |
| Resumen Ejecutivo | 3 gráficas, 6 tarjetas y tabla de motivo | Despacho apilado por categoría con demanda y máxima; energía por empresa; curvas CMg; cinco KPI; fecha en selector; motivo en tarjeta lateral | Anexo 1 de despacho y listado oficial de reprogramas |
| Despacho INKIA | 4 gráficas | Despacho térmico, hidráulico y RER por central; potencia media/referencia y factor por tecnología; cuatro KPI adicionales | Despacho de la emisión elegida + catálogo técnico beta |
| Hidrología INKIA | 2 gráficas, 6 tarjetas y tabla de embalses | Caudal/factor por central; extremos de volumen y caudal diario por embalse; seis KPI; tabla de balance | Anexo 2 Hidrología del PDO + Qmáx. técnico del catálogo |
| Despacho - Otras empresas (1/2) | 3 gráficas | Despacho convencional por central; potencia/factor; ranking energético; cuatro KPI adicionales | Despacho elegido + catálogo |
| Despacho - Otras empresas (2/2) | 3 gráficas | Despacho eólico/solar/otras RER; potencia/factor; ranking energético; cuatro KPI adicionales | Despacho elegido + catálogo |
| RPF/RSF | 1 gráfica, 5 tarjetas y 2 tablas | UP/DOWN por URS; número de URS activas, medias MW y participaciones; tablas completas de delegación y vinculación | Anexo 6 PDO o RS_Reprog específico; anexos 8A y 8B diarios |
| Mantenimientos y restricciones | 2 gráficas, 4 tarjetas y tabla | Eventos por categoría, ranking por MW del evento, cuatro KPI, tabla con buscador y filtros | Anexo 1 Intervenciones del PDI y anexo 5 Restricciones del PDO |
| Análisis Eléctrico | Imagen del análisis de contingencias y textos | Cargabilidades tabulares publicadas, página de origen, informe PDF incorporado y flujos del despacho | Anexo 2 Análisis Eléctrico del PDI y despacho |
| Apuntes operativos | Espacio para apuntes | Bitácora editable por fecha/emisión/revisión, guardado local e importación/exportación JSON | Observaciones del usuario, sin envío externo |

Las 18 gráficas del PBIX tienen una vista correspondiente. Se agregan **Variaciones** y **Archivo de programas** para mantener la comparación consecutiva, el mapa de cambios, los valores por intervalo y los originales descargables. Las tarjetas y tablas se integran en el diseño de la página; el motivo del reprograma, por ejemplo, se presenta como una tarjeta de texto.

## Fuentes y frecuencia

El script obtiene las emisiones del listado `DescargarListadoDeReProgramasPorFecha`, descarga cada anexo de despacho y consulta el explorador documental oficial para los anexos complementarios:

- Programa de Operación / Programa Diario: hidrología, restricciones, reserva secundaria, vinculaciones y delegaciones.
- Reprograma Diario Operación: reserva `RS_Reprog_...` propia de cada emisión, cuando está publicada.
- Programa de Mantenimiento / Programa Diario: ZIP de intervenciones de agentes y ZIP del análisis eléctrico con su PDF.

La descarga descubre los nombres publicados, sin asumir que todos los días existen los mismos archivos. Las intervenciones admiten Excel **XLS, XLSX y XLSM** dentro del ZIP. Se leen valores, sin ejecutar macros. Los originales y sus huellas SHA-256 se conservan en `base_coes/anexos/`; los datos normalizados, en `base_coes/complementos/`.

**Cambiar de reprograma actualiza despacho y RSF; no crea nuevas observaciones hidrológicas ni de mantenimiento.** Esas secciones indican su fuente diaria PDO/PDI. Si falta una reserva específica se identifica expresamente el PDO empleado. Ante un fallo de lectura o conexión se conserva el último dato válido con su fuente y fecha, y se muestra el error de la nueva consulta.

## Criterios de cálculo revisados

1. **Demanda:** la medida `Demanda PDO` del PBIX suma generación. El monitor lee `Demanda COES` del anexo; la generación se calcula y presenta separadamente.
2. **Energía:** suma de los MW publicados en la ventana elegida × 0,5 / 1000 para GWh. Las horas anteriores a la vigencia de un reprograma son nulas, no cero. En la ventana común, ambos programas se comparan sobre los mismos intervalos.
3. **Generación por componentes:** no se suman totales con unidades. Los cogeneradores repetidos se deduplican por código COES; los no integrantes quedan fuera del total COES. La suma se contrastó con la columna oficial en las 15 emisiones reales verificadas.
4. **Grupo INKIA:** KALLPA, ORAZUL, KONDU y JOYA SOLAR, conforme al modelo beta.
5. **Clasificación:** se utiliza el catálogo técnico aportado, con alias inequívocos. Los sufijos explícitos TG/GT/TV/UTI identifican una unidad térmica; no determinan combustible, ciclo ni potencia. Las unidades desconocidas figuran como `Sin clasificación` en el resumen y en Variaciones. No se incluyen arbitrariamente en hidráulica, térmica o RER.
6. **Potencia y factor:** potencia media de la ventana / potencia de referencia del catálogo. La referencia beta no es una certificación actual de potencia efectiva. Se deduplica la referencia por central. Si falta potencia para alguna unidad de un grupo, no se calcula su factor ni se presenta una referencia parcial como si cubriera todo el grupo. Una referencia faltante no equivale a cero.
7. **Hidrología:** factor hidráulico = caudal turbinado diario / Qmáx. técnico. Para Carhuaquero y Cerro del Águila se suman sus grupos G1/G2/G3; Qmáx. se aplica una sola vez por central. El total publicado tiene prioridad sobre sus componentes y un grupo faltante impide calcular un factor parcial. Volumen inicial, final y su variación son valores diarios; no hay interpolación de una curva de 48 medias horas.
8. **RSF:** se muestran UP y DOWN como magnitudes MW; DOWN se grafica en negativo. Los KPI son medias de valores numéricos publicados (vacíos excluidos) y los picos se indican aparte. La suma de registros de media hora no se etiqueta como potencia instantánea. La participación divide la asignación acumulada publicada de la URS entre la reserva acumulada del sistema en la misma ventana; no divide medias calculadas sobre cantidades distintas de celdas.
9. **RPF:** se conservan las fechas, horas, porcentajes y respaldo de los anexos. Sus tablas muestran los anexos diarios completos; los filtros superiores de la página se aplican a RSF.
10. **Mantenimiento:** la suma y el ranking de MW corresponden a los eventos publicados, que pueden solaparse o repetirse. No se afirma que esa suma sea indisponibilidad simultánea. El tipo de equipo del catálogo EQUIPOS distingue generación/transmisión; los casos desconocidos quedan en Otros.
11. **Eléctrico:** se extraen conservadoramente filas tabulares que empiezan con un código L- y terminan en porcentajes explícitos. Para una fila con varios equipos/porcentajes se conserva el texto y se muestra el máximo de la fila agrupada, con su página. El PDF completo permite comprobar el contexto. No se deducen casos Base/N−1 ni se ejecutan simulaciones.
12. **CMg:** se grafican las barras presentes en el anexo. Los archivos verificados publican Santa Rosa, Trujillo y Socabaya; no se inventan las otras cinco barras que consultaba el PBIX.
13. **Solar:** se conservan los valores COES. No se repite la transformación Power Query del PBIX que fuerza ceros por horario.

## Interacción y funcionamiento local

La selección sigue **PDO → A → B → C → …**. Cada emisión exige su predecesor exacto: si falta B, C no se compara con A. El botón **Últimos dos publicados** activa el seguimiento de la emisión más reciente después de regenerar y recargar el HTML. Elegir manualmente una emisión desactiva ese seguimiento y conserva la selección al recargar.

Los filtros de alcance, empresa, central, tecnología y ventana están disponibles donde sus fuentes permiten aplicarlos; los demás aparecen deshabilitados. Hidrología usa su selector de embalse; mantenimiento incorpora categoría, tipo de vista y buscador. Las leyendas de las gráficas permiten ocultar series. Las tablas tienen paginación independiente y la vista puede exportarse como CSV.

El HTML incorpora datos, logo, estilos y Chart.js. No necesita conexión para consultar las gráficas ya generadas. Los enlaces a Excel/PDF requieren conservar la carpeta `base_coes` completa. La actualización ocurre al ejecutar el script; la casilla de recarga solo relee el HTML, no descarga nuevos programas.

La bitácora se guarda en el navegador local. Cambiar de navegador o de ubicación del HTML puede cambiar el almacenamiento disponible; exportar el JSON permite conservar o trasladar los apuntes.

## Identidad visual y mantenimiento

Se incorporaron el isotipo del PBIX y los colores de su tema `PDO_Kallpa_-_Magenta_v4`: magenta **#A62E78**, magenta oscuro **#79144F**, morado **#682888**, rosa **#E80870**, naranja **#E86820**, amarillo **#F8A018** y azul **#3599B8**. El diseño usa navegación lateral, tarjetas, paneles blancos y disposición adaptable a móvil.

Los catálogos estáticos están en `backend/assets/plant_catalog.json`, `hydro_catalog.json` y `urs_catalog.json`. Contienen identificadores y referencias técnicas; no se publican las series operativas históricas del modelo ni el PBIX. Deben revisarse si se incorporan nuevas centrales o cambia su configuración. Chart.js 4.5.1 se distribuye localmente con su licencia MIT.

Validación de esta entrega: 28 pruebas de Python; comparación con totales publicados; navegación real de las 11 secciones; filtros, exportaciones, paginación, bitácora y vista móvil en Chromium. Las capturas y los datos de validación permanecen fuera de Git.
