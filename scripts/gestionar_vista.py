"""Inspecciona, crea y revierte la vista territorial de incendios.

Desde la raíz del proyecto:
    py -m scripts.gestionar_vista estado
    py -m scripts.gestionar_vista crear --confirmar
    py -m scripts.gestionar_vista revertir --confirmar

La creación y la reversión requieren confirmación interactiva. No se modifican
índices ni filas de las tablas originales.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.db import connections, transaction  # noqa: E402

BASE = "cc3201"
ESQUEMA = "electromaquinas"
NOMBRE = "v_incendios_region"
MARCA = "NASA-CONAF:v_incendios_region:v1"
COLUMNAS = (
    "id_incendio", "id_comuna", "fecha", "causa",
    "superficie_total_ha", "id_region",
)
ARCHIVOS = {
    "crear": RAIZ / "sql" / "03_crear_vista.sql",
    "revertir": RAIZ / "sql" / "04_revertir_vista.sql",
}


def cargar_sql(accion: str) -> list[str]:
    """Valida que el archivo contenga solo el DDL previsto para esta vista."""
    contenido = ARCHIVOS[accion].read_text(encoding="utf-8")
    lineas = [
        linea for linea in contenido.splitlines()
        if linea.strip() and not linea.lstrip().startswith("--")
    ]
    sentencias = [
        fragmento.strip() for fragmento in "\n".join(lineas).split(";")
        if fragmento.strip()
    ]
    normalizadas = [" ".join(sentencia.split()) for sentencia in sentencias]
    if accion == "crear":
        if (len(sentencias) != 2
                or not normalizadas[0].startswith(
                    f"CREATE VIEW {ESQUEMA}.{NOMBRE} AS SELECT "
                )
                or normalizadas[1] != (
                    f"COMMENT ON VIEW {ESQUEMA}.{NOMBRE} IS '{MARCA}'"
                )):
            raise RuntimeError("SQL de creación inesperado; no se ejecutará.")
    elif normalizadas != [f"DROP VIEW {ESQUEMA}.{NOMBRE} RESTRICT"]:
        raise RuntimeError("SQL de reversión inesperado; no se ejecutará.")
    return sentencias


def identificar_destino(db) -> None:
    with db.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_user")
        base, usuario = cursor.fetchone()
    print(f"Base de datos: {base} | Usuario PostgreSQL: {usuario}")
    print(f"Esquema: {ESQUEMA}")
    if base != BASE:
        raise RuntimeError(f"Destino incorrecto: se esperaba la base {BASE!r}.")


def obtener_estado(db):
    sql = """
        SELECT c.relkind, obj_description(c.oid, 'pg_class'),
               array_agg(a.attname ORDER BY a.attnum)
                 FILTER (WHERE a.attnum > 0 AND NOT a.attisdropped)
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        LEFT JOIN pg_attribute AS a ON a.attrelid = c.oid
        WHERE n.nspname = %s AND c.relname = %s
        GROUP BY c.oid, c.relkind;
    """
    with db.cursor() as cursor:
        cursor.execute(sql, [ESQUEMA, NOMBRE])
        return cursor.fetchone()


def comprobar_estado(estado) -> None:
    """Protege objetos ajenos aunque reutilicen el mismo nombre."""
    if estado is None:
        return
    tipo, marca, columnas = estado
    if tipo != "v" or marca != MARCA or tuple(columnas) != COLUMNAS:
        raise RuntimeError(
            f"El objeto {ESQUEMA}.{NOMBRE} no tiene la definición "
            "identificada por el proyecto. No se modificará."
        )


def mostrar_estado(estado) -> None:
    if estado is None:
        print(f"Vista {ESQUEMA}.{NOMBRE}: ausente")
    else:
        print(f"Vista {ESQUEMA}.{NOMBRE}: presente y reconocida")
        print("Columnas: " + ", ".join(estado[2]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("accion", choices=("estado", "crear", "revertir"))
    parser.add_argument("--confirmar", action="store_true")
    args = parser.parse_args()

    if args.accion != "estado":
        sentencias = cargar_sql(args.accion)
        print(f"Archivo: {ARCHIVOS[args.accion].relative_to(RAIZ)}")
        for numero, sentencia in enumerate(sentencias, 1):
            print(f"  {numero}. {' '.join(sentencia.split())}")
        if not args.confirmar:
            print("\nSolo vista previa: no se ha conectado a PostgreSQL.")
            return

    db = connections["incendios"]
    try:
        identificar_destino(db)
        estado = obtener_estado(db)
        comprobar_estado(estado)
        mostrar_estado(estado)

        if args.accion == "estado":
            print("Solo lectura: sin cambios en PostgreSQL.")
            return
        if args.accion == "revertir":
            print(
                "AVISO: Q2-Q4 usan esta vista; para revertir la funcionalidad "
                "también debes restaurar el código anterior de consultas.py."
            )
        if args.accion == "crear" and estado is not None:
            print("La vista ya existe. No hay cambios que realizar.")
            return
        if args.accion == "revertir" and estado is None:
            print("La vista está ausente. No hay cambios que realizar.")
            return

        try:
            respuesta = input(
                f"Confirma la operación escribiendo {BASE}/{ESQUEMA}: "
            ).strip()
        except EOFError as error:
            raise RuntimeError("Falta confirmación interactiva.") from error
        if respuesta != f"{BASE}/{ESQUEMA}":
            print("Confirmación incorrecta: operación cancelada.")
            return

        # CREATE VIEW y COMMENT deben aplicarse juntos o revertirse juntos.
        with transaction.atomic(using="incendios"):
            with db.cursor() as cursor:
                for numero, sentencia in enumerate(sentencias, 1):
                    print(f"  Ejecutando {numero}/{len(sentencias)}...")
                    cursor.execute(sentencia)

        nuevo = obtener_estado(db)
        comprobar_estado(nuevo)
        if args.accion == "crear" and nuevo is None:
            raise RuntimeError("La vista no aparece después de crearla.")
        if args.accion == "revertir" and nuevo is not None:
            raise RuntimeError("La vista permanece después de revertirla.")
        mostrar_estado(nuevo)
        print("Operación completada.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
