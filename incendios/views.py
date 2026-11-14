"""Vistas de las cuatro secciones analíticas de NASA–CONAF."""

from decimal import Decimal

from django.http import HttpResponseBadRequest
from django.shortcuts import render

from .consultas import (
    obtener_causas,
    obtener_coincidencias,
    obtener_evolucion,
    obtener_regiones,
    obtener_vegetacion,
)
from .errores import manejar_errores_bd
from .filtros import FiltroInvalido, contexto_filtros, validar_filtros


@manejar_errores_bd
def dashboard(request):
    """Muestra la evolución temporal de incendios y focos detectados."""
    regiones = obtener_regiones()

    try:
        region_id, _ = validar_filtros(
            request, regiones, incluir_temporada=False
        )
    except FiltroInvalido as error:
        return HttpResponseBadRequest(str(error))

    resultados = obtener_evolucion(region_id)
    temporadas = []

    for fila in resultados:
        inicio = fila["temporada_inicio"]
        temporadas.append({
            "nombre": f"{inicio}-{inicio + 1}",
            "incendios": fila["total_incendios"],
            "focos": fila["total_focos"],
            "superficie": fila["superficie_ha"],
        })

    totales = {
        "incendios": sum(fila["incendios"] for fila in temporadas),
        "focos": sum(fila["focos"] for fila in temporadas),
        "superficie": sum(
            (fila["superficie"] for fila in temporadas), Decimal("0")
        ),
    }

    grafico = {
        "etiquetas": [fila["nombre"] for fila in temporadas],
        "superficie": [float(fila["superficie"]) for fila in temporadas],
    }

    contexto = {
        "regiones": regiones,
        "region_seleccionada": region_id,
        "temporadas": temporadas,
        "totales": totales,
        "grafico": grafico,
    }
    return render(request, "incendios/dashboard.html", contexto)


@manejar_errores_bd
def causas(request):
    """Presenta las causas CONAF por región y temporada."""
    regiones = obtener_regiones()

    try:
        region_id, temporada = validar_filtros(request, regiones)
    except FiltroInvalido as error:
        return HttpResponseBadRequest(str(error))

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
        "superficie": sum(
            (fila["superficie"] for fila in datos), Decimal("0")
        ),
        "causas": len(datos),
    }
    grafico = {
        "etiquetas": [fila["causa"] for fila in datos[:8]],
        "valores": [fila["incendios"] for fila in datos[:8]],
    }

    contexto = contexto_filtros(regiones, region_id, temporada)
    contexto.update({
        "datos": datos,
        "resumen": resumen,
        "grafico": grafico,
    })
    return render(request, "incendios/causas.html", contexto)


@manejar_errores_bd
def coincidencias(request):
    """Analiza relaciones registradas entre incendios y focos NASA."""
    regiones = obtener_regiones()

    try:
        region_id, temporada = validar_filtros(request, regiones)
    except FiltroInvalido as error:
        return HttpResponseBadRequest(str(error))

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

    total_incendios = sum(fila["incendios"] for fila in datos)
    total_coincidentes = sum(fila["coincidentes"] for fila in datos)

    resumen = {
        "incendios": total_incendios,
        "coincidentes": total_coincidentes,
        "sin_coincidencia": total_incendios - total_coincidentes,
        "vinculos": sum(fila["vinculos"] for fila in datos),
        # La consulta SQL replica el conteo global por CROSS JOIN.
        # No se suman los focos únicos de cada temporada.
        "focos_unicos": resultados[0]["focos_unicos"] if resultados else 0,
        "porcentaje": (
            Decimal("100") * total_coincidentes / total_incendios
            if total_incendios else Decimal("0")
        ),
    }
    grafico = {
        "etiquetas": [fila["temporada"] for fila in datos],
        "coincidentes": [fila["coincidentes"] for fila in datos],
        "sin_coincidencia": [fila["sin_coincidencia"] for fila in datos],
    }

    contexto = contexto_filtros(regiones, region_id, temporada)
    contexto.update({
        "datos": datos,
        "resumen": resumen,
        "grafico": grafico,
    })
    return render(request, "incendios/coincidencias.html", contexto)


@manejar_errores_bd
def vegetacion(request):
    """Resume superficies de vegetación afectada por incendios CONAF."""
    regiones = obtener_regiones()

    try:
        region_id, temporada = validar_filtros(request, regiones)
    except FiltroInvalido as error:
        return HttpResponseBadRequest(str(error))

    resultados = obtener_vegetacion(region_id, temporada)
    datos = [
        {
            "tipo": fila["tipo_nombre"],
            "incendios": fila["incendios_asociados"],
            "registros": fila["registros_afectacion"],
            "superficie": fila["superficie_ha"],
            "porcentaje": fila["porcentaje_superficie"],
        }
        for fila in resultados
    ]

    resumen = {
        "superficie": sum(
            (fila["superficie"] for fila in datos), Decimal("0")
        ),
        "incendios": (
            resultados[0]["incendios_con_vegetacion"] if resultados else 0
        ),
        "registros": sum(fila["registros"] for fila in datos),
        "tipos": len(datos),
    }
    grafico = {
        "etiquetas": [fila["tipo"] for fila in datos],
        "superficies": [float(fila["superficie"]) for fila in datos],
    }

    contexto = contexto_filtros(regiones, region_id, temporada)
    contexto.update({
        "datos": datos,
        "resumen": resumen,
        "grafico": grafico,
    })
    return render(request, "incendios/vegetacion.html", contexto)
