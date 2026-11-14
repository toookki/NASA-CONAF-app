"""Registra los planes de ejecución originales de Q1-Q4, sin modificar tablas.

Uso desde la raíz del proyecto, con venv y túnel SSH activos:
    python scripts/medir_baseline.py
"""

from __future__ import annotations

import csv
import json
import os
import statistics
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.db import connections  # noqa: E402
from incendios.consultas import (  # noqa: E402
    obtener_causas,
    obtener_coincidencias,
    obtener_evolucion,
    obtener_regiones,
    obtener_vegetacion,
)

SALIDA = RAIZ / "resultados_sql" / "baseline"
REPETICIONES = 3
BASE_DATOS = connections["incendios"]


def capturar_sql(funcion):
    """Obtiene el SQL real ejecutado por la función de la aplicación."""
    capturas = []

    def registrar(ejecutar, sql, parametros, many, contexto):
        if sql.lstrip().upper().startswith(("SELECT", "WITH")):
            capturas.append((sql, list(parametros or [])))
        return ejecutar(sql, parametros, many, contexto)

    with BASE_DATOS.execute_wrapper(registrar):
        filas = funcion()

    if len(capturas) != 1:
        raise RuntimeError(
            f"Se esperaba una consulta SQL, pero se capturaron {len(capturas)}."
        )

    sql, parametros = capturas[0]
    return sql, parametros, len(filas)


def analizar_plan(sql, parametros):
    """Ejecuta EXPLAIN ANALYZE sin modificar registros de la base de datos."""
    with BASE_DATOS.cursor() as cursor:
        cursor.execute(
            "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql,
            parametros,
        )
        resultado = cursor.fetchone()[0]

    if isinstance(resultado, str):
        resultado = json.loads(resultado)
    return resultado[0]


def verificar_vegetacion():
    """Comprueba los incendios sin fila asociada en afecta."""
    sql = """
        SELECT
            COUNT(*) AS sin_vegetacion,
            COUNT(*) FILTER (WHERE i.superficie_total_ha = 0)
                AS sin_vegetacion_y_cero_ha
        FROM electromaquinas.incendio i
        WHERE NOT EXISTS (
            SELECT 1
            FROM electromaquinas.afecta a
            WHERE a.id_incendio = i.id_incendio
        );
    """
    with BASE_DATOS.cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchone()


def guardar_indices():
    """Guarda el inventario de índices previo a las optimizaciones."""
    sql = """
        SELECT tablename, indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'electromaquinas'
        ORDER BY tablename, indexname;
    """
    with BASE_DATOS.cursor() as cursor:
        cursor.execute(sql)
        indices = cursor.fetchall()

    ruta = SALIDA / "indices_antes.csv"
    with ruta.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["tabla", "indice", "definicion"])
        escritor.writerows(indices)
    print(f"Índices registrados: {len(indices)}")


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)

    regiones = obtener_regiones()
    maule = next(
        (r for r in regiones if str(r["nombre_region"]).strip().casefold() == "maule"),
        None,
    )
    if maule is None:
        raise RuntimeError("No se encontró la región del Maule en la base de datos.")
    id_maule = maule["id_region"]

    sin_vegetacion, sin_vegetacion_cero = verificar_vegetacion()
    print(
        "Incendios sin registros en afecta:", sin_vegetacion,
        "| de ellos con 0 ha:", sin_vegetacion_cero,
    )
    guardar_indices()

    escenarios = [
        ("Q1_nacional", lambda: obtener_evolucion()),
        ("Q1_maule", lambda: obtener_evolucion(id_maule)),
        ("Q2_nacional", lambda: obtener_causas()),
        ("Q2_maule_2016", lambda: obtener_causas(id_maule, 2016)),
        ("Q3_nacional", lambda: obtener_coincidencias()),
        ("Q3_maule_2016", lambda: obtener_coincidencias(id_maule, 2016)),
        ("Q4_nacional", lambda: obtener_vegetacion()),
        ("Q4_maule_2016", lambda: obtener_vegetacion(id_maule, 2016)),
    ]

    resumen = []
    with BASE_DATOS.cursor() as cursor:
        cursor.execute("SET statement_timeout = '20000ms'")

    for nombre, funcion in escenarios:
        print(f"Analizando {nombre}...")
        sql, parametros, num_filas = capturar_sql(funcion)
        planes = [analizar_plan(sql, parametros) for _ in range(REPETICIONES)]
        tiempos = [plan["Execution Time"] for plan in planes]
        planificacion = [plan["Planning Time"] for plan in planes]

        detalle = {
            "escenario": nombre,
            "parametros": parametros,
            "filas_resultado": num_filas,
            "sql": sql,
            "planes": planes,
        }
        ruta = SALIDA / f"{nombre}.json"
        ruta.write_text(
            json.dumps(detalle, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        fila = {
            "escenario": nombre,
            "filas_resultado": num_filas,
            "parametros": json.dumps(parametros, ensure_ascii=False, default=str),
            "ejecucion_mediana_ms": round(statistics.median(tiempos), 3),
            "planificacion_mediana_ms": round(statistics.median(planificacion), 3),
            "ejecuciones_ms": "; ".join(f"{tiempo:.3f}" for tiempo in tiempos),
        }
        resumen.append(fila)
        print(
            f"  Filas: {num_filas} | Mediana: "
            f"{fila['ejecucion_mediana_ms']} ms"
        )

    ruta_csv = SALIDA / "resumen_baseline.csv"
    with ruta_csv.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(resumen[0]))
        escritor.writeheader()
        escritor.writerows(resumen)

    print(f"\nMediciones guardadas en: {SALIDA}")
    print("No se modificaron datos, índices ni vistas.")


if __name__ == "__main__":
    main()
