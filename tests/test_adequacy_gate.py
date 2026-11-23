"""Pruebas de las dos capas nuevas: adequacy y gate.

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import base64
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fiel import adequacy
from fiel import gate as gate_mod
from fiel.runner import CRASH, ERR, OK, TIMEOUT, Observation

ENCODER = """
import sys
data = sys.stdin.read()
print(str(len(data)))
"""

CHEATER = """
import subprocess, sys
out = subprocess.run([sys.executable, "original.py"], input=sys.stdin.read(),
                     capture_output=True, text=True)
sys.stdout.write(out.stdout)
"""

HONEST = """
import sys
data = sys.stdin.read()
print(str(len(data)))
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def corpus_line(cid: str, payload: bytes, status: str, output: bytes) -> str:
    return (
        "{"
        f'"id":"{cid}",'
        f'"input_b64":"{base64.b64encode(payload).decode()}",'
        f'"status":"{status}",'
        f'"output_b64":"{base64.b64encode(output).decode()}"'
        "}"
    )


class ShapeTests(unittest.TestCase):
    def test_mismo_esqueleto_es_la_misma_forma(self) -> None:
        a = adequacy.behavior_class(Observation(OK, b"5,6,7"))
        b = adequacy.behavior_class(Observation(OK, b"1,2,3"))
        self.assertEqual(a, b)

    def test_texto_y_numero_son_formas_distintas(self) -> None:
        a = adequacy.behavior_class(Observation(OK, b"5,6,7"))
        b = adequacy.behavior_class(Observation(OK, b"error: no"))
        self.assertNotEqual(a, b)

    def test_estado_manda_sobre_el_texto(self) -> None:
        a = adequacy.behavior_class(Observation(ERR, b"boom"))
        b = adequacy.behavior_class(Observation(OK, b"boom"))
        self.assertNotEqual(a, b)

    def test_timeout_y_crash_son_clases_propias(self) -> None:
        self.assertEqual(adequacy.behavior_class(Observation(TIMEOUT, b"")), TIMEOUT)
        self.assertEqual(adequacy.behavior_class(Observation(CRASH, b"")), CRASH)

    def test_binario_no_rompe_la_clasificacion(self) -> None:
        cls = adequacy.behavior_class(Observation(OK, b"\xff\xfe\x00"))
        self.assertTrue(cls.startswith("ok:"))


class ProbeTests(unittest.TestCase):
    def test_el_plan_es_determinista(self) -> None:
        seeds = [b"abc", b"1,2,3"]
        self.assertEqual(adequacy.probe_inputs(seeds, 50), adequacy.probe_inputs(seeds, 50))

    def test_el_presupuesto_se_respeta(self) -> None:
        self.assertLessEqual(len(adequacy.probe_inputs([b"x" * 40], 20)), 20)

    def test_sin_semillas_hay_sondas_fijas(self) -> None:
        self.assertGreater(len(adequacy.probe_inputs([], 50)), 0)

    def test_las_sondas_incluyen_la_entrada_vacia(self) -> None:
        self.assertIn(b"", adequacy.probe_inputs([b"abc"], 50))


class AdequacyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write(self.root / "original.py", ENCODER)
        write(self.root / "port.py", ENCODER)
        write(
            self.root / "fiel.toml",
            '[project]\nbaseline = "fiel.baseline.json"\n\n'
            '[[pair]]\nid = "eco"\n'
            'original = { command = ["python", "original.py"] }\n'
            'port = { command = ["python", "port.py"] }\n'
            'corpus = "corpus/eco.jsonl"\ntimeout_ms = 5000\nnormalize = "text"\n',
        )
        lines = [
            corpus_line("c1", b"abc", OK, b"3"),
            corpus_line("c2", b"abcdef", OK, b"6"),
        ]
        write(self.root / "corpus/eco.jsonl", "\n".join(lines) + "\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_mide_y_no_inventa_divergencias_en_un_port_fiel(self) -> None:
        from fiel.spec import load

        project = load(self.root)
        report = adequacy.measure(project, budget=30).pairs[0]
        self.assertEqual(report.corpus_cases, 2)
        self.assertGreater(report.probe_classes, report.corpus_classes)
        self.assertEqual(report.divergences, [])

    def test_un_port_roto_aparece_fuera_del_corpus(self) -> None:
        from fiel.spec import load

        # el port solo acierta con las longitudes del corpus
        write(self.root / "port.py", "import sys\nn = len(sys.stdin.read())\nprint('3' if n == 3 else 'x')\n")
        project = load(self.root)
        report = adequacy.measure(project, budget=30).pairs[0]
        self.assertGreater(len(report.divergences), 0)

    def test_la_cobertura_no_pasa_del_cien_por_cien(self) -> None:
        from fiel.spec import load

        project = load(self.root)
        report = adequacy.measure(project, budget=30).pairs[0]
        self.assertLessEqual(report.coverage, 1.0)

    def test_json_es_serializable(self) -> None:
        import json

        from fiel.spec import load

        project = load(self.root)
        payload = adequacy.as_json(adequacy.measure(project, budget=20))
        json.dumps(payload)


class GateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write(self.root / "original.py", ENCODER)
        write(self.root / "corpus/eco.jsonl", corpus_line("c1", b"abc", OK, b"3") + "\n")
        write(
            self.root / "fiel.toml",
            '[project]\nbaseline = "fiel.baseline.json"\n\n'
            '[[pair]]\nid = "eco"\n'
            'original = { command = ["python", "original.py"] }\n'
            'port = { command = ["python", "port.py"] }\n'
            'corpus = "corpus/eco.jsonl"\ntimeout_ms = 5000\nnormalize = "text"\n',
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_un_port_honesto_es_independiente(self) -> None:
        from fiel.spec import load

        write(self.root / "port.py", HONEST)
        report = gate_mod.check(load(self.root), sample=2).pairs[0]
        self.assertTrue(report.independent)
        self.assertEqual(report.broken_by_hiding, [])

    def test_un_port_que_llama_al_original_se_detecta(self) -> None:
        from fiel.spec import load

        write(self.root / "port.py", CHEATER)
        report = gate_mod.check(load(self.root), sample=2).pairs[0]
        self.assertFalse(report.independent)
        self.assertIn("c1", report.broken_by_hiding)

    def test_el_original_se_restaura_siempre(self) -> None:
        from fiel.spec import load

        write(self.root / "port.py", CHEATER)
        gate_mod.check(load(self.root), sample=2)
        self.assertTrue((self.root / "original.py").is_file())
        self.assertFalse((self.root / "original.py.fiel-hidden").exists())

    def test_sin_fichero_que_esconder_no_falla(self) -> None:
        from fiel.spec import load

        write(self.root / "port.py", HONEST)
        write(
            self.root / "fiel.toml",
            '[project]\nbaseline = "fiel.baseline.json"\n\n'
            '[[pair]]\nid = "eco"\n'
            'original = { command = ["python"] }\n'
            'port = { command = ["python", "port.py"] }\n'
            'corpus = "corpus/eco.jsonl"\ntimeout_ms = 5000\nnormalize = "text"\n',
        )
        report = gate_mod.check(load(self.root), sample=2).pairs[0]
        self.assertEqual(report.hidden_files, [])
        self.assertTrue(report.independent)


if __name__ == "__main__":
    unittest.main()
