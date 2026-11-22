# Cómo llenar las otras dos filas de la tabla

La tabla funciona con una fila porque los tres ports de Rust ya existen. Para
añadir modelos solo hace falta una clave gratuita. Dos minutos.

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

## La clave no se guarda

Se lee de la variable de entorno y no se escribe en ningún fichero. Si cierras
la terminal, hay que volver a exportarla.
