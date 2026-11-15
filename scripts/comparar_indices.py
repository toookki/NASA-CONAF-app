"""Compara exclusivamente mediciones de consultas antes y después de crear índices.

Uso desde la raíz del proyecto (no requiere conexión PostgreSQL):
    py -m scripts.comparar_indices

Entradas: resultados_sql/optimizacion_indices/{antes,despues}/*.json
Salidas:  resultados_sql/optimizacion_indices/{comparacion.csv,comparacion.md}
"""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RESULTADOS = RAIZ / "resultados_sql" / "optimizacion_indices"
ESCENARIOS = (
    "Q1_nacional", "Q1_maule", "Q2_nacional", "Q2_maule_2016",
    "Q3_nacional", "Q3_maule_2016", "Q4_nacional", "Q4_maule_2016",
)


def leer_plan(fase: str, escenario: str) -> dict:
    archivo = RESULTADOS / fase / f"{escenario}.json"
    if not archivo.is_file():
        raise SystemExit(
            f"No se encontró el archivo requerido: {archivo}\n"
            "Ejecuta primero las mediciones 'antes' y 'despues'."
        )
    try:
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        if datos.get("fase") != fase:
            raise ValueError(f"Fase incorrecta: se esperaba '{fase}'.")
        if len(datos["planes"]) != 3:
            raise ValueError("Cada escenario debe contener exactamente tres planes.")
        for plan in datos["planes"]:
            _ = plan["Execution Time"]
            _ = plan["Plan"]
        _ = datos["resultados"]
        _ = datos["sql"]
        _ = datos["parametros"]
        return datos
    except (ValueError, TypeError, KeyError) as error:
        raise SystemExit(f"Archivo de medición inválido: {archivo} ({error})") from error


def resumen_accesos(nodo: dict) -> tuple[str, str]:
    """Identifica índices y escaneos secuenciales presentes en el plan."""
    indices = set()
    secuenciales = set()

    def visitar(actual: dict) -> None:
        tipo = actual.get("Node Type", "")
        if tipo in {"Index Scan", "Index Only Scan", "Bitmap Index Scan"}:
            indices.add(actual.get("Index Name", "(sin nombre)"))
        if tipo == "Seq Scan":
            secuenciales.add(actual.get("Relation Name", "(sin tabla)"))
        for hijo in actual.get("Plans", []):
            visitar(hijo)

    visitar(nodo)
    return "; ".join(sorted(indices)), "; ".join(sorted(secuenciales))


def mediana(datos: dict) -> float:
    return statistics.median(plan["Execution Time"] for plan in datos["planes"])


def plan_mediano(datos: dict) -> dict:
    return sorted(datos["planes"], key=lambda plan: plan["Execution Time"])[1]["Plan"]


def comparar_escenario(escenario: str) -> dict:
    antes = leer_plan("antes", escenario)
    despues = leer_plan("despues", escenario)

    tiempo_antes = mediana(antes)
    tiempo_despues = mediana(despues)
    acceso_antes, seq_antes = resumen_accesos(plan_mediano(antes))
    acceso_despues, seq_despues = resumen_accesos(plan_mediano(despues))
    plan_antes = plan_mediano(antes)
    plan_despues = plan_mediano(despues)

    return {
        "escenario": escenario,
        "antes_ms": round(tiempo_antes, 3),
        "despues_ms": round(tiempo_despues, 3),
        "mejora_pct": round(100 * (tiempo_antes - tiempo_despues) / tiempo_antes, 2)
        if tiempo_antes > 0 else None,
        "resultados_iguales": antes["resultados"] == despues["resultados"],
        "sql_igual": antes["sql"] == despues["sql"],
        "parametros_iguales": antes["parametros"] == despues["parametros"],
        "filas": len(antes["resultados"]),
        "indices_usados_antes": acceso_antes,
        "indices_usados_despues": acceso_despues,
        "tablas_seq_scan_antes": seq_antes,
        "tablas_seq_scan_despues": seq_despues,
        "bloques_hit_antes": plan_antes.get("Shared Hit Blocks", 0),
        "bloques_hit_despues": plan_despues.get("Shared Hit Blocks", 0),
        "bloques_read_antes": plan_antes.get("Shared Read Blocks", 0),
        "bloques_read_despues": plan_despues.get("Shared Read Blocks", 0),
    }


def main() -> None:
    filas = [comparar_escenario(nombre) for nombre in ESCENARIOS]
    inconsistentes = [
        f["escenario"] for f in filas
        if not all((f["resultados_iguales"], f["sql_igual"], f["parametros_iguales"]))
    ]
    if inconsistentes:
        raise SystemExit(
            "ERROR: difieren los resultados, SQL o parámetros de: "
            + ", ".join(inconsistentes)
            + ". No se generó un informe de comparación válido."
        )

    tabla = [
        "# Comparación de consultas SQL antes y después de crear índices",
        "",
        "Medianas de tres ejecuciones de `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`.",
        "Los tiempos reflejan las condiciones observadas de caché y carga del servidor.",
        "",
        "| Escenario | Antes (ms) | Después (ms) | Mejora | Resultados iguales |",
        "| --- | ---: | ---: | ---: | :---: |",
    ]
    for fila in filas:
        mejora = (
            f'{fila["mejora_pct"]:+.2f}%'
            if fila["mejora_pct"] is not None else "n/d"
        )
        tabla.append(
            f'| {fila["escenario"]} | {fila["antes_ms"]:.2f} | '
            f'{fila["despues_ms"]:.2f} | {mejora} | Sí |'
        )
    tabla.extend([
        "", "## Validación",
        "", "- Los resultados son idénticos fila por fila en los ocho escenarios.",
        "- El texto SQL y los parámetros coinciden entre ambas mediciones.",
        "- `comparacion.csv` identifica los índices y escaneos utilizados en los planes medianos.",
        "- Los cambios porcentuales no prueban por sí solos causalidad: influyen la carga, "
        "la caché y la actualización de estadísticas.",
        "",
    ])

    RESULTADOS.mkdir(parents=True, exist_ok=True)
    with (RESULTADOS / "comparacion.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as archivo:
        writer = csv.DictWriter(archivo, fieldnames=list(filas[0].keys()))
        writer.writeheader()
        writer.writerows(filas)
    contenido = "\n".join(tabla)
    (RESULTADOS / "comparacion.md").write_text(contenido, encoding="utf-8")
    print(contenido)
    print("Comparación válida: los 8 resultados, SQL y parámetros coinciden.")


if __name__ == "__main__":
    main()
