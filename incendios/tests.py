"""Pruebas de regresión de las cuatro vistas sin conexión a PostgreSQL."""

from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse


class VistasIncendiosTests(SimpleTestCase):
    """Comprueba rutas, filtros y resultados utilizando datos simulados."""

    def setUp(self):
        regiones = [
            {"id_region": 7, "nombre_region": "Maule"},
            {"id_region": 8, "nombre_region": "Biobío"},
        ]
        respuestas = {
            "obtener_regiones": regiones,
            "obtener_evolucion": [
                {
                    "temporada_inicio": 2016,
                    "total_incendios": 3,
                    "superficie_ha": Decimal("12.50"),
                    "total_focos": 9,
                }
            ],
            "obtener_causas": [
                {
                    "causa": "Incendios intencionales",
                    "total_incendios": 3,
                    "superficie_ha": Decimal("12.50"),
                    "porcentaje": Decimal("100.00"),
                }
            ],
            "obtener_coincidencias": [
                {
                    "temporada_inicio": 2016,
                    "total_incendios": 3,
                    "incendios_coincidentes": 2,
                    "incendios_sin_coincidencia": 1,
                    "total_vinculos": 4,
                    "focos_unicos_temporada": 3,
                    "focos_unicos": 3,
                    "porcentaje_coincidencia": Decimal("66.67"),
                }
            ],
            "obtener_vegetacion": [
                {
                    "tipo_nombre": "Matorral",
                    "incendios_asociados": 2,
                    "registros_afectacion": 2,
                    "superficie_ha": Decimal("12.50"),
                    "incendios_con_vegetacion": 2,
                    "porcentaje_superficie": Decimal("100.00"),
                }
            ],
        }

        self.consultas = {}
        for nombre, respuesta in respuestas.items():
            parche = patch(
                f"incendios.views.{nombre}", return_value=respuesta
            )
            self.consultas[nombre] = parche.start()
            self.addCleanup(parche.stop)

    def test_dashboard_renderiza_y_calcula_totales(self):
        respuesta = self.client.get(reverse("dashboard"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "incendios/dashboard.html")
        self.assertEqual(respuesta.context["totales"]["incendios"], 3)
        self.assertEqual(respuesta.context["totales"]["focos"], 9)
        self.consultas["obtener_evolucion"].assert_called_once_with(None)

    def test_dashboard_recibe_region_valida(self):
        respuesta = self.client.get(reverse("dashboard"), {"region": "7"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["region_seleccionada"], 7)
        self.consultas["obtener_evolucion"].assert_called_once_with(7)

    def test_dashboard_rechaza_region_invalida(self):
        respuesta = self.client.get(reverse("dashboard"), {"region": "999"})

        self.assertEqual(respuesta.status_code, 400)
        self.consultas["obtener_evolucion"].assert_not_called()

    def test_causas_renderiza_y_conserva_superficie_decimal(self):
        respuesta = self.client.get(reverse("causas"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "incendios/causas.html")
        self.assertEqual(
            respuesta.context["resumen"]["superficie"], Decimal("12.50")
        )
        self.consultas["obtener_causas"].assert_called_once_with(None, None)

    def test_causas_aplica_dos_filtros(self):
        respuesta = self.client.get(
            reverse("causas"), {"region": "7", "temporada": "2016"}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.consultas["obtener_causas"].assert_called_once_with(7, 2016)

    def test_coincidencias_no_duplica_incendios(self):
        respuesta = self.client.get(reverse("coincidencias"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "incendios/coincidencias.html")
        resumen = respuesta.context["resumen"]
        self.assertEqual(resumen["incendios"], 3)
        self.assertEqual(resumen["coincidentes"], 2)
        self.assertEqual(resumen["sin_coincidencia"], 1)
        self.assertEqual(resumen["vinculos"], 4)
        self.assertEqual(resumen["focos_unicos"], 3)

    def test_coincidencias_aplica_dos_filtros(self):
        respuesta = self.client.get(
            reverse("coincidencias"), {"region": "7", "temporada": "2016"}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.consultas["obtener_coincidencias"].assert_called_once_with(
            7, 2016
        )

    def test_vegetacion_calcula_totales_sin_perder_precision(self):
        respuesta = self.client.get(reverse("vegetacion"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "incendios/vegetacion.html")
        resumen = respuesta.context["resumen"]
        self.assertEqual(resumen["superficie"], Decimal("12.50"))
        self.assertEqual(resumen["incendios"], 2)
        self.assertEqual(resumen["registros"], 2)
        self.assertEqual(resumen["tipos"], 1)

    def test_vegetacion_aplica_dos_filtros(self):
        respuesta = self.client.get(
            reverse("vegetacion"), {"region": "7", "temporada": "2016"}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.consultas["obtener_vegetacion"].assert_called_once_with(7, 2016)

    def test_filtros_invalidos_no_ejecutan_consulta_principal(self):
        casos = [
            ("dashboard", {"region": "7 OR 1=1"}, "obtener_evolucion"),
            ("causas", {"temporada": "2028"}, "obtener_causas"),
            ("coincidencias", {"region": "999"}, "obtener_coincidencias"),
            ("vegetacion", {"temporada": "abc"}, "obtener_vegetacion"),
        ]

        for ruta, filtros, consulta in casos:
            with self.subTest(ruta=ruta, filtros=filtros):
                respuesta = self.client.get(reverse(ruta), filtros)
                self.assertEqual(respuesta.status_code, 400)
                self.consultas[consulta].assert_not_called()

    def test_navegacion_contiene_las_cuatro_secciones(self):
        respuesta = self.client.get(reverse("dashboard"))

        self.assertEqual(respuesta.status_code, 200)
        for ruta in ("dashboard", "causas", "coincidencias", "vegetacion"):
            self.assertContains(respuesta, f'href="{reverse(ruta)}"')