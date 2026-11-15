-- ============================================================================
-- 1. CONSULTA AUXILIAR: LISTADO DE REGIONES
-- ============================================================================
-- Usada para poblar el selector de regiones de la interfaz.
SELECT id_region, nombre_region
FROM electromaquinas.region
ORDER BY nombre_region;


-- ============================================================================
-- 2. CONSULTAS ORIGINALES SIN VISTA
-- ============================================================================
-- Estas son las versiones base utilizadas para medir el efecto de los índices.

-- Q1 | Evolución anual por temporada de incendios y focos NASA
-- Funcion Python: obtener_evolucion() | Variante: region + sin temporada
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
    WHERE p.id_region = %s
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
    WHERE p.id_region = %s
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

-- Q2 | Causas de incendios y superficie total afectada
-- Funcion Python: obtener_causas() | Variante: region + temporada
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
    WHERE p.id_region = %s AND i.fecha >= %s AND i.fecha < %s
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

-- Q3 | Coincidencias NASA–CONAF por temporada
-- Funcion Python: obtener_coincidencias() | Variante: region + temporada
WITH incendios_filtrados AS (
    SELECT
        i.id_incendio,
        EXTRACT(
            YEAR FROM i.fecha - INTERVAL '6 months'
        )::integer AS temporada_inicio
    FROM electromaquinas.incendio i
    JOIN electromaquinas.comuna c
        ON i.id_comuna = c.id_comuna
    JOIN electromaquinas.provincia p
        ON c.id_provincia = p.id_provincia
    WHERE p.id_region = %s AND i.fecha >= %s AND i.fecha < %s
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

-- Q4 | Superficie quemada por tipo de vegetación
-- Funcion Python: obtener_vegetacion() | Variante: region + temporada
WITH vegetacion_filtrada AS (
    SELECT
        i.id_incendio,
        a.id_vegetacion,
        v.tipo_nombre,
        a.superficie_quemada_ha
    FROM electromaquinas.incendio i
    JOIN electromaquinas.afecta a
        ON i.id_incendio = a.id_incendio
    JOIN electromaquinas.tipo_vegetacion v
        ON a.id_vegetacion = v.id_vegetacion
    JOIN electromaquinas.comuna c
        ON i.id_comuna = c.id_comuna
    JOIN electromaquinas.provincia p
        ON c.id_provincia = p.id_provincia
    WHERE p.id_region = %s AND i.fecha >= %s AND i.fecha < %s
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


-- ============================================================================
-- 3. DEFINICIÓN DE LOS TRES ÍNDICES
-- ============================================================================
-- Las siguientes instrucciones son las definiciones exactas de sql/01_crear_indices.sql.
-- Ya se aplicaron sobre electromaquinas; NO ejecutar nuevamente este archivo.
-- CREATE INDEX CONCURRENTLY se ejecuta fuera de bloques de transacción.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_incendio_comuna_fecha
ON electromaquinas.incendio (id_comuna, fecha);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_foco_calor_comuna_fecha
ON electromaquinas.foco_calor (id_comuna, acq_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_incendio_fecha
ON electromaquinas.incendio (fecha);

-- Al crearlos también se ejecutaron ANALYZE incendio y foco_calor.
-- La reversión está en sql/02_revertir_indices.sql.


-- ============================================================================
-- 4. VISTA CONVENCIONAL: v_incendios_region
-- ============================================================================
-- Definición idéntica a sql/03_crear_vista.sql.
-- No materializa resultados: reutiliza los joins territoriales.
-- La reversión está en sql/04_revertir_vista.sql.

CREATE VIEW electromaquinas.v_incendios_region AS
SELECT
    i.id_incendio,
    i.id_comuna,
    i.fecha,
    i.causa,
    i.superficie_total_ha,
    p.id_region
FROM electromaquinas.incendio AS i
JOIN electromaquinas.comuna AS c
    ON i.id_comuna = c.id_comuna
JOIN electromaquinas.provincia AS p
    ON c.id_provincia = p.id_provincia;

-- Identificador para que el gestor solo revierta la vista de este proyecto.
COMMENT ON VIEW electromaquinas.v_incendios_region
IS 'NASA-CONAF:v_incendios_region:v1';


-- ============================================================================
-- 5. CONSULTAS FINALES CON VISTA (EN PRODUCCIÓN DJANGO)
-- ============================================================================
-- Q2, Q3 y Q4 usan v_incendios_region; Q1 conserva el SQL de la sección 2.

-- Q2 final | Causas de incendios y superficie total afectada
-- Funcion Python: obtener_causas() | Parámetros: [id_region, fecha_inicio, fecha_fin]
WITH resumen_causas AS (
    SELECT
        COALESCE(
            NULLIF(BTRIM(i.causa::text), ''),
            'Sin especificar'
        ) AS causa,
        COUNT(*) AS total_incendios,
        COALESCE(SUM(i.superficie_total_ha), 0)::numeric AS superficie_ha
    FROM electromaquinas.v_incendios_region i
    WHERE i.id_region = %s AND i.fecha >= %s AND i.fecha < %s
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

-- Q3 final | Coincidencias NASA–CONAF por temporada
-- Funcion Python: obtener_coincidencias() | Parámetros: [id_region, fecha_inicio, fecha_fin]
WITH incendios_filtrados AS (
    SELECT
        i.id_incendio,
        EXTRACT(
            YEAR FROM i.fecha - INTERVAL '6 months'
        )::integer AS temporada_inicio
    FROM electromaquinas.v_incendios_region i
    WHERE i.id_region = %s AND i.fecha >= %s AND i.fecha < %s
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

-- Q4 final | Superficie quemada por tipo de vegetación
-- Funcion Python: obtener_vegetacion() | Parámetros: [id_region, fecha_inicio, fecha_fin]
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
    WHERE i.id_region = %s AND i.fecha >= %s AND i.fecha < %s
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