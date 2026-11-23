# Cómo añadir filas a la tabla

La tabla ya trae tres filas hechas, todas medibles sin clave ni conexión:

| fila | qué es |
|---|---|
| port de IA (Rust, una pasada) | los tres ports de `examples/targets`, escritos por un asistente |
| bibliotecas reales | `semver` de Python contra `semver` de Rust |
| reescritura a mano (stdlib) | seis funciones de la biblioteca estándar reescritas a mano |

Las dos primeras se miden solas: los binarios de Rust tienen que estar
compilados (`cargo build --release --target x86_64-pc-windows-gnu`). La tercera
no necesita compilar nada.

Para añadir filas de modelos hace falta una clave gratuita. Dos minutos.

## 0. Rehacer la fila de las reescrituras

Solo si se tocan los corpus:

```powershell
python estudio/portes/casos.py       # reescribe normal.txt y trampas.txt
python estudio/portes/probe.py       # dice qué entradas divergen
```

Y se vuelven a grabar con `fiel add --root estudio/portes add --pair mano-csv ...`.
El detalle está en `estudio/portes/LEEME.md`.

## 1. Saca la clave

Cualquiera de los tres sirve. Groq es el más rápido de configurar.

| proveedor | dónde | variable |
|---|---|---|
| Groq | console.groq.com/keys | `GROQ_API_KEY` |
| Gemini | aistudio.google.com/apikey | `GEMINI_API_KEY` |
| OpenRouter | openrouter.ai/keys | `OPENROUTER_API_KEY` |

## 2. Compruébalo

```powershell
$env:GROQ_API_KEY = "gsk_..."
python estudio/estudio.py estado
```

Debe decir `clave lista`.

## 3. Genera y mide

```powershell
python estudio/estudio.py generar --modelo groq
python estudio/estudio.py medir
```

`generar` escribe tres ficheros en `estudio/salidas/groq/` (url, toml, slug).
`medir` los pasa por el mismo instrumento que todo lo demás y reescribe
`resultados.md` y `resultados.csv`.

## 4. Repite con otro modelo

```powershell
$env:GEMINI_API_KEY = "..."
python estudio/estudio.py generar --modelo gemini
python estudio/estudio.py medir
```

Cada modelo añade una fila. No hay que tocar código.

## Qué mirar en la tabla

- **casos normales**: si suspende aquí, el port ni siquiera funciona.
- **trampas**: aquí está el estudio. Un modelo puede aprobar todo lo normal y
  fallar la mitad de los bordes.
- **% fiel**: el número global, útil solo si se lee con las dos columnas
  anteriores al lado.
- **tiempo**: lo que tarda la fila entera. Sirve para decidir si esto cabe en un
  `pre-commit`; hoy cabe: las tres filas juntas, menos de cuatro segundos.

## La clave no se guarda

Se lee de la variable de entorno y no se escribe en ningún fichero. Si cierras
la terminal, hay que volver a exportarla.
