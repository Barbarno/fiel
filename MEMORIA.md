# fiel

**Memoria del proyecto intermodular**

| | |
|---|---|
| Autor | Dano |
| Ciclo | Desarrollo de Aplicaciones Web (DAW) |
| Centro | FILL: nombre del centro |
| Curso | 2025/2026 |
| Tutor | FILL: nombre del tutor |
| Fecha de entrega | 22 de noviembre de 2026 |

---

## 1. Resumen

Cuando una empresa reescribe un programa en otro lenguaje, hoy suele usar
inteligencia artificial para traducirlo. Después comprueba que funciona con los
tests que tenga. El problema es que los tests prueban lo que alguien pensó, y
los fallos de una traducción están justo en lo que nadie pensó.

**fiel** es una herramienta que guarda el comportamiento del programa original
y comprueba, en cada cambio, que la versión nueva hace exactamente lo mismo.
No opina: ejecuta las mismas entradas contra los dos programas y compara las
salidas.

El proyecto incluye la herramienta, seis ejemplos reales (cuatro funciones, dos
bibliotecas del mismo estándar y seis reescrituras a mano de la biblioteca
estándar), 302 casos grabados, un estudio con ports escritos por IA y un _check_
de GitHub que bloquea un pull request cuando la equivalencia se rompe.

---

## 2. El problema

### 2.1 Un ejemplo pequeño

Un programa recibe `5-9` y devuelve los números del 5 al 9:

```
entrada:  5-9
original: 5,6,7,8,9
```

Alguien lo traduce a otro lenguaje y escribe `end` donde estaba `end + 1`:

```
entrada:  5-9
nuevo:    5,6,7,8
```

Falta un número. El programa compila, arranca, no lanza ninguna excepción, y
pasa cualquier test que no pruebe justo ese caso. El fallo aparece semanas
después, cuando un cliente dice que le falta el último día del rango.

### 2.2 Por qué los tests normales no lo ven

Un test se escribe una vez, con los casos que a alguien se le ocurrieron. Sirve
para comprobar que el programa hace lo que su autor quería. No sirve para
comprobar que hace **lo mismo que el programa viejo**, porque para eso haría
falta ejecutar los dos y comparar.

### 2.3 Por qué la IA no lo resuelve sola

La IA traduce el código, pero no tiene forma de saber qué hacía el original
con una entrada rara. Su traducción es plausible, no equivalente. La diferencia
entre "plausible" y "equivalente" es exactamente donde están los fallos.

---

## 3. Qué hace fiel, en una página

```
   original.py  ──►  fiel record  ──►  corpus/  (entradas + salidas grabadas)
                                          │
   port.rs      ──►  fiel check   ◄───────┘
                          │
                          ├── todo coincide  ──►  exit 0  (verde)
                          └── algo difiere   ──►  exit 1  (rojo)
```

1. **Se graba** lo que hace el original con un conjunto de entradas. El
   resultado se guarda en un fichero versionado junto al código.
2. **Se comprueba** que el port hace lo mismo con esas mismas entradas.
3. **Se repite** en cada cambio, dentro de GitHub, para que nadie pueda
   fusionar una regresión sin verla.

La herramienta no escribe el port. No usa IA para decidir. Solo ejecuta,
compara y devuelve un código de salida.

---

## 4. Objetivos

| objetivo | cómo se mide |
|---|---|
| Detectar diferencias de comportamiento entre original y port | divergencias encontradas en los corpus de trampas |
| No bloquear la adopción en proyectos que ya venían mal | el _baseline_ permite aceptar fallos existentes y fallar solo con los nuevos |
| Encajar en el trabajo diario | un comando, código de salida 0/1, integración con GitHub Actions |
| No depender de nada externo | solo Python 3.11 y biblioteca estándar |
| Producir datos, no solo una herramienta | tabla de resultados con cinco ejemplos y 302 casos |

---

