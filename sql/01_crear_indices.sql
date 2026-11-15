-- Índices candidatos para las consultas Q1–Q4.
-- Ejecutar con scripts/gestionar_indices.py crear --confirmar.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_incendio_comuna_fecha
ON electromaquinas.incendio (id_comuna, fecha);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_foco_calor_comuna_fecha
ON electromaquinas.foco_calor (id_comuna, acq_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_incendio_fecha
ON electromaquinas.incendio (fecha);

-- Actualizar estadísticas para que el optimizador considere los índices nuevos.
ANALYZE electromaquinas.incendio;
ANALYZE electromaquinas.foco_calor;
