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

**Para presentarlo:** [`DEMO.md`](DEMO.md) tiene el guion minuto a minuto, y
`demo.ps1` lo ejecuta con pausas. Sin red, sin permisos, cinco minutos.

**La memoria:** [`MEMORIA.md`](MEMORIA.md), con el problema, el diseño, las
pruebas, los resultados y las limitaciones.

**El estudio:** [`estudio/resultados.md`](estudio/resultados.md) mide ports
generados por IA contra el corpus y publica la tabla.

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
| `fiel adequacy` | mide qué parte del comportamiento deja sin comprobar el corpus |
| `fiel gate` | comprueba que el port no está llamando al original por debajo |
| `fiel comment` | publica o actualiza el informe en un pull request |
| `fiel report` | escribe un informe HTML en un solo fichero (`--out`, `--open`) |
| `fiel demo` | la historia completa, sin preparar nada |

Opciones útiles de `check`: `--pair`, `--case`, `--jobs`, `--strict` (ignora el
baseline), `--no-baseline`, `--format console|markdown|github|json`.

## Lo que el corpus no cubre

Un corpus demuestra que el port coincide **en los casos grabados**. No dice nada
de los que no están. Las herramientas de migración con IA lo admiten con estas
palabras: *"solo detecta lo que cubre la grabación"*.

`fiel adequacy` mide ese hueco sin instrumentar nada y sin saber en qué lenguaje
está escrito el original:

1. Cada salida se reduce a una **forma**: estado, esqueleto del texto y tamaño.
   `5,6,7` y `1,2,3` son la misma forma; `error: no` es otra.
2. Se generan sondas deterministas a partir de las entradas del corpus: vacío,
   truncados, duplicados, delimitadores, desplazamiento de un byte, límites
   numéricos, Unicode.
3. Las formas que el corpus nunca produjo son **comportamiento no verificado**:
   ahí el port puede hacer lo que quiera y `fiel check` no dirá nada.
4. Se ejecuta el port sobre esas sondas. Cada diferencia es un fallo real que el
   corpus no estaba viendo.

```
$ fiel --root examples/targets/url adequacy
url: 40 casos cubren 36/180 formas de comportamiento (20.0%)
  144 formas sin verificar, 16 divergencias encontradas fuera del corpus
    [output] caso probe00059: original='http|-|example.com|-|/|-|-' port='http|-|example.com|80||-|-'
```

Dieciséis fallos que pasaban el `check` con nota perfecta. Eso es el número que
ninguna otra herramienta de este espacio publica.

Con `--write-unverified corpus/nuevas.jsonl` deja esas sondas listas para
`fiel record`, y el corpus crece justo por donde estaba ciego.

## El port no llama al original

Un port puede pasar los 40 casos sin reimplementar nada:

```python
subprocess.run([sys.executable, "original.py"], input=data)
```

`fiel gate` comprueba la definición literal de independencia: esconde los
ficheros del original, vuelve a ejecutar el port y mira si los casos que antes
pasaban siguen pasando. Si se rompen, el port dependía del original.

```
$ fiel gate
cron-fiel: independiente - 6 casos siguen pasando sin el original
tramposo: DEPENDIENTE - 1 de 1 casos se rompen al esconder el original
```

Los ficheros se restauran siempre, incluso si el port se cuelga.

## El informe

`fiel report` escribe un HTML en un solo fichero: sin javascript, sin
dependencias externas, se abre con el wifi apagado y se adjunta a la memoria
tal cual.

```bash
fiel --spec fiel.demo.toml report --out informe.html --open
```

La especificación `fiel.demo.toml` junta cuatro parejas —el port bueno, el roto,
el de Rust y los tres casos trampa— para que el informe enseñe el sistema
completo: 33 casos, 28 fieles y 5 divergencias con su entrada exacta.

Y `fiel.estudio.toml` junta los cuatro targets y el ejemplo real:
**230 comprobaciones, 25 divergencias**.

## Los cuatro targets

Cada target es una función distinta, con su original en Python, su port en Rust
y dos corpus: uno normal y uno de trampas.

| target | qué hace | dónde se rompe |
|---|---|---|
| `cron` | rangos y pasos (`5-9`, `*/15`) | enteros sin límite, `1_0`, espacios |
| `url` | separa las partes de una URL | IPv6, puerto por defecto, esquema en mayúsculas |
| `toml` | una línea `clave = valor` | enteros de 20 cifras, `\u`, arrays de cadenas |
| `slug` | título a URL (`Café` → `cafe`) | acentos, que Rust no pliega solo |

Los ports pasan el 100% del corpus normal y fallan 15 de las 24 trampas. Eso es
el proyecto entero en una frase: **funcionar no es ser equivalente**.

Los tres ports de Rust los escribió un asistente de IA en una pasada, sin
retoques: son la primera fila del estudio, no código preparado para lucirse.

## Dos bibliotecas reales

El quinto ejemplo no compara una función escrita aquí con su traducción.
Compara dos bibliotecas mantenidas por otras personas que implementan el mismo
estándar, SemVer 2.0.0: [`semver` de Python](https://pypi.org/project/semver/)
contra [`semver` de Rust](https://crates.io/crates/semver).

El estándar dice que la metadata de build **no** cuenta para el orden. Las dos
lo cumplen, pero con nombres distintos: Python lo hace en `semver.compare`;
Rust lo hace en `cmp_precedence`, y su `cmp` normal **sí** compara el build.

Un port mecánico traduce lo obvio y cambia el orden:

```
1.0.0+build2  vs  1.0.0+build1
  python-semver -> 0   (misma precedencia)
  semver-rs     -> 1   (build2 es mayor)
```

```
semver-real:          40/40 fieles  [OK]
semver-real-trampas:   3/8  fieles  [5 divergencias]
semver-real-fijo:      5/5  fieles  [OK]   <- con cmp_precedence
```

Detalle en [`examples/real-semver/README.md`](examples/real-semver/README.md).

## El estudio

`estudio/` mide ports generados por modelos contra los mismos corpus:

```bash
python estudio/estudio.py generar --modelo groq   # necesita GROQ_API_KEY
python estudio/estudio.py medir
```

Escribe `estudio/resultados.md` y `estudio/resultados.csv`. Las claves se leen
del entorno; no hay ninguna en el repositorio.

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