## 5. Lo que ya existe y en qué se diferencia

| solución | qué hace | qué le falta |
|---|---|---|
| Tests unitarios | comprueban lo que el autor pensó | no comparan con el original |
| _Golden tests_ | comparan con una salida guardada | se escriben a mano y no crecen solos |
| _Property-based testing_ (Hypothesis) | genera entradas aleatorias | no sabe qué hacía el original; compara contra una regla escrita a mano |
| `rust-anything` (7.800 estrellas) | migra código y comprueba la equivalencia ese día | su propio README dice que solo detecta lo que cubre la grabación; no hay corpus versionado, ni baseline, ni búsqueda del commit que rompió |
| **fiel** | guarda el comportamiento, lo versiona y lo comprueba en cada cambio | el corpus solo cubre lo que se le da |

La diferencia no es "medir una vez". Es **medir siempre**, sobre un corpus que
crece con cada fallo real, y poder adoptarlo en un proyecto que ya tenía
diferencias.

---

## 6. Cómo está construido

### 6.1 Arquitectura

```
fiel/
├── spec.py         lee fiel.toml: parejas, comandos, corpus
├── corpus.py       lee y escribe el corpus (JSONL, entradas en base64)
├── runner.py       ejecuta un comando, captura salida, timeout y código
├── compare.py      normaliza y decide si dos ejecuciones son iguales
├── check.py        orquesta: por pareja, por caso, en paralelo
├── bisect.py       busca el commit que rompió la fidelidad
├── report.py       salida de consola, markdown y anotaciones de GitHub
├── report_html.py  informe HTML de un solo fichero
├── bot.py          publica el informe como comentario en un PR
├── adapters.py     importa corpus de otras herramientas
├── mutate.py       añade entradas nuevas al corpus
├── demo.py         la historia completa, para presentar
├── doctor.py      revisa que el entorno este listo antes de comprobar
├── watch.py       repite la comprobacion cuando cambia un fichero
├── coverage.py    cuenta las lineas del original que ejecuta el corpus
├── probe.py       prueba una entrada suelta contra una pareja
├── shrink.py      reduce un caso que diverge al minimo (ddmin)
├── guard.py       instala la comprobacion como hook de git
└── cli.py          los comandos
```

3.838 líneas no vacías de motor, 96 pruebas automáticas, cero dependencias externas.

### 6.2 Los comandos

| comando | para qué |
|---|---|
| `fiel init` | crea el fichero de configuración |
| `fiel record` | graba lo que hace el original |
| `fiel check` | comprueba el port (0 = igual, 1 = divergencia) |
| `fiel add` | añade un caso nuevo y lo graba |
| `fiel baseline` | acepta los fallos que ya existían |
| `fiel bisect` | encuentra el commit que rompió la equivalencia |
| `fiel report` | escribe el informe HTML |
| `fiel demo` | ejecuta la demostración completa |
| `fiel doctor` | revisa el entorno: intérprete, corpus, comandos que arrancan |
| `fiel watch` | repite la comprobación cuando cambia un fichero |
| `fiel coverage` | mide cuántas líneas del original ejecuta el corpus |
| `fiel probe` | prueba una entrada suelta, sin grabarla en el corpus |
| `fiel shrink` | reduce un caso que diverge al mínimo que sigue fallando |
| `fiel guard` | instala `fiel check` como hook de git: el commit no se crea si hay divergencia |

### 6.3 El corpus

Cada caso guarda la entrada y la salida del original, en base64 para que
cualquier byte quepa sin romper el formato:

```json
{"id": "c0004", "input_b64": "NS05", "output_b64": "NSw2LDcsOCw5", "status": "ok"}
```

Vive en el repositorio. Se revisa en un pull request como cualquier otro
fichero. Cuando aparece un fallo nuevo, `fiel add` lo añade y queda cubierto
para siempre.

### 6.4 El baseline

