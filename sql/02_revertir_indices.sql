-- Opcional: eliminar únicamente los índices definidos en 01_crear_indices.sql.
-- Los DROP CONCURRENTLY deben ejecutarse fuera de una transacción.
-- No ejecutar si otra aplicación ya depende de alguno de ellos.
DROP INDEX CONCURRENTLY IF EXISTS electromaquinas.idx_incendio_fecha;
DROP INDEX CONCURRENTLY IF EXISTS electromaquinas.idx_foco_calor_comuna_fecha;
DROP INDEX CONCURRENTLY IF EXISTS electromaquinas.idx_incendio_comuna_fecha;

ANALYZE electromaquinas.incendio;
ANALYZE electromaquinas.foco_calor;
