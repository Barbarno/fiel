"""Pruebas de fiel. Solo biblioteca estandar:

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import base64
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fiel import corpus as corpus_mod
from fiel import check as check_mod
from fiel import cli
from fiel.compare import compare, normalize
from fiel.runner import ERR, OK, TIMEOUT, Observation, run
from fiel.spec import SpecError, load

ROOT = Path(__file__).resolve().parent.parent


def case(cid: str, payload: bytes, status: str, output: bytes) -> corpus_mod.Case:
    return corpus_mod.Case(id=cid, input=payload, status=status, output=output)


class NormalizeTests(unittest.TestCase):
    def test_texto_iguales_con_otro_salto_de_linea(self) -> None:
        self.assertEqual(normalize(b"a\nb", "text"), normalize(b"a\r\nb", "text"))

    def test_texto_ignora_espacios_al_final(self) -> None:
        self.assertEqual(normalize(b"5,6  ", "text"), "5,6")

    def test_json_ignora_orden_de_claves(self) -> None:
        self.assertEqual(normalize(b'{"b":1,"a":2}', "json"), normalize(b'{"a":2,"b":1}', "json"))

    def test_bytes_es_exacto(self) -> None:
        self.assertNotEqual(normalize(b"\x00", "bytes"), normalize(b"\x01", "bytes"))


class CompareTests(unittest.TestCase):
    def test_fiel_no_es_divergencia(self) -> None:
        c = case("c1", b"x", OK, b"1,2")
        self.assertIsNone(compare(c, Observation(OK, b"1,2"), Observation(OK, b"1,2"), "text", "compare"))

    def test_valor_distinto_es_divergencia(self) -> None:
        c = case("c1", b"x", OK, b"1,2")
        d = compare(c, Observation(OK, b"1,2"), Observation(OK, b"1"), "text", "compare")
        assert d is not None
        self.assertEqual(d.kind, "output")
        self.assertIn("1,2", d.original)

    def test_estado_distinto_es_divergencia(self) -> None:
        c = case("c1", b"x", OK, b"1")
        d = compare(c, Observation(OK, b"1"), Observation(ERR, b""), "text", "compare")
        assert d is not None
        self.assertEqual(d.kind, "status")

    def test_timeout_es_divergencia(self) -> None:
        c = case("c1", b"x", OK, b"1")
        d = compare(c, Observation(OK, b"1"), Observation(TIMEOUT, b""), "text", "compare")
        assert d is not None
        self.assertEqual(d.kind, "status")

    def test_errores_ignorados_no_compara_mensaje(self) -> None:
        c = case("c1", b"x", ERR, b"")
        d = compare(c, Observation(ERR, b"error: paso"), Observation(ERR, b"panic"), "text", "ignore")
        self.assertIsNone(d)

    def test_errores_comparados_si_se_pide(self) -> None:
        c = case("c1", b"x", ERR, b"")
        d = compare(c, Observation(ERR, b"error: paso"), Observation(ERR, b"panic"), "text", "compare")
        assert d is not None
        self.assertEqual(d.kind, "error-text")

    def test_caso_sin_grabar_es_error(self) -> None:
        c = corpus_mod.Case(id="c1", input=b"x", status=None, output=b"")
        with self.assertRaises(Exception):
            compare(c, Observation(OK, b"1"), Observation(OK, b"1"), "text", "compare")

    def test_firma_estable(self) -> None:
        c = case("c1", b"x", OK, b"1")
        a = compare(c, Observation(OK, b"1"), Observation(OK, b"2"), "text", "compare")
        b = compare(c, Observation(OK, b"1"), Observation(OK, b"2"), "text", "compare")
        assert a is not None and b is not None
        self.assertEqual(a.signature, b.signature)


class CorpusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="fiel-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_ida_y_vuelta(self) -> None:
        path = self.dir / "c.jsonl"
        cases = [
            corpus_mod.Case("c2", b"b", OK, b"2"),
            corpus_mod.Case("c1", b"a", ERR, b""),
        ]
        corpus_mod.write(path, cases)
        again = corpus_mod.read(path)
        self.assertEqual([c.id for c in again], ["c1", "c2"])
        self.assertEqual(again[0].status, ERR)
        self.assertEqual(again[1].output, b"2")

    def test_semilla_sin_salida(self) -> None:
        path = self.dir / "s.jsonl"
        path.write_text(json.dumps({"id": "c1", "input_b64": base64.b64encode(b"x").decode()}) + "\n", encoding="utf-8")
        cases = corpus_mod.read(path)
        self.assertFalse(cases[0].recorded)

    def test_id_duplicado_es_error(self) -> None:
        path = self.dir / "d.jsonl"
        row = json.dumps({"id": "c1", "input_b64": base64.b64encode(b"x").decode()})
        path.write_text(row + "\n" + row + "\n", encoding="utf-8")
        with self.assertRaises(corpus_mod.CorpusError):
            corpus_mod.read(path)

    def test_json_invalido_es_error(self) -> None:
        path = self.dir / "e.jsonl"
        path.write_text("{no es json}\n", encoding="utf-8")
        with self.assertRaises(corpus_mod.CorpusError):
            corpus_mod.read(path)


class RunnerTests(unittest.TestCase):
    def test_exit_cero_es_ok(self) -> None:
        obs = run([sys.executable, "-c", "import sys; sys.stdout.write(sys.stdin.read())"], b"hola", 5000)
        self.assertEqual(obs.status, OK)
        self.assertEqual(obs.output, b"hola")

    def test_exit_uno_es_err(self) -> None:
        obs = run([sys.executable, "-c", "import sys; sys.exit(1)"], b"", 5000)
        self.assertEqual(obs.status, ERR)

    def test_timeout(self) -> None:
        obs = run([sys.executable, "-c", "import time; time.sleep(10)"], b"", 200)
        self.assertEqual(obs.status, TIMEOUT)

    def test_comando_inexistente_es_crash(self) -> None:
        obs = run(["no-existe-esto-123"], b"", 1000)
        self.assertEqual(obs.status, "crash")


class SpecTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="fiel-spec-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_lee_el_demo(self) -> None:
        project = load(ROOT / "examples" / "demo")
        self.assertEqual(len(project.pairs), 2)
        self.assertEqual(project.pairs[0].id, "cron-fiel")

    def test_normalize_invalido_falla(self) -> None:
        (self.dir / "fiel.toml").write_text(
            '[[pair]]\nid="a"\noriginal={command=["x"]}\nport={command=["y"]}\n'
            'corpus="c.jsonl"\nnormalize="magia"\n',
            encoding="utf-8",
        )
        with self.assertRaises(SpecError):
            load(self.dir)

    def test_sin_parejas_falla(self) -> None:
        (self.dir / "fiel.toml").write_text("[project]\n", encoding="utf-8")
        with self.assertRaises(SpecError):
            load(self.dir)


class EndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="fiel-e2e-"))
        (self.dir / "orig.py").write_text(
            "import sys\nd=sys.stdin.buffer.read()\n"
            "sys.stdout.write('ok:'+d.decode())\n",
            encoding="utf-8",
        )
        (self.dir / "port.py").write_text(
            "import sys\nd=sys.stdin.buffer.read()\n"
            "sys.stdout.write('ok:'+d.decode())\n",
            encoding="utf-8",
        )
        (self.dir / "fiel.toml").write_text(
            '[project]\nbaseline = "fiel.baseline.json"\n\n'
            '[[pair]]\nid = "p"\noriginal = { command = ["python", "orig.py"] }\n'
            'port = { command = ["python", "port.py"] }\ncorpus = "corpus/p.jsonl"\n'
            'normalize = "text"\n',
            encoding="utf-8",
        )
        (self.dir / "corpus").mkdir()
        seed = [
            corpus_mod.Case(f"c{i}", f"in{i}".encode(), None, b"") for i in range(1, 4)
        ]
        corpus_mod.write(self.dir / "corpus" / "p.jsonl", seed)

    def tearDown(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)

    def _cli(self, *args: str) -> int:
        return cli.main(["--root", str(self.dir), *args])

    def test_record_y_check_limpio(self) -> None:
        self.assertEqual(self._cli("record"), 0)
        self.assertEqual(self._cli("check"), 0)

    def test_regresion_detectada(self) -> None:
        self.assertEqual(self._cli("record"), 0)
        (self.dir / "port.py").write_text(
            "import sys\nd=sys.stdin.buffer.read()\n"
            "sys.stdout.write('KO:'+d.decode())\n",
            encoding="utf-8",
        )
        self.assertEqual(self._cli("check"), 1)

    def test_baseline_acepta_lo_conocido(self) -> None:
        (self.dir / "port.py").write_text(
            "import sys\nsys.stdin.buffer.read()\nsys.stdout.write('KO')\n",
            encoding="utf-8",
        )
        self.assertEqual(self._cli("record"), 0)
        self.assertEqual(self._cli("baseline"), 0)
        self.assertEqual(self._cli("check"), 0)
        self.assertEqual(self._cli("check", "--strict"), 1)

    def test_drift_del_original_se_avisa(self) -> None:
        self.assertEqual(self._cli("record"), 0)
        (self.dir / "orig.py").write_text(
            "import sys\nsys.stdin.buffer.read()\nsys.stdout.write('distinto')\n",
            encoding="utf-8",
        )
        project = load(self.dir)
        result = check_mod.check(project)
        self.assertEqual(result.drifted, 3)

    def test_json_salida_parseable(self) -> None:
        self.assertEqual(self._cli("record"), 0)
        (self.dir / "port.py").write_text(
            "import sys\nsys.stdin.buffer.read()\nsys.stdout.write('KO')\n",
            encoding="utf-8",
        )
        import contextlib
        import io

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self._cli("check", "--format", "json")
        payload = json.loads(buffer.getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["fresh"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
