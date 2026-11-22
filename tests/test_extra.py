"""Pruebas de importacion, ampliacion de corpus y publicacion del informe."""

from __future__ import annotations

import base64
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fiel import adapters, cli, mutate
from fiel import corpus as corpus_mod
from fiel.bot import BotError, resolve_token, upsert_comment


class AdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="fiel-ad-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)

    def _file(self, rows: list[dict]) -> Path:
        path = self.dir / "foreign.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        return path

    def test_nombres_de_campo_alternativos(self) -> None:
        path = self._file(
            [
                {"case_id": "a", "stdin": "hola", "stdout": "adiós", "status": "pass"},
                {"name": "b", "payload": "x", "result": "y", "ok": True},
            ]
        )
        rows, report = adapters.read_foreign(path)
        self.assertEqual(len(rows), 2)
        self.assertEqual(report.skipped, 0)
        self.assertEqual(rows[0]["id"], "a")
        self.assertEqual(rows[0]["input"], b"hola")
        self.assertEqual(rows[0]["status"], "ok")
        self.assertEqual(rows[1]["status"], "ok")

    def test_base64_por_sufijo(self) -> None:
        path = self._file(
            [{"id": "a", "input_b64": base64.b64encode(b"\x00\x01").decode(), "output_b64": base64.b64encode(b"z").decode()}]
        )
        rows, _ = adapters.read_foreign(path)
        self.assertEqual(rows[0]["input"], b"\x00\x01")
        self.assertEqual(rows[0]["output"], b"z")

    def test_entrada_estructurada_se_serializa(self) -> None:
        path = self._file([{"id": "a", "args": {"b": 1, "a": 2}}])
        rows, _ = adapters.read_foreign(path)
        self.assertEqual(rows[0]["input"], b'{"a": 2, "b": 1}')

    def test_lineas_malas_se_descartan(self) -> None:
        path = self.dir / "malo.jsonl"
        path.write_text("\n".join(["{roto}", json.dumps({"id": "a"}), json.dumps({"id": "b", "input": "v"})]), encoding="utf-8")
        rows, report = adapters.read_foreign(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(report.skipped, 2)

    def test_id_duplicado_se_renombra(self) -> None:
        path = self._file([{"id": "a", "input": "1"}, {"id": "a", "input": "2"}])
        rows, _ = adapters.read_foreign(path)
        converted = adapters.to_fiel(rows)
        self.assertEqual([r["id"] for r in converted], ["a", "a-2"])

    def test_escritura_con_append_no_duplica(self) -> None:
        target = self.dir / "corpus" / "c.jsonl"
        rows = adapters.to_fiel([{"id": "a", "input": b"1", "status": "ok", "output": b"1"}])
        adapters.write_corpus(rows, target)
        added = adapters.write_corpus(rows, target, append=True)
        self.assertEqual(added, 0)
        self.assertEqual(len(corpus_mod.read(target)), 1)


class MutateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="fiel-mut-"))
        self.path = self.dir / "c.jsonl"

    def tearDown(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_ids_secuenciales_sin_colision(self) -> None:
        corpus_mod.write(self.path, [corpus_mod.Case("u0001", b"a", "ok", b"1")])
        ids = mutate.add_inputs(self.path, [b"b", b"c"])
        self.assertEqual(ids, ["u0002", "u0003"])
        self.assertEqual(len(corpus_mod.read(self.path)), 3)

    def test_fichero_de_entradas(self) -> None:
        source = self.dir / "traps.txt"
        source.write_text("uno\n\ndos\n", encoding="utf-8")
        self.assertEqual(mutate.read_input_file(source), [b"uno", b"dos"])


class BotTests(unittest.TestCase):
    def test_dry_run_no_hace_peticiones(self) -> None:
        outcome = upsert_comment("a/b", 1, "cuerpo", "token", dry_run=True)
        self.assertIn("dry-run", outcome)

    def test_sin_token_falla(self) -> None:
        saved = {k: os.environ.pop(k, None) for k in ("GH_TOKEN", "GITHUB_TOKEN")}
        try:
            with self.assertRaises(BotError):
                resolve_token(None)
        finally:
            for key, value in saved.items():
                if value is not None:
                    os.environ[key] = value


class CliExtraTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="fiel-cli-"))
        (self.dir / "orig.py").write_text(
            "import sys\nd=sys.stdin.buffer.read()\nsys.stdout.write('o:'+d.decode())\n", encoding="utf-8"
        )
        (self.dir / "port.py").write_text(
            "import sys\nd=sys.stdin.buffer.read()\nsys.stdout.write('o:'+d.decode())\n", encoding="utf-8"
        )
        (self.dir / "fiel.toml").write_text(
            '[project]\nbaseline = "fiel.baseline.json"\n\n'
            '[[pair]]\nid = "p"\noriginal = { command = ["python", "orig.py"] }\n'
            'port = { command = ["python", "port.py"] }\ncorpus = "corpus/p.jsonl"\n',
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)

    def _cli(self, *args: str) -> int:
        return cli.main(["--root", str(self.dir), *args])

    def test_import_y_check(self) -> None:
        foreign = self.dir / "foreign.jsonl"
        foreign.write_text(
            json.dumps({"id": "a", "input": "uno", "output": "o:uno"}) + "\n"
            + json.dumps({"id": "b", "input": "dos"}) + "\n",
            encoding="utf-8",
        )
        self.assertEqual(self._cli("import", "--file", str(foreign), "--output", "corpus/p.jsonl"), 0)
        self.assertEqual(self._cli("record"), 0)
        self.assertEqual(self._cli("check"), 0)

    def test_add_anade_y_graba(self) -> None:
        (self.dir / "corpus").mkdir()
        corpus_mod.write(self.dir / "corpus" / "p.jsonl", [corpus_mod.Case("u0001", b"x", None, b"")])
        self.assertEqual(self._cli("record"), 0)
        self.assertEqual(self._cli("add", "--pair", "p", "--input", "y"), 0)
        self.assertEqual(self._cli("check"), 0)

    def test_add_sin_entradas_falla(self) -> None:
        (self.dir / "corpus").mkdir()
        corpus_mod.write(self.dir / "corpus" / "p.jsonl", [corpus_mod.Case("u0001", b"x", None, b"")])
        self.assertEqual(self._cli("add", "--pair", "p"), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
