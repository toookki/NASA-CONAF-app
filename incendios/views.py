from django.http import HttpResponseBadRequest
from django.shortcuts import render

from .consultas import obtener_evolucion, obtener_regiones


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
