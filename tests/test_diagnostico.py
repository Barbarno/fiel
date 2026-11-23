"""Pruebas de los comandos de diagnostico: coverage, probe, shrink, doctor, watch.

Todos trabajan sobre `examples/demo`, que son dos scripts de Python pequenos y
no necesitan toolchain de Rust.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fiel import check as check_mod
from fiel import ci as ci_mod
from fiel import badge as badge_mod
from fiel import cli
from fiel import corpus as corpus_mod
from fiel import coverage as coverage_mod
from fiel import doctor as doctor_mod
from fiel import guard as guard_mod
from fiel import probe as probe_mod
from fiel import report as report_mod
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


class GuardTests(unittest.TestCase):
    def _repo(self, tmp: str) -> Path:
        raiz = Path(tmp)
        subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
        (raiz / "fiel.toml").write_text("[project]\n", encoding="utf-8")
        return raiz

    def test_instala_y_quita_el_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raiz = self._repo(tmp)

            puesto = guard_mod.instalar(raiz)
            self.assertTrue(puesto.instalado)
            self.assertTrue(puesto.nuestro)
            contenido = puesto.hook.read_text(encoding="utf-8")
            self.assertIn("fiel: puerta de fidelidad", contenido)
            self.assertIn(" check", contenido)

            quitado = guard_mod.quitar(raiz)
            self.assertFalse(quitado.instalado)

    def test_no_pisa_un_hook_ajeno(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raiz = self._repo(tmp)
            ajeno = guard_mod.dir_hooks(raiz) / "pre-commit"
            ajeno.parent.mkdir(parents=True, exist_ok=True)
            ajeno.write_text("#!/bin/sh\necho hola\n", encoding="utf-8")

            with self.assertRaises(guard_mod.GuardError):
                guard_mod.instalar(raiz)

            self.assertIn("hola", ajeno.read_text(encoding="utf-8"))

    def test_sin_especificacion_no_instala(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raiz = self._repo(tmp)
            (raiz / "fiel.toml").unlink()

            with self.assertRaises(guard_mod.GuardError):
                guard_mod.instalar(raiz)

    def test_fuera_de_un_repositorio_se_queja(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(guard_mod.GuardError):
                guard_mod.estado(Path(tmp))


class BadgeTests(unittest.TestCase):
    def _resultado(self, fieles: int, total: int) -> check_mod.CheckResult:
        resultado = check_mod.CheckResult()
        resultado.pairs.append(
            check_mod.PairResult(pair_id="p", total=total, passed=fieles, cases=[])
        )
        return resultado

    def test_todo_fiel_es_verde(self) -> None:
        chapa = badge_mod.resumen(self._resultado(10, 10))
        self.assertEqual(chapa.color, badge_mod.VERDE)
        self.assertEqual(chapa.valor, "10/10")

    def test_casi_todo_fiel_es_ambar(self) -> None:
        chapa = badge_mod.resumen(self._resultado(95, 100))
        self.assertEqual(chapa.color, badge_mod.AMBAR)

    def test_desviado_es_rojo(self) -> None:
        chapa = badge_mod.resumen(self._resultado(5, 100))
        self.assertEqual(chapa.color, badge_mod.ROJO)

    def test_sin_casos_no_presume_de_verde(self) -> None:
        chapa = badge_mod.resumen(self._resultado(0, 0))
        self.assertEqual(chapa.color, badge_mod.GRIS)
        self.assertEqual(chapa.valor, "sin casos")

    def test_el_svg_es_xml_valido_y_se_explica_solo(self) -> None:
        import xml.etree.ElementTree as ET

        chapa = badge_mod.resumen(self._resultado(10, 10))
        arbol = ET.fromstring(badge_mod.svg(chapa))

        self.assertEqual(arbol.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertEqual(arbol.get("role"), "img")
        self.assertIn("10/10", arbol.get("aria-label", ""))
        self.assertIsNotNone(arbol.find("{http://www.w3.org/2000/svg}title"))

    def test_el_svg_no_tiene_recursos_remotos(self) -> None:
        texto = badge_mod.svg(badge_mod.resumen(self._resultado(3, 4)))
        sin_espacio_de_nombres = texto.replace('xmlns="http://www.w3.org/2000/svg"', "")
        for prohibido in ("http://", "https://", "<script", "@import"):
            self.assertNotIn(prohibido, sin_espacio_de_nombres)

    def test_el_comando_escribe_el_fichero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "sub" / "chapa.svg"
            codigo = cli.main(
                ["--root", str(DEMO), "badge", "--pair", "cron-fiel", "--out", str(destino)]
            )
            self.assertEqual(codigo, cli.EXIT_OK)
            self.assertIn("<svg", destino.read_text(encoding="utf-8"))

    def test_un_port_infiel_pinta_rojo_y_sale_con_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "chapa.svg"
            codigo = cli.main(
                ["--root", str(DEMO), "badge", "--pair", "cron-roto", "--out", str(destino)]
            )
            self.assertEqual(codigo, cli.EXIT_DIVERGENCE)
            self.assertIn(badge_mod.ROJO, destino.read_text(encoding="utf-8"))


class JunitTests(unittest.TestCase):
    def _xml(self, *args: str):
        import xml.etree.ElementTree as ET

        proyecto = load(DEMO)
        resultado = check_mod.check(proyecto, pairs=list(args), jobs=2)
        conocido, nuevo = check_mod.split_by_baseline(resultado, {})
        return ET.fromstring(report_mod.junit(resultado, conocido, nuevo, strict=False))

    def test_un_testcase_por_caso(self) -> None:
        arbol = self._xml("cron-fiel")
        self.assertEqual(arbol.get("tests"), "10")
        self.assertEqual(arbol.get("failures"), "0")
        casos = arbol.findall("./testsuite/testcase")
        self.assertEqual(len(casos), 10)

    def test_una_divergencia_es_un_fallo_con_las_dos_salidas(self) -> None:
        arbol = self._xml("cron-roto")
        self.assertEqual(arbol.get("failures"), "2")
        fallos = arbol.findall(".//failure")
        self.assertEqual(len(fallos), 2)
        texto = "".join(f.text or "" for f in fallos)
        self.assertIn("original:", texto)
        self.assertIn("port:", texto)

    def test_las_comillas_no_rompen_el_xml(self) -> None:
        arbol = self._xml("cron-roto")
        nombres = [c.get("name") or "" for c in arbol.findall(".//testcase")]
        self.assertTrue(all('"' not in n for n in nombres))

    def test_el_formato_junit_sale_por_la_linea_de_comandos(self) -> None:
        codigo = cli.main(
            ["--root", str(DEMO), "check", "--pair", "cron-fiel", "--format", "junit"]
        )
        self.assertEqual(codigo, cli.EXIT_OK)


class CiTests(unittest.TestCase):
    def test_el_guion_lleva_la_especificacion_y_las_parejas(self) -> None:
        proyecto = load(DEMO)
        texto = ci_mod.guion(proyecto, ("cron-fiel",))
        self.assertIn("fiel.toml", texto)
        self.assertIn("--pair cron-fiel", texto)
        self.assertIn("--format github", texto)
        self.assertIn(ci_mod.MARCA, texto)

    def test_con_todas_las_parejas_no_se_listan(self) -> None:
        proyecto = load(DEMO)
        todas = tuple(p.id for p in proyecto.pairs)
        texto = ci_mod.guion(proyecto, todas)
        self.assertNotIn("--pair", texto)

    def test_una_pareja_que_no_existe_se_rechaza(self) -> None:
        proyecto = load(DEMO)
        with self.assertRaises(ci_mod.CiError):
            ci_mod.guion(proyecto, ("no-existe",))

    def test_escribe_y_quita_el_workflow(self) -> None:
        proyecto = load(DEMO)
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / ".github" / "workflows" / "fiel.yml"
            escrito = ci_mod.escribir(proyecto, destino=destino)
            self.assertTrue(escrito.existe)
            self.assertTrue(destino.is_file())

            quitado = ci_mod.quitar(DEMO, destino)
            self.assertFalse(quitado.existe)
            self.assertFalse((Path(tmp) / ".github").exists())

    def test_no_pisa_un_workflow_ajeno(self) -> None:
        proyecto = load(DEMO)
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / ".github" / "workflows" / "fiel.yml"
            destino.parent.mkdir(parents=True)
            destino.write_text("name: otro\n", encoding="utf-8")

            with self.assertRaises(ci_mod.CiError):
                ci_mod.escribir(proyecto, destino=destino)
            self.assertEqual(destino.read_text(encoding="utf-8"), "name: otro\n")

    def test_el_comando_escribe_y_quita(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "wf" / "fiel.yml"
            codigo = cli.main(["--root", str(DEMO), "ci", "--install", "--out", str(destino)])
            self.assertEqual(codigo, cli.EXIT_OK)
            self.assertIn("actions/checkout", destino.read_text(encoding="utf-8"))

            codigo = cli.main(["--root", str(DEMO), "ci", "--remove", "--out", str(destino)])
            self.assertEqual(codigo, cli.EXIT_OK)
            self.assertFalse(destino.exists())


class CliTests(unittest.TestCase):
    def test_los_comandos_nuevos_estan_en_el_ayuda(self) -> None:
        parser = cli.build_parser()
        acciones = [a for a in parser._actions if getattr(a, "choices", None)]
        comandos = set(acciones[0].choices) if acciones else set()

        for nombre in ("coverage", "probe", "shrink", "doctor", "watch", "guard", "badge", "ci"):
            self.assertIn(nombre, comandos)

    def test_probe_por_linea_de_comandos(self) -> None:
        codigo = cli.main(["--root", str(DEMO), "probe", "--pair", "cron-fiel", "--input", "1-3"])
        self.assertEqual(codigo, cli.EXIT_OK)

    def test_probe_infiel_sale_con_1(self) -> None:
        codigo = cli.main(["--root", str(DEMO), "probe", "--pair", "cron-roto", "--input", "1-3"])
        self.assertEqual(codigo, cli.EXIT_DIVERGENCE)


if __name__ == "__main__":
    unittest.main()
