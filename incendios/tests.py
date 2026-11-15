"""Pruebas de regresión de las cuatro vistas sin conexión a PostgreSQL."""

from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.db import InterfaceError, OperationalError, ProgrammingError
from django.test import override_settings

from django.test import RequestFactory, SimpleTestCase
from django.urls import Resolver404, resolve, reverse

from .filtros import FiltroInvalido, opciones_temporadas, validar_filtros


class VistasSimuladasBase(SimpleTestCase):
    """Datos y mocks compartidos para pruebas HTTP sin PostgreSQL."""

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

class VistasIncendiosTests(VistasSimuladasBase):
    """Comprueba rutas, filtros y resultados usando datos simulados."""

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

    def test_dashboard_suma_superficie_con_decimal(self):
        respuesta = self.client.get(reverse("dashboard"))
        self.assertEqual(
            respuesta.context["totales"]["superficie"], Decimal("12.50")
        )
        self.assertIsInstance(
            respuesta.context["totales"]["superficie"], Decimal
        )


class FiltrosTests(SimpleTestCase):
    """Comprueba los filtros sin realizar consultas PostgreSQL."""

    def setUp(self):
        self.factory = RequestFactory()
        self.regiones = [
            {"id_region": 7, "nombre_region": "Maule"},
            {"id_region": 8, "nombre_region": "Biobío"},
        ]

    def test_filtros_vacios(self):
        request = self.factory.get("/")
        self.assertEqual(
            validar_filtros(request, self.regiones), (None, None)
        )

    def test_region_y_temporada_validas(self):
        request = self.factory.get("/causas/", {
            "region": "7", "temporada": "2016"
        })
        self.assertEqual(
            validar_filtros(request, self.regiones), (7, 2016)
        )

    def test_region_no_existente(self):
        request = self.factory.get("/causas/", {"region": "999"})
        with self.assertRaises(FiltroInvalido):
            validar_filtros(request, self.regiones)

    def test_temporada_fuera_del_rango(self):
        request = self.factory.get("/causas/", {"temporada": "2028"})
        with self.assertRaises(FiltroInvalido):
            validar_filtros(request, self.regiones)

    def test_dashboard_ignora_temporada(self):
        request = self.factory.get("/", {
            "region": "8", "temporada": "2028"
        })
        self.assertEqual(
            validar_filtros(
                request, self.regiones, incluir_temporada=False
            ),
            (8, None),
        )

    def test_opciones_temporadas(self):
        opciones = opciones_temporadas()
        self.assertEqual(len(opciones), 5)
        self.assertEqual(opciones[0]["nombre"], "2014-2015")
        self.assertEqual(opciones[-1]["nombre"], "2018-2019")


