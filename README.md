# NASA–CONAF | Análisis de incendios forestales

Aplicación web para explorar información sobre incendios forestales en Chile mediante la integración de registros de **CONAF** y detecciones satelitales de focos de calor de **NASA FIRMS**.

La plataforma permite consultar indicadores, visualizar gráficos y examinar tablas de resultados con filtros territoriales y temporales. Su propósito es facilitar el análisis de la evolución de los incendios, sus causas, la correspondencia con detecciones satelitales y la vegetación afectada.

## Funcionalidades

La aplicación está organizada en cuatro secciones:

| Sección | Descripción |
| --- | --- |
| **Evolución temporal** | Compara por temporada la cantidad de incendios registrados por CONAF, los focos de calor detectados por NASA y la superficie afectada. |
| **Causas** | Presenta la distribución de incendios por causa, con cantidades, superficie asociada y porcentajes. |
| **Coincidencias NASA–CONAF** | Analiza los incendios con y sin detecciones satelitales asociadas, la cantidad de vínculos y los focos únicos relacionados. |
| **Vegetación afectada** | Resume la superficie quemada, los incendios asociados y los registros de afectación según el tipo de vegetación. |

Todas las secciones permiten filtrar por **región**. Las secciones de causas, coincidencias y vegetación permiten además seleccionar una **temporada**. Las temporadas se consideran desde el 1 de julio de un año hasta el 30 de junio del siguiente.

Los resultados se presentan mediante indicadores, gráficos interactivos y tablas detalladas.

## Tecnologías

- **Python y Django:** lógica de la aplicación, rutas, procesamiento de filtros y generación de páginas HTML.
- **PostgreSQL:** almacenamiento y consulta de datos relacionales.
- **Psycopg 3:** comunicación entre Django y PostgreSQL mediante consultas SQL parametrizadas.
- **HTML y CSS:** estructura y presentación de la interfaz.
- **Chart.js:** visualización de gráficos en el navegador.
- **JavaScript:** preparación y representación de los datos para los gráficos.

Las consultas analíticas están escritas en **SQL directo** y se ejecutan a través de la conexión `incendios` definida en Django. No dependen del ORM para obtener los indicadores.

## Organización del proyecto

```text
config/
    settings.py                 Configuración de Django y conexiones de datos
    urls.py                     Rutas generales
    wsgi.py                     Punto de entrada WSGI

incendios/
    consultas.py                Consultas SQL de las cuatro secciones
    views.py                    Procesamiento de resultados y contexto HTML
    filtros.py                  Validación de filtros
    errores.py                  Manejo de errores de acceso a datos
    urls.py                     Rutas de la aplicación
    tests.py                    Pruebas automatizadas
    templates/incendios/        Plantillas y componentes HTML
    static/incendios/           Hojas de estilo e imágenes

scripts/
    gestionar_vista.py          Administración de la vista SQL
    gestionar_indices.py        Administración de índices
    medir_consultas.py          Mediciones antes y después de optimizar
    comparar_indices.py        Comparación de tiempos y resultados

sql/
    01_crear_indices.sql
    02_revertir_indices.sql
    03_crear_vista.sql
    04_revertir_vista.sql

manage.py                       Comandos de administración de Django
requirements.txt               Dependencias Python
.env.example                   Ejemplo de variables de entorno
```

### Flujo general

1. El usuario selecciona los filtros en la interfaz.
2. Django valida los parámetros recibidos.
3. `consultas.py` ejecuta una consulta parametrizada en PostgreSQL.
4. `views.py` transforma los resultados en indicadores y datos para gráficos.
5. Las plantillas HTML muestran los resultados y Chart.js construye las visualizaciones.

## Consultas SQL

Las consultas principales se encuentran en `incendios/consultas.py`:

- **Evolución temporal:** agrupa por temporada los registros de incendios y focos de calor, y combina ambos conjuntos de resultados.
- **Causas:** agrupa incendios por causa y calcula frecuencias, superficies y participación porcentual.
- **Coincidencias:** utiliza las relaciones registradas entre incendios y focos de calor para distinguir incendios coincidentes, vínculos y focos únicos. Un vínculo no equivale necesariamente a un foco único.
- **Vegetación:** relaciona incendios con registros de afectación y tipos de vegetación. Un mismo incendio puede estar asociado a más de una categoría.

