# NASA–CONAF | Análisis de incendios forestales de Chile

Aplicación académica del curso **CC3201 Bases de Datos** de la Universidad de Chile. Integra incendios registrados por CONAF y focos satelitales NASA FIRMS para consultar estadísticas históricas mediante Django y PostgreSQL.

## Funcionalidades

| Ruta | Módulo |
| --- | --- |
| `/` | Evolución de incendios, focos NASA y hectáreas por temporada |
| `/causas/` | Incendios y superficie por causa, filtrados por región y temporada |
| `/coincidencias/` | Incendios CONAF asociados a focos NASA |
| `/vegetacion/` | Superficie afectada por tipo de vegetación |

Las consultas están en `incendios/consultas.py` y utilizan SQL parametrizado. La base de datos del curso se llama `cc3201` y sus tablas se consultan mediante el esquema `electromaquinas`.

## Requisitos

- Python **3.13** (entorno utilizado: **3.13.13**).
- Windows con CMD para los comandos de este documento.
- Acceso SSH autorizado al servidor del curso y a la base de datos PostgreSQL para ver datos reales.

## Primera instalación (Windows CMD)

Desde la carpeta raíz, donde está `manage.py`:

```cmd
py -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
```

**Configurar la clave Django:** genera una clave aleatoria con:

```cmd
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copia el valor producido y colócalo después de `DJANGO_SECRET_KEY=` en tu archivo `.env`. No compartas ni subas `.env` a Git. Si ya existe un `.env` válido, **no lo sobreescribas** al seguir estas instrucciones.

La configuración de desarrollo por defecto (`POSTGRES_HOST=127.0.0.1`, `POSTGRES_PORT=5540`, `POSTGRES_PASSWORD=` vacío) requiere un túnel SSH hacia el socket PostgreSQL remoto; no presupone una contraseña de PostgreSQL.

```cmd
python manage.py migrate
python manage.py check
```

La migración anterior utiliza la base SQLite interna de Django (`db.sqlite3`); **no modifica** las tablas `electromaquinas` de PostgreSQL.

## Ejecutar con datos reales

**CMD 1: abrir y mantener el túnel SSH** (se solicitará la contraseña SSH):

```cmd
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:5540:/var/run/postgresql/.s.PGSQL.5432 -p 240 cc3201@cc3201.dcc.uchile.cl
```

Es normal que CMD no muestre ningún mensaje tras la autenticación: el túnel queda abierto hasta pulsar `Ctrl + C`.

**CMD 2: iniciar Django** (con `venv` activo):

```cmd
python manage.py runserver
```

Abrir `http://127.0.0.1:8000/`. Los endpoints `/causas/`, `/coincidencias/` y `/vegetacion/` requieren el mismo túnel para consultar el servidor.

## Pruebas automatizadas

No necesitan PostgreSQL ni túnel SSH porque las consultas están simuladas con `unittest.mock`:

```cmd
python manage.py test incendios -v 2
```

Al completar la primera etapa de refactorización se aprobaron **11 pruebas** de vistas, filtros, totales y navegación.

## Mediciones de rendimiento SQL

Con el túnel activo:

```cmd
python scripts\medir_baseline.py
```

Los archivos generados se almacenan en `resultados_sql/baseline/` y se excluyen del repositorio mediante `.gitignore`. **No sobrescribir las mediciones iniciales ya obtenidas**: son la referencia para comparar optimizaciones futuras. Guardar una copia externa antes de repetir el script.

## Estructura

- `config/`: configuración global y URLs raíz de Django.
- `incendios/`: vistas HTTP, consultas SQL, rutas, pruebas y recursos de las páginas.
- `incendios/templates/incendios/`: plantillas con espacio de nombres Django.
- `incendios/static/incendios/`: estilos de la aplicación.
- `scripts/`: utilidades de medición y análisis SQL.
- `resultados_sql/`: resultados locales de `EXPLAIN ANALYZE` (ignorados por Git).

## Estado del despliegue

**La aplicación todavía funciona en desarrollo local; no está desplegada para evaluación.** Antes de publicar se requiere confirmar el servidor web asignado por el curso, configurar la conexión a PostgreSQL desde ese servidor, cambiar `DJANGO_DEBUG=False`, definir el dominio en `DJANGO_ALLOWED_HOSTS`, generar una clave `DJANGO_SECRET_KEY` específica para producción, servir archivos estáticos y ejecutar `python manage.py check --deploy`.

La configuración local del túnel (`127.0.0.1:5540`) **no es válida por sí sola** para el despliegue definitivo. No modificar la configuración global del servidor PostgreSQL compartido sin autorización.
