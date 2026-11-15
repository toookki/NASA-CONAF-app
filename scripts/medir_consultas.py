"""Mide las consultas Q1-Q4 antes y después de evaluar índices.

Desde la raíz del proyecto y con acceso a PostgreSQL:
    py -m scripts.medir_consultas antes
    py -m scripts.medir_consultas despues

Una sola fuente de escenarios y metodología. No ejecuta DDL ni
sobrescribe mediciones existentes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import statistics
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.db import connections  # noqa: E402
from incendios.consultas import (  # noqa: E402
    obtener_causas, obtener_coincidencias, obtener_evolucion,
    obtener_regiones, obtener_vegetacion,
)

SALIDA = RAIZ / "resultados_sql" / "optimizacion_indices"
REPETICIONES = 3
BASE_DATOS = connections["incendios"]


def valor_json(valor):
    if isinstance(valor, Decimal):
        return {"__tipo__": "decimal", "valor": format(valor.normalize(), "f")}
    if isinstance(valor, (date, datetime)):
        return {"__tipo__": "fecha", "valor": valor.isoformat()}
    raise TypeError(f"Tipo no serializable: {type(valor).__name__}")


def serializar(filas):
    return json.loads(json.dumps(filas, ensure_ascii=False, default=valor_json))


def huella(filas):
    contenido = json.dumps(filas, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


def capturar(funcion):
    capturas = []

    def registrar(ejecutar, sql, parametros, many, contexto):
        if sql.lstrip().upper().startswith(("SELECT", "WITH")):
            capturas.append((sql, list(parametros or [])))
        return ejecutar(sql, parametros, many, contexto)

    with BASE_DATOS.execute_wrapper(registrar):
        filas = funcion()
    if len(capturas) != 1:
        raise RuntimeError(f"Se esperaba 1 SELECT, se capturaron {len(capturas)}.")
    sql, parametros = capturas[0]
    return sql, parametros, serializar(filas)


def analizar(sql, parametros):
    with BASE_DATOS.cursor() as cursor:
        cursor.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql, parametros)
        resultado = cursor.fetchone()[0]
    if isinstance(resultado, str):
        resultado = json.loads(resultado)
    return resultado[0]


def listar_indices():
    sql = """
        SELECT tablename, indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'electromaquinas'
        ORDER BY tablename, indexname;
    """
    with BASE_DATOS.cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchall()


def verificar_indices(candidatos, fase):
    """Comprueba que los índices sean válidos antes de medir su efecto."""
    sql = """
        SELECT ic.relname, ix.indisvalid, ix.indisready
        FROM pg_index ix
        JOIN pg_class ic ON ic.oid = ix.indexrelid
        JOIN pg_namespace n ON n.oid = ic.relnamespace
        WHERE n.nspname = 'electromaquinas'
          AND ic.relname = ANY(%s)
    """
    with BASE_DATOS.cursor() as cursor:
        cursor.execute(sql, [sorted(candidatos)])
        filas = cursor.fetchall()

    encontrados = {nombre: (valido, listo) for nombre, valido, listo in filas}
    if fase == "antes" and encontrados:
        raise RuntimeError(
            "La medición anterior requiere ausencia de índices nuevos: "
            + ", ".join(sorted(encontrados))
        )
    if fase == "despues":
        faltantes = candidatos - encontrados.keys()
        invalidos = [nombre for nombre, estado in encontrados.items()
                    if not all(estado)]
        if faltantes or invalidos:
            raise RuntimeError(
                f"Índices faltantes: {sorted(faltantes)}; "
                f"índices inválidos: {sorted(invalidos)}"
            )


def escenarios():
    regiones = obtener_regiones()
    maule = next(
        (r for r in regiones if str(r["nombre_region"]).strip().casefold() == "maule"),
        None,
    )
    if maule is None:
        raise RuntimeError("No se encontró la región del Maule.")
    id_maule = maule["id_region"]
    return [
        ("Q1_nacional", lambda: obtener_evolucion()),
        ("Q1_maule", lambda: obtener_evolucion(id_maule)),
        ("Q2_nacional", lambda: obtener_causas()),
        ("Q2_maule_2016", lambda: obtener_causas(id_maule, 2016)),
        ("Q3_nacional", lambda: obtener_coincidencias()),
        ("Q3_maule_2016", lambda: obtener_coincidencias(id_maule, 2016)),
        ("Q4_nacional", lambda: obtener_vegetacion()),
        ("Q4_maule_2016", lambda: obtener_vegetacion(id_maule, 2016)),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fase", choices=("antes", "despues"))
    args = parser.parse_args()
    salida = SALIDA / args.fase
    if salida.exists() and any(salida.iterdir()):
        raise RuntimeError(
            f"La carpeta {salida} ya tiene archivos. No se sobrescriben mediciones: "
            "renómbrala manualmente si quieres repetir la comparación."
        )
    salida.mkdir(parents=True, exist_ok=True)

    with BASE_DATOS.cursor() as cursor:
        cursor.execute("SET statement_timeout = '20000ms'")
        cursor.execute("SHOW server_version")
        postgres_version = cursor.fetchone()[0]

    inventario_inicial = listar_indices()
    candidatos = {
        "idx_incendio_comuna_fecha",
        "idx_foco_calor_comuna_fecha",
        "idx_incendio_fecha",
    }
    verificar_indices(candidatos, args.fase)

    resumen = []
    for nombre, funcion in escenarios():
        print(f"Midiendo {args.fase}: {nombre}", flush=True)
        sql, parametros, filas = capturar(funcion)
        planes = [analizar(sql, parametros) for _ in range(REPETICIONES)]
        tiempos = [plan["Execution Time"] for plan in planes]
        tiempos_plan = [plan["Planning Time"] for plan in planes]
        detalle = {
            "escenario": nombre,
            "fase": args.fase,
            "parametros": parametros,
            "sql": sql,
            "filas_resultado": len(filas),
            "resultados": filas,
            "huella_resultados": huella(filas),
            "planes": planes,
        }
        (salida / f"{nombre}.json").write_text(
            json.dumps(detalle, ensure_ascii=False, indent=2, default=valor_json),
            encoding="utf-8",
        )
        resumen.append({
            "escenario": nombre,
            "filas_resultado": len(filas),
            "ejecucion_mediana_ms": round(statistics.median(tiempos), 3),
            "planificacion_mediana_ms": round(statistics.median(tiempos_plan), 3),
            "ejecuciones_ms": "; ".join(f"{t:.3f}" for t in tiempos),
            "huella_resultados": huella(filas),
        })
        print(f"  Mediana: {statistics.median(tiempos):.3f} ms")

    if resumen:
        with (salida / "resumen.csv").open("w", newline="", encoding="utf-8-sig") as archivo:
            writer = csv.DictWriter(archivo, fieldnames=list(resumen[0].keys()))
            writer.writeheader()
            writer.writerows(resumen)

    with (salida / "indices.csv").open("w", newline="", encoding="utf-8-sig") as archivo:
        writer = csv.writer(archivo)
        writer.writerow(("tabla", "indice", "definicion"))
        writer.writerows(inventario_inicial)
    (salida / "metadatos.json").write_text(
        json.dumps({"fase": args.fase, "postgres_version": postgres_version,
                    "registrado_en": datetime.now().astimezone().isoformat(),
                    "repeticiones": REPETICIONES}, indent=2),
        encoding="utf-8",
    )
    print(f"\nMediciones de {args.fase} guardadas en: {salida}")


if __name__ == "__main__":
    main()
