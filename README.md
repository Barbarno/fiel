# fiel

![fiel](https://github.com/Barbarno/fiel/actions/workflows/fiel.yml/badge.svg)

**La equivalencia no se demuestra una vez. Se mantiene.**

`fiel` vigila un port —una reescritura de código de un lenguaje a otro— y falla el
build en el momento en que el port deja de comportarse como el original.

Las herramientas de migración con IA demuestran la equivalencia **el día que
migras**. Al día siguiente alguien toca el port, o actualiza el original, y nadie
vuelve a comprobar nada. La equivalencia se pudre en silencio, igual que los
tests que nadie ejecuta. `fiel` cubre ese hueco: un corpus grabado, una
comprobación en cada pull request, y un `bisect` que encuentra el commit exacto
que rompió la fidelidad.

Sin dependencias. Solo Python 3.11 o superior.

---

## Cómo funciona

```
corpus (lo que hacía el original)  ──►  fiel check  ──►  ¿el port hace lo mismo?
                                            │
                                            ├─ no: falla el build, dice el caso exacto
                                            └─ sí: sigue
```

1. **Corpus.** Un fichero JSONL con entradas y la salida que dio el original para
   cada una. Se graba una vez y se versiona con el código.
2. **Check.** Ejecuta el original y el port sobre cada entrada, normaliza las dos
   salidas y las compara. Cualquier diferencia es una divergencia.
3. **Baseline.** Si llegas a un proyecto que ya tenía divergencias, las aceptas
   una vez y `fiel` solo falla con las **nuevas**. Sin esto, nadie adopta la
   herramienta.
4. **Bisect.** Cuando aparece una divergencia, `fiel` recorre los commits en un
   worktree temporal y te dice cuál la introdujo.

## Instalación

```bash
pip install .
```

Si `fiel` no aparece en el PATH:

```bash
python -m fiel --version
```

Y el camino corto para ver todo funcionando, sin preparar nada:

```bash
fiel demo
```

## Arranque en dos minutos

```bash
cd examples/demo
fiel record    # graba lo que hace el original
fiel check     # comprueba los dos ports del ejemplo
```

El ejemplo tiene dos parejas: `cron-fiel` (port fiel) y `cron-roto` (port con una
regresión de una línea). La salida:

```
cron-fiel: 10/10 fieles  [OK]
cron-roto: 8/10 fieles  [2 divergencias]

Divergencias (2), primeras 2:
  [output] caso c0004: original='5,6,7,8,9' port='5,6,7,8'
  [output] caso c0005: original='0' port=''
```

Y el commit culpable:

```bash
fiel bisect --since main --pair cron-fiel
```

## fiel.toml

```toml
[project]
baseline = "fiel.baseline.json"

[[pair]]
id = "cron"
original = { command = ["python", "original.py"] }
port     = { command = ["cargo", "run", "--quiet", "--release"] }
corpus   = "corpus/cron.jsonl"
timeout_ms = 5000
normalize = "text"     # text | json | bytes
errors = "compare"     # compare | ignore
```

- `command` recibe el caso por **stdin** y devuelve el resultado por **stdout**.
  Exit 0 = correcto, exit positivo = error controlado, señal o crash = caída.
- `normalize` decide qué cuenta como diferencia. `text` iguala saltos de línea y
  quita espacios al final; `json` ordena claves; `bytes` compara exacto.
- `errors = "ignore"` compara solo el estado cuando ambos fallan, útil cuando el
  mensaje de error del port no tiene por qué coincidir con el del original.

## En GitHub Actions

```yaml
name: fidelidad
on: [pull_request]
jobs:
  fiel:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: tu-usuario/fiel@v1
        with:
          root: .
```

O directamente:

```yaml
      - run: pip install . && fiel check --format github
```

`--format github` emite anotaciones `::error` que aparecen en la pestaña
*Files changed* del pull request, y `--format markdown` genera un comentario
idempotente listo para publicar.

## Comandos

| comando | qué hace |
|---|---|
| `fiel init` | crea un `fiel.toml` de plantilla |
| `fiel record` | vuelve a grabar las salidas del original |
| `fiel check` | comprueba el port y devuelve código de salida 1 si hay divergencias nuevas |
| `fiel add` | añade casos nuevos al corpus (`--input` o `--file`) y los graba |
| `fiel import` | trae un corpus de otra herramienta (JSONL tolerante) |
| `fiel baseline` | acepta las divergencias actuales (`--prune` limpia las resueltas) |
| `fiel bisect --since <ref>` | encuentra el commit que rompió la fidelidad |
| `fiel comment` | publica o actualiza el informe en un pull request |
| `fiel demo` | la historia completa, sin preparar nada |

Opciones útiles de `check`: `--pair`, `--case`, `--jobs`, `--strict` (ignora el
baseline), `--no-baseline`, `--format console|markdown|github|json`.

## Casos que aparecen solos

`fiel add` es lo que hace que el corpus crezca con el uso: cada fallo que
aparece en producción se añade como caso y no vuelve a pasar desapercibido.

```bash
fiel add --pair cron --input "1_0" --input "5 - 9"
fiel check
```

## Importar el corpus de otra herramienta

`fiel import` lee JSONL sin exigir un esquema: busca los campos por nombre
(`id`/`case_id`, `input`/`stdin`/`args`, `output`/`stdout`/`result`,
`status`/`ok`), acepta base64 cuando el nombre del campo acaba en `_b64`, y
serializa a JSON las entradas que lleguen como objeto.

```bash
fiel import --file casos.jsonl --output corpus/cron.jsonl
```

Las líneas que no puede interpretar las descarta y las cuenta, en vez de
abortar la importación entera.

## El ejemplo en Rust

`examples/rust-demo` es el caso real: un original en Python y un port compilado
en Rust. Los diez casos base pasan. Los tres casos trampa no:

| entrada | Python | Rust |
|---|---|---|
| `1_0` | `10` (acepta separadores) | error de parseo |
| `5 - 9` | `5,6,7,8,9` (tolera espacios) | error de parseo |
| `99999999999999999999` | número exacto (bignum) | desborda `i32` |

Son tres fallos de migración reales que ningún test escrito a mano detecta,
porque nadie escribe un test con `1_0` dentro.

```bash
cd examples/rust-demo/rust-port
cargo build --release --target x86_64-pc-windows-gnu   # Linux/macOS: cargo build --release
cd .. && fiel check
```

En el CI se compila y se comprueba en cada push, con
`examples/rust-demo/fiel.linux.toml` (misma pareja, distinta ruta de binario).
Ese fichero existe porque Windows añade `.exe` y compila en un subdirectorio por
tripleta; el `--spec` permite elegir el que corresponda sin duplicar el corpus.

## La puerta en rojo, con pruebas

El repositorio incluye la demostración hecha de verdad: el
[pull request #1](https://github.com/Barbarno/fiel/pull/1) cambia una línea del
port fiel a propósito, y el check `fidelidad` se pone en rojo diciendo el caso
exacto:

```
fidelidad  Comprobar fidelidad del ejemplo
cron-fiel: 8/10 fieles  [2 divergencias]
##[error]divergencia output: original=5,6,7,8,9 port=5,6,7,8
```

El PR se cerró sin fusionar para dejar `main` en verde. El registro queda ahí.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

41 pruebas, sin dependencias externas.

## Qué no hace

- **No genera el port.** Eso lo hace el agente o tú.
- **No inventa entradas.** Solo comprueba el corpus que le des. Un corpus pobre
  da una garantía pobre: la herramienta no puede demostrar lo que no ha probado.
- **No detecta un cambio que ninguna entrada del corpus provoca.** Es un
  guardián de regresiones, no una demostración de equivalencia perfecta.
- **No sustituye a los tests.** Los complementa: los tests dicen "esto funciona",
  `fiel` dice "esto sigue comportándose como el original".
- **El corpus puede quedarse viejo.** Si el original cambia, `fiel check` avisa
  con el recuento de casos desincronizados y sugiere `fiel record`.

## Relación con rust-anything

`rust-anything` es excelente en el día uno: graba, guía la migración y demuestra
la equivalencia antes de activar el port. `fiel` empieza donde ellos terminan:
el día mil, cuando el port ya está en producción y nadie se acuerda de por qué
era equivalente.

Son compatibles: el corpus de `fiel` acepta cualquier entrada en JSONL, y su
formato es lo bastante simple como para importarlo desde otra herramienta con un
adaptador de veinte líneas.

## Licencia

MIT.
