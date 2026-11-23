# Dos bibliotecas reales, el mismo estándar

Este ejemplo no compara una función escrita para el proyecto con su traducción.
Compara **dos bibliotecas mantenidas por otras personas** que implementan el
mismo estándar, [SemVer 2.0.0](https://semver.org):

| lado | biblioteca | versión |
|---|---|---|
| original | [`semver` para Python](https://pypi.org/project/semver/) | 3.1.2 |
| port | [`semver` para Rust](https://crates.io/crates/semver) | 1.0.28 |

## La diferencia que encontró fiel

El estándar dice, en el punto 10:

> *Build metadata MUST be ignored when determining version precedence. Thus two
> versions that differ only in the build metadata, have the same precedence.*

Las dos bibliotecas lo cumplen, pero lo exponen con nombres distintos:

- Python: `semver.compare(a, b)` ignora la metadata de build.
- Rust: `Version::cmp` **la tiene en cuenta**; la comparación del estándar está
  en `Version::cmp_precedence`.

El crate lo documenta así:

> `cmp_precedence`: *Compare the major, minor, patch, and pre-release value of
> two versions, disregarding build metadata. [...] This comparison is what the
> SemVer spec refers to as "precedence".*

## Por qué esto importa

Un port mecánico traduce `semver.compare(a, b)` a `a.cmp(&b)`. Compila, pasa los
casos normales y **cambia el orden de versiones que solo difieren en build**:

```
1.0.0+build2  vs  1.0.0+build1
  python-semver -> 0   (misma precedencia, como dice el estándar)
  semver-rs     -> 1   (build2 es mayor)
```

Ningún test escrito a mano mira esto, porque los tests se escriben con versiones
"normales". `fiel` sí, porque ejecuta las dos bibliotecas sobre las mismas
entradas.

## Los tres corpus

| corpus | casos | qué demuestra |
|---|---|---|
| `cases/normal.txt` | 40 | las dos bibliotecas coinciden en todo lo corriente |
| `cases/traps.txt` | 8 | 5 divergencias: 3 de orden y 2 de desbordamiento |
| `cases/orden.txt` | 5 | el port corregido (`cmp_precedence`) las pasa todas |

```
semver-real:          40/40 fieles  [OK]
semver-real-trampas:   3/8  fieles  [5 divergencias]
semver-real-fijo:      5/5  fieles  [OK]
```

## Cómo ejecutarlo

```bash
pip install semver
cd rust-port && cargo build --release --target x86_64-pc-windows-gnu
cd .. && fiel check
```

En Linux o macOS, compila con `cargo build --release` y apunta `port` al binario
de `target/release/`.

## Las dos divergencias que quedan

`18446744073709551616.0.0` y `99999999999999999999.0.0` caben en Python y no en
un `u64`. No es un fallo del crate: es el tipo que eligió. Se queda documentado
como límite, que es lo que hace un proyecto honesto con sus resultados.
