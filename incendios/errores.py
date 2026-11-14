"""Respuesta controlada ante indisponibilidad de PostgreSQL."""

import logging
from functools import wraps

from django.db import InterfaceError, OperationalError
from django.shortcuts import render

logger = logging.getLogger(__name__)


def manejar_errores_bd(vista):
    """Transforma fallas operativas de la BD en HTTP 503 sin exponer detalles.

    No captura errores de programación (por ejemplo SQL mal formado): esos
    deben detectarse y corregirse, no ocultarse como caídas del servidor.
    """
    @wraps(vista)
    def protegida(request, *args, **kwargs):
        try:
            return vista(request, *args, **kwargs)
        except (OperationalError, InterfaceError):
            logger.exception("PostgreSQL no disponible en %s", request.path)
            respuesta = render(
                request,
                "incendios/error_base_datos.html",
                status=503,
            )
            respuesta["Cache-Control"] = "no-store"
            return respuesta

    return protegida
