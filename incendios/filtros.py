"""Validación y opciones de los filtros compartidos del dashboard."""

ANIOS_TEMPORADA = range(2014, 2019)


class FiltroInvalido(ValueError):
    """Indica que un filtro recibido desde la interfaz no es válido."""


def validar_filtros(request, regiones, *, incluir_temporada=True):
    """Valida los filtros de GET y devuelve (region_id, temporada).

    Los identificadores de región se contrastan con los registros disponibles
    y los años con las temporadas cubiertas por el proyecto.
    """
    region_param = request.GET.get("region", "")
    ids_validos = {str(region["id_region"]) for region in regiones}

    if region_param and region_param not in ids_validos:
        mensaje = (
            "Región no válida."
            if incluir_temporada
            else "La región seleccionada no es válida."
        )
        raise FiltroInvalido(mensaje)

    region_id = int(region_param) if region_param else None

    if not incluir_temporada:
        return region_id, None

    temporada_param = request.GET.get("temporada", "")
    anios_validos = {str(anio) for anio in ANIOS_TEMPORADA}

    if temporada_param and temporada_param not in anios_validos:
        raise FiltroInvalido("Temporada no válida.")

    temporada = int(temporada_param) if temporada_param else None
    return region_id, temporada


def opciones_temporadas():
    """Construye las opciones de temporadas para los formularios HTML."""
    return [
        {"inicio": anio, "nombre": f"{anio}-{anio + 1}"}
        for anio in ANIOS_TEMPORADA
    ]


def contexto_filtros(regiones, region_id, temporada):
    """Contexto común de las vistas con filtros de región y temporada."""
    return {
        "regiones": regiones,
        "region_seleccionada": region_id,
        "temporada_seleccionada": temporada,
        "temporadas": opciones_temporadas(),
    }
