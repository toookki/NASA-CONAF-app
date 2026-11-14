from django.db import connections


def ejecutar_consulta(sql, parametros=None):
    """Ejecuta una consulta y retorna los resultados como diccionarios."""
    with connections["incendios"].cursor() as cursor:
        cursor.execute(sql, parametros or [])
        columnas = [col[0] for col in cursor.description]

        return [
            dict(zip(columnas, fila))
            for fila in cursor.fetchall()
        ]


def obtener_regiones():
    """Obtiene las regiones disponibles para el filtro."""
    sql = """
        SELECT id_region, nombre_region
        FROM electromaquinas.region
        ORDER BY nombre_region;
    """
    return ejecutar_consulta(sql)


def obtener_evolucion(region_id=None):
    """Obtiene estadísticas por temporada para una región o todo Chile."""

    filtro = "WHERE p.id_region = %s" if region_id is not None else ""
    parametros = [region_id] if region_id is not None else []

    sql = f"""
        WITH incendios_temporada AS (
            SELECT
                EXTRACT(
                    YEAR FROM i.fecha - INTERVAL '6 months'
                )::integer AS temporada_inicio,
                COUNT(*) AS total_incendios,
                SUM(i.superficie_total_ha) AS superficie_ha
            FROM electromaquinas.incendio i
            JOIN electromaquinas.comuna c
                ON i.id_comuna = c.id_comuna
            JOIN electromaquinas.provincia p
                ON c.id_provincia = p.id_provincia
            {filtro}
            GROUP BY temporada_inicio
        ),
        focos_temporada AS (
            SELECT
                EXTRACT(
                    YEAR FROM f.acq_date - INTERVAL '6 months'
                )::integer AS temporada_inicio,
                COUNT(*) AS total_focos
            FROM electromaquinas.foco_calor f
            JOIN electromaquinas.comuna c
                ON f.id_comuna = c.id_comuna
            JOIN electromaquinas.provincia p
                ON c.id_provincia = p.id_provincia
            {filtro}
            GROUP BY temporada_inicio
        )
        SELECT
            COALESCE(
                i.temporada_inicio,
                f.temporada_inicio
            ) AS temporada_inicio,
            COALESCE(i.total_incendios, 0) AS total_incendios,
            COALESCE(i.superficie_ha, 0) AS superficie_ha,
            COALESCE(f.total_focos, 0) AS total_focos
        FROM incendios_temporada i
        FULL OUTER JOIN focos_temporada f
            ON i.temporada_inicio = f.temporada_inicio
        ORDER BY temporada_inicio;
    """

    return ejecutar_consulta(sql, parametros * 2)

def obtener_causas(region_id=None, temporada=None):
    """Resume incendios por causa, región y temporada."""
    from datetime import date

    condiciones = []
    parametros = []

    if region_id is not None:
        condiciones.append("p.id_region = %s")
        parametros.append(region_id)

    if temporada is not None:
        condiciones.append(
            "i.fecha >= %s AND i.fecha < %s"
        )
        parametros.extend([
            date(temporada, 7, 1),
            date(temporada + 1, 7, 1),
        ])

    filtro = (
        "WHERE " + " AND ".join(condiciones)
        if condiciones else ""
    )

    sql = f"""
        WITH resumen_causas AS (
            SELECT
                COALESCE(
                    NULLIF(BTRIM(i.causa::text), ''),
                    'Sin especificar'
                ) AS causa,
                COUNT(*) AS total_incendios,
                COALESCE(SUM(i.superficie_total_ha), 0)::numeric AS superficie_ha
            FROM electromaquinas.incendio i
            JOIN electromaquinas.comuna c
                ON i.id_comuna = c.id_comuna
            JOIN electromaquinas.provincia p
                ON c.id_provincia = p.id_provincia
            {filtro}
            GROUP BY 1
        )
        SELECT
            causa,
            total_incendios,
            superficie_ha,
            ROUND(
                100.0 * total_incendios
                / NULLIF(SUM(total_incendios) OVER (), 0),
                2
            ) AS porcentaje
        FROM resumen_causas
        ORDER BY total_incendios DESC, causa;
    """

    return ejecutar_consulta(sql, parametros)