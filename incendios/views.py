from django.http import HttpResponseBadRequest
from django.shortcuts import render

from .consultas import obtener_causas, obtener_evolucion, obtener_regiones

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