Las consultas utilizan parámetros para incorporar filtros, en lugar de concatenar directamente los valores introducidos por el usuario.

### Vista de apoyo

La vista convencional `electromaquinas.v_incendios_region` relaciona incendios, comunas y provincias para incorporar la región de cada incendio. Es utilizada por las consultas de **causas, coincidencias y vegetación**.

Su definición está en `sql/03_crear_vista.sql`. Al ser una vista convencional, no mantiene una copia materializada de los registros.

### Índices

El proyecto incluye tres índices B-tree para apoyar el acceso a datos mediante filtros:

| Índice | Tabla | Columnas |
| --- | --- | --- |
| `idx_incendio_comuna_fecha` | `incendio` | `id_comuna`, `fecha` |
| `idx_foco_calor_comuna_fecha` | `foco_calor` | `id_comuna`, `acq_date` |
| `idx_incendio_fecha` | `incendio` | `fecha` |

Los índices pueden reducir los tiempos de determinadas consultas filtradas, aunque el planificador de PostgreSQL decide si conviene utilizarlos en cada ejecución.

## Instalación y ejecución local

**Requisitos:** Python 3.13, PostgreSQL con el esquema y los datos requeridos, y las dependencias de `requirements.txt`.

1. Crear un entorno virtual e instalar dependencias:

   ```bash
   python -m venv venv
   ```

   En Windows:

   ```cmd
   venv\Scripts\python -m pip install -r requirements.txt
   ```

   En Linux o macOS:

   ```bash
   venv/bin/python -m pip install -r requirements.txt
   ```

2. Copiar `.env.example` a `.env` y ajustar las variables según el entorno. Como mínimo, se requiere una clave `DJANGO_SECRET_KEY` propia y los parámetros de conexión `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST` y `POSTGRES_PORT`.

3. Verificar la configuración y ejecutar las pruebas. En Windows:

   ```cmd
   venv\Scripts\python manage.py check
   venv\Scripts\python manage.py test incendios
   ```

   En Linux o macOS, sustituir `venv\Scripts\python` por `venv/bin/python`.

4. Iniciar la aplicación localmente:

   ```cmd
   venv\Scripts\python manage.py runserver
   ```

   La aplicación necesita acceso a una base de datos PostgreSQL compatible para mostrar los datos. El repositorio contiene el código y los scripts SQL, **no los registros originales ni una copia de la base de datos**.

> **Seguridad:** el archivo `.env` contiene configuración privada y está excluido de Git. No incorporar credenciales, contraseñas ni claves secretas al repositorio.

## Mediciones y validación

Los scripts de `scripts/` permiten evaluar el efecto de los índices mediante `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` y comparar las respuestas de las consultas antes y después de su creación.

El procedimiento contempla escenarios generales y filtrados, repeticiones de cada consulta y comparación de medianas. `comparar_indices.py` comprueba además que el SQL, los parámetros y los resultados obtenidos sean equivalentes entre ambas mediciones.

Los archivos generados se guardan en `resultados_sql/`, carpeta excluida de Git. Las mediciones de tiempo dependen de las condiciones de ejecución y no implican, por sí solas, una mejora garantizada en todos los escenarios.

## Pruebas y mantenimiento del código

El proyecto incluye pruebas automatizadas en `incendios/tests.py` para validar el comportamiento de las consultas, los filtros y las vistas.

Para realizar modificaciones:

- **Interfaz:** editar `incendios/templates/incendios/` y `incendios/static/incendios/`.
- **Indicadores y procesamiento:** revisar `incendios/views.py`.
- **Consultas SQL:** modificar `incendios/consultas.py` y verificar los resultados mediante pruebas.
- **Filtros:** revisar `incendios/filtros.py`.
- **Vista e índices:** consultar los archivos correspondientes de `sql/` y los scripts de gestión antes de efectuar cambios en la estructura de datos.

Se recomienda ejecutar las pruebas después de cada modificación relevante y mantener separadas las configuraciones privadas del código fuente.
