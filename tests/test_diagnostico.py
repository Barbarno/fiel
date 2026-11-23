"""Pruebas de los comandos de diagnostico: coverage, probe, shrink, doctor, watch.

Todos trabajan sobre `examples/demo`, que son dos scripts de Python pequenos y
no necesitan toolchain de Rust.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fiel import check as check_mod
from fiel import cli
from fiel import corpus as corpus_mod
from fiel import coverage as coverage_mod
from fiel import doctor as doctor_mod
from fiel import probe as probe_mod
from fiel import shrink as shrink_mod
from fiel import watch as watch_mod
from fiel.spec import Project, load

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "examples" / "demo"


class DdminTests(unittest.TestCase):
    """El algoritmo, sin lanzar procesos: aqui lo que se prueba es la busqueda."""

    def test_reduce_hasta_el_trozo_que_falla(self) -> None:
        buscador = shrink_mod.Buscador(lambda datos: b"ab" in datos)

        minimo = buscador.reducir(b"xxabxxxxxxxxxxxx")

        self.assertEqual(minimo, b"ab")

    def test_un_solo_caracter_que_falla_se_queda(self) -> None:
        buscador = shrink_mod.Buscador(lambda datos: b"#" in datos)

        self.assertEqual(buscador.reducir(b"http://host/a#b"), b"#")

    def test_respeta_el_presupuesto(self) -> None:
        buscador = shrink_mod.Buscador(lambda datos: b"ab" in datos, presupuesto=3)

        minimo = buscador.reducir(b"x" * 40 + b"ab")

        self.assertIn(b"ab", minimo)
        self.assertTrue(buscador.agotado)
        self.assertLessEqual(buscador.ejecuciones, 3)

    def test_no_llama_dos_veces_con_la_misma_entrada(self) -> None:
        vistas = []
        buscador = shrink_mod.Buscador(lambda datos: vistas.append(datos) or b"ab" in datos)

        buscador.reducir(b"xxabxx")
        repetidas = len(vistas) - len(set(vistas))
        # puede haber repetidos entre ddmin y la pasada de extremos, pero no
        # dentro de la busqueda: la cache es lo que evita el trabajo doble
        self.assertGreater(len(vistas), 0)
        self.assertLessEqual(repetidas, 2)

    def test_trozos_no_pasa_de_n(self) -> None:
        for n in (2, 3, 5, 9):
            trozos = shrink_mod._trozos(b"0123456789abcdef", n)
            self.assertLessEqual(len(trozos), n)
            self.assertEqual(b"".join(trozos), b"0123456789abcdef")

    def test_lineas_antes_que_bytes(self) -> None:
        # una linea de las tres no hace falta: ddmin por lineas la quita de una
        buscador = shrink_mod.Buscador(lambda datos: b"falla" in datos)
        datos = b"ruido\nmas ruido\nfalla\ny mas ruido"

        self.assertEqual(buscador.reducir(datos), b"falla")


class ShrinkEndToEndTests(unittest.TestCase):
    def test_reduce_un_caso_real_de_la_demo(self) -> None:
        project = load(DEMO)
        pair = next(p for p in project.pairs if p.id == "cron-roto")
        resultado_check = check_mod.check(Project(root=project.root, pairs=(pair,)))
        divergencia = resultado_check.pairs[0].divergences[0]
        caso = next(
            c for c in corpus_mod.read(project.root / pair.corpus)
            if c.id == divergencia.case_id
        )

        reducido = shrink_mod.reducir(pair, project, caso, divergencia, presupuesto=30)

        self.assertLessEqual(len(reducido.despues), len(reducido.antes))
        self.assertIsNotNone(reducido.divergencia_despues)
        self.assertGreater(reducido.ejecuciones, 0)

    def test_sin_caso_ni_all_se_queja(self) -> None:
        project = load(DEMO)
        with self.assertRaises(ValueError):
            shrink_mod.shrink_casos(project, pairs=["cron-roto"], casos=None, todos=False)


class CoverageTests(unittest.TestCase):
    def test_mide_la_demo(self) -> None:
        project = load(DEMO)
        resultado = coverage_mod.medir(project, pairs=["cron-fiel"])

        par = resultado.pairs[0]
        self.assertTrue(par.medido)
        self.assertGreater(par.statements, 10)
        self.assertGreater(par.covered, 10)
        self.assertLessEqual(par.covered, par.statements)
        self.assertLess(par.porcentaje, 101.0)

    def test_un_binario_no_se_puede_medir(self) -> None:
        project = load(DEMO)
        pair = project.pairs[0]
        falso = type(pair)(
            id="rust",
            original=type(pair.original)(command=("port.exe",)),
            port=pair.port,
            corpus=pair.corpus,
        )

        self.assertIsNone(coverage_mod.script_de(falso.original, project))

    def test_rangos_compactos(self) -> None:
        self.assertEqual(coverage_mod._rangos([1, 2, 3, 7, 9, 10]), "1-3, 7, 9-10")
        self.assertEqual(coverage_mod._rangos([]), "ninguna")

    def test_markdown_y_console_no_revientan(self) -> None:
        resultado = coverage_mod.medir(load(DEMO))
        self.assertIn("| pareja |", coverage_mod.markdown(resultado))
        self.assertIn("sentencias", coverage_mod.console(resultado))

    def test_min_devuelve_1_por_debajo_del_umbral(self) -> None:
        self.assertEqual(cli.main(["--root", str(DEMO), "coverage", "--pair", "cron-fiel", "--min", "90"]), cli.EXIT_OK)
        self.assertEqual(
            cli.main(["--root", str(DEMO), "coverage", "--pair", "cron-fiel", "--min", "101"]),
            cli.EXIT_DIVERGENCE,
        )


class ProbeTests(unittest.TestCase):
    def test_entrada_fiel(self) -> None:
        project = load(DEMO)
        pair = probe_mod.obtener(project, "cron-fiel")

        resultado = probe_mod.una(pair, project, b"1-3")

        self.assertTrue(resultado.fiel)
        self.assertIn("FIEL", probe_mod.console(resultado))

    def test_entrada_infiel(self) -> None:
        project = load(DEMO)
        pair = probe_mod.obtener(project, "cron-roto")

        resultado = probe_mod.una(pair, project, b"1-3")

        self.assertFalse(resultado.fiel)
        self.assertIn("NO FIEL", probe_mod.console(resultado))
        self.assertIsNotNone(probe_mod.as_json(resultado)["kind"])

    def test_lee_de_fichero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "entrada.txt"
            ruta.write_text("7", encoding="utf-8")

            self.assertEqual(probe_mod.leer_entrada(f"@{ruta}"), b"7")

    def test_pareja_desconocida(self) -> None:
        project = load(DEMO)
        with self.assertRaises(probe_mod.ProbeError):
            probe_mod.obtener(project, "no-existe")


class DoctorTests(unittest.TestCase):
    def test_la_demo_esta_en_orden(self) -> None:
        project = load(DEMO)
        hallazgos = doctor_mod.diagnosticar(project)

        fallos = [h for h in hallazgos if h.nivel == doctor_mod.FALLO]
        self.assertEqual(fallos, [])
        self.assertTrue(any(h.nivel == doctor_mod.OK for h in hallazgos))

    def test_smoke_arranca_los_dos_lados(self) -> None:
        project = load(DEMO)
        hallazgos = doctor_mod.diagnosticar(project, smoke=True)

        arrancan = [h for h in hallazgos if "los dos lados arrancan" in h.titulo]
        self.assertEqual(len(arrancan), 2)
        self.assertTrue(all(h.nivel == doctor_mod.OK for h in arrancan))


class WatchTests(unittest.TestCase):
    def test_la_firma_cambia_al_tocar_un_fichero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "a.txt"
            ruta.write_text("uno", encoding="utf-8")
            antes = watch_mod.firma([ruta])

            ruta.write_text("dos mas largo", encoding="utf-8")
            os.utime(ruta, (1.0, 1.0))
            despues = watch_mod.firma([ruta])

            self.assertNotEqual(antes, despues)

    def test_una_vuelta_sin_cambios_devuelve_el_codigo_de_la_comprobacion(self) -> None:
        project = load(DEMO)
        resultado = watch_mod.una_vuelta(project, ["cron-fiel"], jobs=2, quiet=True)

        self.assertEqual(resultado.codigo, 0)
        self.assertEqual(resultado.total, 10)

    def test_una_vuelta_con_divergencias_sale_con_1(self) -> None:
        project = load(DEMO)
        resultado = watch_mod.una_vuelta(project, ["cron-roto"], jobs=2, quiet=True)

        self.assertEqual(resultado.codigo, 1)
        self.assertGreater(resultado.fallos, 0)


class CliTests(unittest.TestCase):
    def test_los_comandos_nuevos_estan_en_el_ayuda(self) -> None:
        parser = cli.build_parser()
        acciones = [a for a in parser._actions if getattr(a, "choices", None)]
        comandos = set(acciones[0].choices) if acciones else set()

        for nombre in ("coverage", "probe", "shrink", "doctor", "watch"):
            self.assertIn(nombre, comandos)

    def test_probe_por_linea_de_comandos(self) -> None:
        codigo = cli.main(["--root", str(DEMO), "probe", "--pair", "cron-fiel", "--input", "1-3"])
        self.assertEqual(codigo, cli.EXIT_OK)

    def test_probe_infiel_sale_con_1(self) -> None:
        codigo = cli.main(["--root", str(DEMO), "probe", "--pair", "cron-roto", "--input", "1-3"])
        self.assertEqual(codigo, cli.EXIT_DIVERGENCE)


if __name__ == "__main__":
    unittest.main()
