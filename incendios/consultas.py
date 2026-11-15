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
        condiciones.append("i.id_region = %s")
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
            FROM electromaquinas.v_incendios_region i
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

def obtener_coincidencias(region_id=None, temporada=None):
    """Analiza coincidencias NASA-CONAF por temporada."""
    from datetime import date

    condiciones = []
    parametros = []

    if region_id is not None:
        condiciones.append("i.id_region = %s")
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
        WITH incendios_filtrados AS (
            SELECT
                i.id_incendio,
                EXTRACT(
                    YEAR FROM i.fecha - INTERVAL '6 months'
                )::integer AS temporada_inicio
            FROM electromaquinas.v_incendios_region i
            {filtro}
        ),
        relaciones AS (
            SELECT
                i.id_incendio,
                i.temporada_inicio,
                co.id_foco
            FROM incendios_filtrados i
            LEFT JOIN electromaquinas.coincide co
                ON i.id_incendio = co.id_incendio
        ),
        resumen_temporada AS (
            SELECT
                temporada_inicio,
                COUNT(DISTINCT id_incendio) AS total_incendios,
                COUNT(DISTINCT id_incendio)
                    FILTER (WHERE id_foco IS NOT NULL)
                    AS incendios_coincidentes,
                COUNT(id_foco) AS total_vinculos,
                COUNT(DISTINCT id_foco) AS focos_unicos_temporada
            FROM relaciones
            GROUP BY temporada_inicio
        ),
        resumen_global AS (
            SELECT
                COUNT(DISTINCT id_foco) AS focos_unicos
            FROM relaciones
        )
        SELECT
            r.temporada_inicio,
            r.total_incendios,
            r.incendios_coincidentes,
            r.total_incendios - r.incendios_coincidentes
                AS incendios_sin_coincidencia,
            r.total_vinculos,
            r.focos_unicos_temporada,
            g.focos_unicos,
            ROUND(
                100.0 * r.incendios_coincidentes
                / NULLIF(r.total_incendios, 0),
                2
            ) AS porcentaje_coincidencia
        FROM resumen_temporada r
        CROSS JOIN resumen_global g
        ORDER BY r.temporada_inicio;
    """

    return ejecutar_consulta(sql, parametros)

def obtener_vegetacion(region_id=None, temporada=None):
    """Resume la superficie quemada por tipo de vegetación."""
    from datetime import date

    condiciones = []
    parametros = []

    if region_id is not None:
        condiciones.append("i.id_region = %s")
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
        WITH vegetacion_filtrada AS (
            SELECT
                i.id_incendio,
                a.id_vegetacion,
                v.tipo_nombre,
                a.superficie_quemada_ha
            FROM electromaquinas.v_incendios_region i
            JOIN electromaquinas.afecta a
                ON i.id_incendio = a.id_incendio
            JOIN electromaquinas.tipo_vegetacion v
                ON a.id_vegetacion = v.id_vegetacion
            {filtro}
        ),
        resumen_vegetacion AS (
            SELECT
                id_vegetacion,
                tipo_nombre,
                COUNT(DISTINCT id_incendio)
                    AS incendios_asociados,
                COUNT(*) AS registros_afectacion,
                SUM(superficie_quemada_ha)::numeric
                    AS superficie_ha
            FROM vegetacion_filtrada
            GROUP BY id_vegetacion, tipo_nombre
        ),
        cobertura AS (
            SELECT
                COUNT(DISTINCT id_incendio)
                    AS incendios_con_vegetacion
            FROM vegetacion_filtrada
        )
        SELECT
            r.tipo_nombre,
            r.incendios_asociados,
            r.registros_afectacion,
            r.superficie_ha,
            c.incendios_con_vegetacion,
            ROUND(
                100.0 * r.superficie_ha
                / NULLIF(SUM(r.superficie_ha) OVER (), 0),
                2
            ) AS porcentaje_superficie
        FROM resumen_vegetacion r
        CROSS JOIN cobertura c
        ORDER BY r.superficie_ha DESC, r.tipo_nombre;
    """

    return ejecutar_consulta(sql, parametros)