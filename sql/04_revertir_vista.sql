-- La reversión no modifica ni elimina las tablas de origen.
-- RESTRICT impide eliminarla si otras vistas/objetos dependen de ella.
DROP VIEW electromaquinas.v_incendios_region RESTRICT;
