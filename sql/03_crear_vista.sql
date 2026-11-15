-- Vista convencional: centraliza la relación territorial de los incendios.
-- No almacena filas ni modifica las tablas de origen.
-- Utilizada por Q2 (causas), Q3 (coincidencias) y Q4 (vegetación).
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