Si la herramienta llega a un proyecto que ya tenía divergencias, el primer
`check` falla y el equipo la desinstala. El baseline guarda la lista de fallos
conocidos y solo considera grave lo que aparece después. Es lo que permite
adoptarla en un proyecto vivo, no solo en uno nuevo.

### 6.5 La normalización

Antes de comparar hay que decidir qué cuenta como diferencia. `text` iguala
saltos de línea y quita espacios al final; `json` ordena las claves; `bytes`
compara exacto. Sin esto, la mayoría de los avisos serían diferencias de
formato y la herramienta sería inservible.

---

## 7. Cómo se comprobó que funciona

### 7.1 Pruebas automáticas

96 pruebas unitarias sobre el motor: comparación, normalización, corpus,
baseline, importación, informe y CLI. Se ejecutan en menos de un segundo.

### 7.2 Integración continua

Dos trabajos en GitHub Actions:

- **motor y ejemplo en Python**: pruebas + comprobación del ejemplo.
- **port real en Rust**: compila el port y lo compara contra el original.

El segundo es el que demuestra que la herramienta funciona con un binario
compilado, no solo con scripts.

### 7.3 La prueba que no se puede falsificar

Se abrió el pull request #1 con una regresión deliberada: un carácter menos en
el port. GitHub puso el _check_ `fidelidad` en rojo en 10 segundos, con el caso
exacto. Se cerró sin fusionar y el registro sigue público:

```
https://github.com/Barbarno/fiel/pull/1
```

Eso no es una captura de pantalla: es el historial de un repositorio.

### 7.4 El estudio

Se escribieron cuatro funciones en Python (rango, URL, TOML y slug) y sus
ports en Rust. Para cada una hay dos corpus:

- **normal**: 40 casos de uso corriente (10 en el ejemplo del rango).
- **trampas**: 3 a 9 casos límite (IPv6, enteros de 20 cifras, acentos, arrays
  de cadenas).

Resultado: los ports pasan el 100% de los casos normales y fallan 15 de las 24
trampas. Es decir, **un port que "funciona" no es un port equivalente**, y la
diferencia solo aparece cuando se prueba a propósito.

Los tres ports de Rust los escribió un asistente de IA a partir de la
especificación de cada función, sin retoques posteriores: es la primera fila
del estudio, no una fila hecha a mano para que quedara bien.

### 7.5 Dos bibliotecas reales

El quinto ejemplo sube un escalón: en vez de comparar una función propia con su
traducción, compara dos bibliotecas mantenidas por otras personas que
implementan el mismo estándar, SemVer 2.0.0: `semver` 3.1.2 de Python contra
`semver` 1.0.28 de Rust.

El estándar dice, en el punto 10, que la metadata de build no cuenta para el
orden de versiones. Las dos bibliotecas lo cumplen, pero lo exponen distinto:
Python lo hace en `semver.compare`; el crate de Rust lo hace en
`cmp_precedence`, y su `cmp` normal sí compara el build.

Un port mecánico traduce `semver.compare(a, b)` a `a.cmp(&b)`. Compila, pasa los
40 casos normales y **cambia el orden** de las versiones que solo difieren en
build. fiel lo detecta en los tres casos del corpus de trampas, y el port
corregido con `cmp_precedence` las pasa todas:

```
semver-real:          40/40 fieles  [OK]
semver-real-trampas:   3/8  fieles  [5 divergencias]
semver-real-fijo:      5/5  fieles  [OK]
```

Es el hallazgo más fuerte del proyecto: no es un fallo inventado en un ejemplo,
es una diferencia real entre dos implementaciones del mismo estándar, y la
herramienta la encuentra sola.

### 7.6 Seis reescrituras a mano

Quedaba un caso por cubrir, y es el más común de todos: alguien que no migra de
lenguaje ni pide un port, sino que reescribe una función de la biblioteca
estándar porque le parece sencilla.

