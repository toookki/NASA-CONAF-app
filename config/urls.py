"""Rutas públicas de la aplicación NASA–CONAF.

No se publica el panel de administración de Django: el dashboard no tiene
operaciones administrativas ni autenticación desde la interfaz.
"""

from django.urls import include, path

urlpatterns = [
    path("", include("incendios.urls")),
]
