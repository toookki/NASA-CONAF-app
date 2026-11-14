from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("causas/", views.causas, name="causas"),
    path(
        "coincidencias/",
        views.coincidencias,
        name="coincidencias",
    ),
    path("vegetacion/", views.vegetacion, name="vegetacion"),
]