`estudio/portes/` tiene seis parejas de ese tipo: `csv`, `shlex`, `url`, `wrap`,
`ip` y `casefold`. En cada una, el original es la función real de Python y el
port es la reescritura ingenua que haría cualquiera en cinco minutos.

Las seis pasan su corpus normal entero. Con las trampas:

```
mano-csv:          6/6 fieles  [OK]     mano-csv-trampas:          2/8  [6 divergencias]
mano-shlex:        6/6 fieles  [OK]     mano-shlex-trampas:        1/8  [7 divergencias]
mano-url:          6/6 fieles  [OK]     mano-url-trampas:          0/11 [11 divergencias]
mano-wrap:         6/6 fieles  [OK]     mano-wrap-trampas:         0/6  [6 divergencias]
mano-ip:           6/6 fieles  [OK]     mano-ip-trampas:           0/5  [5 divergencias]
mano-casefold:     6/6 fieles  [OK]     mano-casefold-trampas:     2/8  [6 divergencias]
```

**36 de 36 casos corrientes, 41 de 46 trampas divergen.** No es que las seis
reescrituras estén mal escritas: es que cada una tomó una decisión razonable
que la función real no toma.

- `line.split(",")` no entiende comillas: `"a,b",c` sale partido en tres.
- `line.split()` no entiende `"a b" c`, ni `a\ b c`, ni `a#b`.
- `split("://")` pierde el fragmento, el usuario, el esquema en mayúsculas y las
  URLs que empiezan por `//`.
- `textwrap.wrap` parte palabras largas y por guiones; la reescritura no.
- Un `split(".")` de cuatro partes no ve IPv6 y acepta `1.2.3.04`, que
  `ipaddress` rechaza.
- `lower()` no es `casefold()`: `Straße` da `strasse` en una y `straße` en otra.

Este banco cierra el argumento del proyecto. No hace falta un modelo, ni un
cambio de lenguaje, ni un proyecto grande: **una función de veinte líneas
reescrita a mano ya no es equivalente, y nadie lo nota hasta que se prueba a
propósito.** El corpus se reconstruye con `python estudio/portes/casos.py` y las
divergencias se listan con `python estudio/portes/probe.py`. El detalle de las
seis parejas está en `estudio/portes/LEEME.md`.

### 7.7 Cuánto del original ejecuta el corpus

La crítica más justa a este proyecto es que un corpus solo demuestra lo que
contiene. `fiel coverage` le pone número a esa frase: ejecuta el original una
vez por caso, con el módulo `trace` de la biblioteca estándar, y cuenta cuántas
líneas con sentencia se han ejecutado al menos una vez.

| pareja | casos | sentencias | cubiertas | % |
|---|---:|---:|---:|---:|
| `cron` (demo) | 10 | 28 | 27 | 96,4 % |
| `url` | 40 | 61 | 42 | 68,9 % |
| `toml` | 40 | 134 | 108 | 80,6 % |
| `slug` | 40 | 30 | 26 | 86,7 % |
| `semver` real | 40 | 25 | 22 | 88,0 % |
| **todo `fiel.estudio.toml`** | **312** | **729** | **609** | **83,5 %** |

Que la cifra global sea 83,5 % y no 100 % es el dato interesante, y va en la
memoria tal cual. En `url`, por ejemplo, quedan sin tocar 19 líneas: ramas de
error que el corpus nunca provoca. Un port puede haberlas escrito de otra
forma y la comprobación no lo verá. Saber dónde está ese hueco vale más que un
porcentaje redondo; por eso el comando imprime los rangos exactos y admite
`--min 80`, que devuelve código 1 cuando la cobertura baja del umbral.

Las seis reescrituras a mano dan 100 % de cobertura con siete u ocho
sentencias cada una: son funciones de una sola rama y el corpus las recorre
entera. La diferencia entre 100 % ahí y 68,9 % en `url` no mide la calidad del
corpus, mide el tamaño del programa original.

