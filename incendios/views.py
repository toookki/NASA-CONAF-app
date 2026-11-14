from django.http import HttpResponseBadRequest
from django.shortcuts import render

from .consultas import (
    obtener_causas,
    obtener_coincidencias,
    obtener_evolucion,
    obtener_regiones,
)

def dashboard(request):
    regiones = obtener_regiones()

    region_param = request.GET.get("region", "")
    ids_validos = {str(r["id_region"]) for r in regiones}

    if region_param and region_param not in ids_validos:
        return HttpResponseBadRequest("La región seleccionada no es válida.")

    region_id = int(region_param) if region_param else None
    resultados = obtener_evolucion(region_id)

    temporadas = []
    for fila in resultados:
        inicio = fila["temporada_inicio"]

        temporadas.append({
            "nombre": f"{inicio}-{inicio + 1}",
            "incendios": fila["total_incendios"],
            "focos": fila["total_focos"],
            "superficie": float(fila["superficie_ha"]),
        })

    totales = {
        "incendios": sum(t["incendios"] for t in temporadas),
        "focos": sum(t["focos"] for t in temporadas),
        "superficie": sum(t["superficie"] for t in temporadas),
    }

    grafico = {
        "etiquetas": [t["nombre"] for t in temporadas],
        "superficie": [t["superficie"] for t in temporadas],
    }

    contexto = {
        "regiones": regiones,
        "region_seleccionada": region_id,
        "temporadas": temporadas,
        "totales": totales,
        "grafico": grafico,
    }

    return render(request, "incendios/dashboard.html", contexto)

def causas(request):
    regiones = obtener_regiones()

    region_param = request.GET.get("region", "")
    temporada_param = request.GET.get("temporada", "")

    ids_validos = {str(r["id_region"]) for r in regiones}
    anios_validos = {str(anio) for anio in range(2014, 2019)}

    if region_param and region_param not in ids_validos:
        return HttpResponseBadRequest("Región no válida.")

    if temporada_param and temporada_param not in anios_validos:
        return HttpResponseBadRequest("Temporada no válida.")

    region_id = int(region_param) if region_param else None
    temporada = int(temporada_param) if temporada_param else None

    resultados = obtener_causas(region_id, temporada)

    datos = [
        {
            "causa": fila["causa"],
            "incendios": fila["total_incendios"],
            "superficie": fila["superficie_ha"],
            "porcentaje": float(fila["porcentaje"]),
        }
        for fila in resultados
    ]

    resumen = {
        "incendios": sum(fila["incendios"] for fila in datos),
        "superficie": sum(fila["superficie"] for fila in datos),
        "causas": len(datos),
    }

    grafico = {
        "etiquetas": [fila["causa"] for fila in datos[:8]],
        "valores": [fila["incendios"] for fila in datos[:8]],
    }

    temporadas = [
        {
            "inicio": anio,
            "nombre": f"{anio}-{anio + 1}",
        }
        for anio in range(2014, 2019)
    ]

    contexto = {
        "regiones": regiones,
        "region_seleccionada": region_id,
        "temporada_seleccionada": temporada,
        "temporadas": temporadas,
        "datos": datos,
        "resumen": resumen,
        "grafico": grafico,
    }

    return render(request, "incendios/causas.html", contexto)

def coincidencias(request):
    """Muestra estadísticas de coincidencias NASA-CONAF."""
    regiones = obtener_regiones()

    region_param = request.GET.get("region", "")
    temporada_param = request.GET.get("temporada", "")

    ids_validos = {str(r["id_region"]) for r in regiones}
    anios_validos = {str(anio) for anio in range(2014, 2019)}

    if region_param and region_param not in ids_validos:
        return HttpResponseBadRequest("Región no válida.")

    if temporada_param and temporada_param not in anios_validos:
        return HttpResponseBadRequest("Temporada no válida.")

    region_id = int(region_param) if region_param else None
    temporada = int(temporada_param) if temporada_param else None

    resultados = obtener_coincidencias(region_id, temporada)

    datos = []

    for fila in resultados:
        inicio = fila["temporada_inicio"]

        datos.append({
            "temporada": f"{inicio}-{inicio + 1}",
            "incendios": fila["total_incendios"],
            "coincidentes": fila["incendios_coincidentes"],
            "sin_coincidencia": fila["incendios_sin_coincidencia"],
            "vinculos": fila["total_vinculos"],
            "focos_unicos": fila["focos_unicos_temporada"],
            "porcentaje": fila["porcentaje_coincidencia"],
        })

    total_incendios = sum(f["incendios"] for f in datos)
    total_coincidentes = sum(f["coincidentes"] for f in datos)

    resumen = {
        "incendios": total_incendios,
        "coincidentes": total_coincidentes,
        "sin_coincidencia": total_incendios - total_coincidentes,
        "vinculos": sum(f["vinculos"] for f in datos),
        "focos_unicos": (
            resultados[0]["focos_unicos"] if resultados else 0
        ),
        "porcentaje": (
            100 * total_coincidentes / total_incendios
            if total_incendios else 0
        ),
    }

    grafico = {
        "etiquetas": [f["temporada"] for f in datos],
        "coincidentes": [f["coincidentes"] for f in datos],
        "sin_coincidencia": [
            f["sin_coincidencia"] for f in datos
        ],
    }

    temporadas = [
        {
            "inicio": anio,
            "nombre": f"{anio}-{anio + 1}",
        }
        for anio in range(2014, 2019)
    ]

    contexto = {
        "regiones": regiones,
        "region_seleccionada": region_id,
        "temporada_seleccionada": temporada,
        "temporadas": temporadas,
        "datos": datos,
        "resumen": resumen,
        "grafico": grafico,
    }

    return render(
        request,
        "incendios/coincidencias.html",
        contexto,
    )