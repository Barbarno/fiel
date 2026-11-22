"""Pruebas del informe HTML: escapado, baseline y casos vacios."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fiel import report_html
from fiel.check import CheckResult, PairResult
from fiel.compare import Divergence
from fiel.spec import Endpoint, Pair, Project


def _pair(pair_id: str, corpus: str = "corpus/x.jsonl") -> Pair:
    return Pair(
        id=pair_id,
        original=Endpoint(command=("echo", "a")),
        port=Endpoint(command=("echo", "b")),
        corpus=corpus,
    )


def _project(pairs: list[Pair], root: Path) -> Project:
    return Project(root=root, pairs=tuple(pairs))


def _div(case_id: str = "c0001", kind: str = "output", original: str = "ok", port: str = "err") -> Divergence:
    return Divergence(case_id=case_id, kind=kind, original=original, port=port, signature=f"sig-{case_id}")


class ReportHtmlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="fiel-html-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_escapa_html_de_los_datos(self) -> None:
        pair = _pair("<b>par</b>")
        div = _div(case_id="c1", original="<script>alert(1)</script>", port="a&b")
        result = CheckResult(pairs=[PairResult(pair_id="<b>par</b>", total=1, passed=0, divergences=[div])])

        out = report_html.render(_project([pair], self.dir), result)
        self.assertNotIn("<script>alert(1)</script>", out)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", out)
        self.assertIn("a&amp;b", out)
        self.assertIn("&lt;b&gt;par&lt;/b&gt;", out)

    def test_marca_las_divergencias_aceptadas(self) -> None:
        pair = _pair("p1")
        div = _div("c1", original="1", port="2")
        result = CheckResult(pairs=[PairResult(pair_id="p1", total=10, passed=9, divergences=[div])])

        out = report_html.render(_project([pair], self.dir), result, known=[div], fresh=[])
        self.assertIn("aceptada en baseline", out)
        self.assertIn("class='diff known'", out)
        self.assertNotIn("divergencias nuevas", out)

    def test_cuenta_las_nuevas_aparte(self) -> None:
        pair = _pair("p1")
        old, new = _div("c1", original="1", port="2"), _div("c2", original="3", port="4")
        result = CheckResult(pairs=[PairResult(pair_id="p1", total=10, passed=8, divergences=[old, new])])

        out = report_html.render(_project([pair], self.dir), result, known=[old], fresh=[new])
        self.assertIn("<span class=\"n red\">1</span><span class=\"l\">nuevas</span>", out)
        self.assertIn("1</span><span class=\"l\">en baseline</span>", out)

    def test_sin_divergencias(self) -> None:
        pair = _pair("p1")
        result = CheckResult(pairs=[PairResult(pair_id="p1", total=4, passed=4)])
        out = report_html.render(_project([pair], self.dir), result)
        self.assertIn("todas las parejas fieles", out)
        self.assertIn("Ninguna. El port hace lo mismo", out)

    def test_sin_parejas_no_revienta(self) -> None:
        out = report_html.render(_project([], self.dir), CheckResult())
        self.assertIn("0</span><span class=\"l\">casos</span>", out)
        self.assertIn("</html>", out)

    def test_entrada_texto_y_binaria(self) -> None:
        self.assertEqual(report_html._readable(b"5-9"), "5-9")
        self.assertEqual(report_html._readable(b"1_0"), "1_0")
        self.assertEqual(report_html._readable(b"5 - 9"), "5 - 9")
        self.assertEqual(report_html._readable(b""), "(vacio)")
        self.assertIn("\\n", report_html._readable(b"a\nb"))
        self.assertIn("(base64)", report_html._readable(bytes([0xFF, 0xFE, 0x00])))
        self.assertIn("...", report_html._readable(b"x" * 500))

    def test_lee_la_entrada_del_corpus(self) -> None:
        corpus_dir = self.dir / "corpus"
        corpus_dir.mkdir()
        (corpus_dir / "x.jsonl").write_text(
            '{"id": "c1", "input_b64": "NS05", "status": "ok", "output_b64": ""}\n',
            encoding="utf-8",
        )
        pair = _pair("p1")
        div = _div("c1", original="1", port="2")
        result = CheckResult(pairs=[PairResult(pair_id="p1", total=1, passed=0, divergences=[div])])

        out = report_html.render(_project([pair], self.dir), result)
        self.assertIn("5-9", out)

    def test_write_crea_directorios(self) -> None:
        pair = _pair("p1")
        result = CheckResult(pairs=[PairResult(pair_id="p1", total=1, passed=1)])
        target = self.dir / "sub" / "informe.html"

        written = report_html.write(_project([pair], self.dir), result, [], [], target, title="prueba")
        self.assertTrue(written.is_file())
        self.assertIn("prueba - informe", written.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