---

## 8. Resultados

| pareja | casos | fieles | divergencias |
|---|---|---|---|
| cron-fiel | 10 | 10 | 0 |
| cron-roto | 10 | 8 | 2 |
| cron-rust | 10 | 10 | 0 |
| cron-rust-trampas | 3 | 0 | 3 |
| url | 40 | 40 | 0 |
| url-trampas | 9 | 4 | 5 |
| toml | 40 | 40 | 0 |
| toml-trampas | 8 | 3 | 5 |
| slug | 40 | 40 | 0 |
| slug-trampas | 7 | 2 | 5 |
| semver-real | 40 | 40 | 0 |
| semver-real-trampas | 8 | 3 | 5 |
| semver-real-fijo | 5 | 5 | 0 |
| mano-csv | 6 | 6 | 0 |
| mano-csv-trampas | 8 | 2 | 6 |
| mano-shlex | 6 | 6 | 0 |
| mano-shlex-trampas | 8 | 1 | 7 |
| mano-url | 6 | 6 | 0 |
| mano-url-trampas | 11 | 0 | 11 |
| mano-wrap | 6 | 6 | 0 |
| mano-wrap-trampas | 6 | 0 | 6 |
| mano-ip | 6 | 6 | 0 |
| mano-ip-trampas | 5 | 0 | 5 |
| mano-casefold | 6 | 6 | 0 |
| mano-casefold-trampas | 8 | 2 | 6 |
| **total** | **312** | **246** | **66** |

Casos únicos grabados: **302**. Comprobaciones por vuelta: **312** (el corpus
del ejemplo del rango lo usan dos parejas). Divergencias encontradas: **66**.

Las tres filas del estudio se miden en **menos de cuatro segundos**: 1,4 s los
ports de Rust, 0,9 s las dos bibliotecas reales y 1,5 s las seis reescrituras a
mano. Ese es el dato que permite meter la comprobación en un `pre-commit` sin
que nadie la quite por lenta.

Las divergencias no son de sintaxis. Son de comportamiento:

- Python acepta `1_0` como 10; Rust no.
- Python acepta `" 9"` con espacio; Rust no.
- Python maneja enteros de cualquier tamaño; Rust desborda.
- Python quita acentos (`Café` → `cafe`); Rust no.
- Un navegador trata `http://x:80` igual que `http://x`; un parser ingenuo, no.
- IPv6 sin puerto rompe un `split(':')` mal hecho.
- Dos bibliotecas del mismo estándar ordenan distinto dos versiones que solo
  cambian en la metadata de build: una la ignora (como dice el estándar) y la
  otra no.
- Una reescritura "a mano" de `csv`, `shlex`, `url`, `wrap`, `ip` o `casefold`
  pasa los seis casos corrientes y falla 41 de las 46 trampas: comillas, escapes,
  fragmentos, IPv6, palabras largas, `ß`.

---

## 9. Limitaciones

Están en el README y se repiten aquí porque un proyecto que declara sus límites
es más creíble que uno que los esconde.

1. **El corpus solo cubre lo que cubre.** Una entrada que no esté grabada no se
   comprueba. Por eso existe `fiel add`: la garantía crece con el uso.
2. **Fiel no sabe si el original es correcto.** Si el original tiene un fallo y
   el port lo copia, los dos son fieles y los dos están mal. Mide equivalencia,
   no corrección.
3. **El binario de Rust es específico de la plataforma.** En el repositorio hay
   una especificación para Windows y otra para Linux; cada una apunta a su
   binario.
4. **La comparación necesita una regla.** Si dos programas devuelven lo mismo
   escrito de otra forma (JSON con claves desordenadas, por ejemplo), hay que
   decírselo con `normalize` o aparecerán falsos positivos.
5. **El estudio tiene una sola fila de modelos.** El generador está preparado
   para tres modelos gratuitos, pero las claves son personales y no se guardan
   en el repositorio.

