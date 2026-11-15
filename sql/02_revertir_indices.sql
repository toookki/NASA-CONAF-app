DROP INDEX CONCURRENTLY IF EXISTS electromaquinas.idx_incendio_fecha;
DROP INDEX CONCURRENTLY IF EXISTS electromaquinas.idx_foco_calor_comuna_fecha;
DROP INDEX CONCURRENTLY IF EXISTS electromaquinas.idx_incendio_comuna_fecha;

ANALYZE electromaquinas.incendio;
ANALYZE electromaquinas.foco_calor;