class RobustezPostgresTests(VistasSimuladasBase):
    """Comprueba HTTP 503 cuando PostgreSQL falla, sin BD real."""

    def test_conexion_fallida_devuelve_503_en_cualquier_vista(self):
        for ruta in ("dashboard", "causas", "coincidencias", "vegetacion"):
            with self.subTest(ruta=ruta):
                self.consultas["obtener_regiones"].side_effect = OperationalError(
                    "Conexión interna confidencial"
                )
                with self.assertLogs("incendios.errores", level="ERROR"):
                    respuesta = self.client.get(reverse(ruta))
                self.assertEqual(respuesta.status_code, 503)
                self.assertTemplateUsed(respuesta, "incendios/error_base_datos.html")
                self.assertNotIn(b"confidencial", respuesta.content.lower())
                self.assertEqual(respuesta["Cache-Control"], "no-store")
            self.consultas["obtener_regiones"].reset_mock(side_effect=True)

    def test_timeout_sql_devuelve_503(self):
        self.consultas["obtener_evolucion"].side_effect = OperationalError(
            "canceling statement due to statement timeout"
        )
        with self.assertLogs("incendios.errores", level="ERROR"):
            respuesta = self.client.get(reverse("dashboard"))
        self.assertEqual(respuesta.status_code, 503)
        self.assertContains(
            respuesta, "No se pudieron obtener los datos", status_code=503
        )

    def test_error_de_interfaz_devuelve_503(self):
        self.consultas["obtener_causas"].side_effect = InterfaceError(
            "Canal cerrado"
        )
        with self.assertLogs("incendios.errores", level="ERROR"):
            respuesta = self.client.get(reverse("causas"))
        self.assertEqual(respuesta.status_code, 503)
        self.assertNotIn(b"Canal cerrado", respuesta.content)

    def test_error_de_programacion_no_se_disfraza_de_503(self):
        self.consultas["obtener_vegetacion"].side_effect = ProgrammingError(
            "Consulta SQL inválida"
        )
        with self.assertRaises(ProgrammingError):
            self.client.get(reverse("vegetacion"))

    def test_log_identifica_la_ruta_con_falla(self):
        self.consultas["obtener_coincidencias"].side_effect = OperationalError(
            "Sin conexión"
        )
        with self.assertLogs("incendios.errores", level="ERROR") as registro:
            respuesta = self.client.get(reverse("coincidencias"))
        self.assertEqual(respuesta.status_code, 503)
        self.assertIn("/coincidencias/", registro.output[0])


class ConfiguracionTests(SimpleTestCase):
    """Verifica la configuración desplegable sin usar PostgreSQL."""

    def test_timeouts_positivos_y_sin_conexiones_persistentes(self):
        configuracion = settings.DATABASES["incendios"]
        opciones = configuracion["OPTIONS"]
        self.assertGreater(opciones["connect_timeout"], 0)
        self.assertIn("statement_timeout=", opciones["options"])
        self.assertEqual(configuracion["CONN_MAX_AGE"], 0)

    def test_parametros_aislados_y_sentencias_preparadas(self):
        opciones = settings.DATABASES["incendios"]["OPTIONS"]
        self.assertIs(opciones["server_side_binding"], True)
        self.assertEqual(opciones["prepare_threshold"], 0)

    def test_administracion_no_expuesta(self):
        with self.assertRaises(Resolver404):
            resolve("/admin/")

    def test_directorio_de_static_collectstatic(self):
        with TemporaryDirectory() as destino:
            with override_settings(STATIC_ROOT=destino):
                call_command("collectstatic", interactive=False, verbosity=0)
                archivo_css = Path(destino) / "incendios" / "estilos.css"
                self.assertTrue(archivo_css.is_file())


class ConsultasVistaSQLTests(SimpleTestCase):
    """Comprueba que Q2-Q4 usen la vista sin perder parametrización."""

    def verificar_consulta(self, funcion):
        from datetime import date

        with patch(
            "incendios.consultas.ejecutar_consulta", return_value=[]
        ) as ejecutar:
            funcion(region_id=7, temporada=2016)

        sql, parametros = ejecutar.call_args.args
        self.assertIn("FROM electromaquinas.v_incendios_region i", sql)
        self.assertIn("i.id_region = %s", sql)
        self.assertIn("i.fecha >= %s AND i.fecha < %s", sql)
        self.assertEqual(parametros, [
            7, date(2016, 7, 1), date(2017, 7, 1),
        ])
        self.assertNotIn("JOIN electromaquinas.comuna", sql)
        self.assertNotIn("JOIN electromaquinas.provincia", sql)
        self.assertNotIn("FROM electromaquinas.incendio i", sql)

    def test_causas_usa_vista(self):
        from .consultas import obtener_causas
        self.verificar_consulta(obtener_causas)

    def test_coincidencias_usa_vista(self):
        from .consultas import obtener_coincidencias
        self.verificar_consulta(obtener_coincidencias)

    def test_vegetacion_usa_vista(self):
        from .consultas import obtener_vegetacion
        self.verificar_consulta(obtener_vegetacion)