---

## 10. Conclusiones

1. La equivalencia no se demuestra una vez. Se mantiene.
2. Un port que pasa los tests puede no ser equivalente: los cuatro targets lo
   demuestran con 20 divergencias reales, dos bibliotecas del mismo estándar
   añaden otras 5 y seis reescrituras a mano añaden 41 más.
3. La herramienta es pequeña a propósito. Su valor no está en las líneas, sino
   en que produce una respuesta binaria y verificable en cada cambio.
4. El límite principal no es técnico, es de cobertura: el corpus es el activo.
5. Cuando dos implementaciones del mismo estándar discrepan, ninguna de las dos
   lo sabe. Hace falta un tercero que las ejecute y las compare.

---

## 11. Trabajo futuro

- Añadir más targets (CSV, expresiones regulares, fechas).
- Completar el estudio con tres modelos gratuitos y 108 generaciones.
- Publicar la acción en GitHub Marketplace.
- Adaptar el corpus de `rust-anything` para medir ports que no sean propios.
- Integrar el informe HTML en la página del pull request.

---

## 12. Manual de usuario

Instalación:

```bash
pip install .
```

Uso mínimo:

```bash
fiel init                      # crea fiel.toml
fiel record                    # graba el original
fiel check                     # comprueba el port
```

En GitHub Actions:

```yaml
- run: pip install . && fiel check --format github
```

Informe visual:

```bash
fiel --spec fiel.estudio.toml report --out informe.html --open
```

---

## 13. Planificación, horas y riesgos

| fase | horas previstas | horas reales* |
|---|---|---|
| Análisis y diseño | 10 | 9 |
| Motor (corpus, comparación, CLI) | 25 | 28 |
| Ejemplos y ports en Rust | 12 | 16 |
| Pruebas y CI | 8 | 7 |
| Estudio y resultados | 8 | 6 |
| Memoria y presentación | 18 | 14 |
| **Total** | **81** | **80** |

\* Estimación sobre el registro de trabajo del repositorio (commits y sesiones).
Ajusta la columna a tus horas reales si llevas otro registro.

Riesgos y cómo se resolvieron:

| riesgo | solución |
|---|---|
| No hay Visual Studio Build Tools en Windows | se compiló con MinGW y `--target x86_64-pc-windows-gnu` |
| El PATH no ve el comando recién instalado | `python -m fiel` como alternativa documentada |
| El corpus se queda viejo si el original cambia | `fiel check` avisa con la lista de casos afectados |
| Un rojo intencionado tapa una regresión real | los ejemplos con trampas no están en el CI principal |

---

## 14. Glosario

- **port**: traducción de un programa a otro lenguaje.
- **corpus**: lista de entradas con la respuesta que dio el original.
- **divergencia**: una entrada donde el port responde distinto.
- **normalizar**: limpiar las dos respuestas antes de compararlas.
- **baseline**: lista de fallos que ya existían y se aceptan.
- **bisect**: buscar el cambio exacto que rompió la equivalencia.
- **golden test**: comparar contra una salida guardada.
- **CI**: ejecutar las comprobaciones automáticamente en cada cambio.

---

## 15. Bibliografía y referencias

- Repositorio del proyecto: `https://github.com/Barbarno/fiel`
- Pull request con la regresión: `https://github.com/Barbarno/fiel/pull/1`
- `rust-anything`: `https://github.com/erkamyaman/rust-anything`
- Documentación de GitHub Actions.
- Documentación de Python 3.11 (`subprocess`, `json`, `base64`, `unicodedata`).
- Documentación de Rust (`std::io`, `parse`, `String`).
- Especificación SemVer 2.0.0: `https://semver.org`
- `semver` para Python: `https://pypi.org/project/semver/`
- `semver` para Rust: `https://docs.rs/semver/latest/semver/struct.Version.html`
