"""Inspecciona, crea o revierte los tres índices de optimización SQL.

Comandos, desde la raíz del repositorio:
    py -m scripts.gestionar_indices estado
    py -m scripts.gestionar_indices crear
    py -m scripts.gestionar_indices revertir

Para ejecutar DDL se requieren --confirmar y una confirmación interactiva.
Solo actúa en la base cc3201 y el esquema electromaquinas.
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

from django.db import connections  # noqa: E402

BASE_ESPERADA = "cc3201"
ESQUEMA = "electromaquinas"
RUTAS = {
    "crear": RAIZ / "sql" / "01_crear_indices.sql",
    "revertir": RAIZ / "sql" / "02_revertir_indices.sql",
}

# Definiciones esperadas: nunca confiar solo en que coincida el nombre.
INDICES = {
    "idx_incendio_comuna_fecha": (
        "incendio",
        "CREATE INDEX idx_incendio_comuna_fecha "
        "ON electromaquinas.incendio USING btree (id_comuna, fecha)",
    ),
    "idx_foco_calor_comuna_fecha": (
        "foco_calor",
        "CREATE INDEX idx_foco_calor_comuna_fecha "
        "ON electromaquinas.foco_calor USING btree (id_comuna, acq_date)",
    ),
    "idx_incendio_fecha": (
        "incendio",
        "CREATE INDEX idx_incendio_fecha "
        "ON electromaquinas.incendio USING btree (fecha)",
    ),
}


def cargar_instrucciones(ruta: Path) -> list[str]:
    """Lee el SQL versionado que define el experimento."""
    lineas = [
        linea for linea in ruta.read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.lstrip().startswith("--")
    ]
    instrucciones = [
        fragmento.strip() for fragmento in "\n".join(lineas).split(";")
        if fragmento.strip()
    ]
    # Las sentencias SQL permitidas se obtienen de las definiciones exactas
    # de los tres índices. Ni el nombre ni la tabla pueden cambiar por error.
    creacion = []
    reversion = []
    for nombre, (tabla, definicion) in INDICES.items():
        columnas = definicion.split("USING btree (", 1)[1].rstrip(")")
        creacion.append(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {nombre} "
            f"ON {ESQUEMA}.{tabla} ({columnas})"
        )
        reversion.append(f"DROP INDEX CONCURRENTLY IF EXISTS {ESQUEMA}.{nombre}")
    mantenimiento = [
        f"ANALYZE {ESQUEMA}.incendio",
        f"ANALYZE {ESQUEMA}.foco_calor",
    ]
    esperadas = creacion + mantenimiento if ruta.name.startswith("01_") else reversion + mantenimiento
    normalizar = lambda s: " ".join(s.split()).casefold()
    if sorted(map(normalizar, instrucciones)) != sorted(map(normalizar, esperadas)):
        raise RuntimeError(
            f"El SQL de {ruta.name} no corresponde al conjunto cerrado de "
            "instrucciones aprobado. No se ejecutará."
        )
    return instrucciones


def identidad(db) -> tuple[str, str]:
    with db.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_user")
        base, usuario = cursor.fetchone()
    print(f"Base de datos remota: {base} | Usuario PostgreSQL: {usuario}")
    print(f"Esquema que se inspecciona: {ESQUEMA}")
    if base != BASE_ESPERADA:
        raise RuntimeError(
            f"Se esperaba la base {BASE_ESPERADA!r}, no {base!r}. "
            "Operación cancelada para proteger otras bases de datos."
        )
    return base, usuario


def obtener_estado(db) -> dict[str, dict]:
    """Inspecciona todo objeto con los nombres previstos en el esquema destino."""
    sql = """
        SELECT ic.relname, ic.relkind, tc.relname,
               ix.indisvalid, ix.indisready, ix.indisunique, ix.indisprimary,
               pg_get_indexdef(ic.oid)
        FROM pg_class ic
        JOIN pg_namespace n ON n.oid = ic.relnamespace
        LEFT JOIN pg_index ix ON ix.indexrelid = ic.oid
        LEFT JOIN pg_class tc ON tc.oid = ix.indrelid
        WHERE n.nspname = %s
          AND ic.relname = ANY(%s)
    """
    with db.cursor() as cursor:
        cursor.execute(sql, [ESQUEMA, list(INDICES)])
        filas = cursor.fetchall()
    return {
        nombre: {
            "tipo": tipo, "tabla": tabla, "valido": valido,
            "listo": listo, "unico": unico, "primario": primario,
            "definicion": definicion,
        }
        for nombre, tipo, tabla, valido, listo, unico, primario, definicion in filas
    }


def validar_definiciones(estado: dict[str, dict]) -> None:
    for nombre, encontrado in estado.items():
        tabla, definicion = INDICES[nombre]
        actual = encontrado["definicion"] or ""
        if (encontrado["tipo"] != "i"
                or encontrado["tabla"] != tabla
                or encontrado["unico"]
                or encontrado["primario"]
                or " ".join(actual.split()) != " ".join(definicion.split())):
            raise RuntimeError(
                f"El objeto {ESQUEMA}.{nombre} existe pero no coincide "
                "exactamente con la definición del proyecto. "
                "NO se modificará ni eliminará automáticamente."
            )


def mostrar_estado(estado: dict[str, dict]) -> None:
    print("\nÍndices gestionados por este proyecto:")
    for nombre in INDICES:
        encontrado = estado.get(nombre)
        if encontrado is None:
            print(f"  {nombre}: ausente")
        else:
            print(
                f"  {nombre}: válido={encontrado['valido']}, "
                f"listo={encontrado['listo']}"
            )
            print(f"    {encontrado['definicion']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("accion", choices=("estado", "crear", "revertir"))
    parser.add_argument("--confirmar", action="store_true")
    args = parser.parse_args()

    if args.accion != "estado":
        instrucciones = cargar_instrucciones(RUTAS[args.accion])
        print(f"Archivo: {RUTAS[args.accion].relative_to(RAIZ)}")
        for n, instruccion in enumerate(instrucciones, 1):
            print(f"  {n}. {instruccion}")
        if not args.confirmar:
            print("\nVista previa: no se ha conectado ni modificado PostgreSQL.")
            print("Utiliza --confirmar solamente si tienes autorización.")
            return

    db = connections["incendios"]
    try:
        identidad(db)
        estado = obtener_estado(db)
        validar_definiciones(estado)
        mostrar_estado(estado)

        if args.accion == "estado":
            print("\nSolo lectura: no se han realizado modificaciones.")
            return

        if args.accion == "crear" and all(
            nombre in estado and estado[nombre]["valido"] and estado[nombre]["listo"]
            for nombre in INDICES
        ):
            print("\nTodos los índices ya existen y son válidos. Nada que crear.")
            return
        if args.accion == "crear" and any(
            not e["valido"] or not e["listo"] for e in estado.values()
        ):
            raise RuntimeError(
                "Hay índices inválidos o incompletos. "
                "No se vuelve a ejecutar CREATE IF NOT EXISTS."
            )
        if args.accion == "revertir" and not estado:
            print("\nNingún índice presente. Nada que revertir.")
            return

        print("\nATENCIÓN: esta acción afecta a la base REMOTA y puede "
              "afectar a otros usuarios del esquema.")
        frase = f"{BASE_ESPERADA}/{ESQUEMA}"
        try:
            entrada = input(f"Para continuar, escribe exactamente {frase}: ").strip()
        except EOFError as error:
            raise RuntimeError("Se requiere confirmación interactiva.") from error
        if entrada != frase:
            print("Confirmación incorrecta. Operación cancelada.")
            return

        if not db.get_autocommit():
            raise RuntimeError("CREATE/DROP INDEX CONCURRENTLY requiere autocommit.")
        with db.cursor() as cursor:
            cursor.execute("SET statement_timeout = '60000ms'")
        for n, instruccion in enumerate(instrucciones, 1):
            print(f"  Ejecutando {n}/{len(instrucciones)}...")
            with db.cursor() as cursor:
                cursor.execute(instruccion)

        nuevo = obtener_estado(db)
        validar_definiciones(nuevo)
        mostrar_estado(nuevo)
        if args.accion == "revertir" and nuevo:
            raise RuntimeError("La reversión terminó, pero aún quedan índices.")
        if args.accion == "crear" and any(
            n not in nuevo or not nuevo[n]["valido"] or not nuevo[n]["listo"]
            for n in INDICES
        ):
            raise RuntimeError("No se crearon correctamente los tres índices.")
        print("\nOperación completada.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
