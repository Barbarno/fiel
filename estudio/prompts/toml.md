# Target: toml

Escribe `parse(linea: str) -> str` y un `main()` que lea una linea de TOML por
stdin. Es el subconjunto que aparece en un fichero de configuracion, no TOML
completo: no hay secciones `[tabla]`, ni fechas, ni tablas inline.

La salida es una sola linea:

```
clave|tipo|valor
```

Tipos admitidos:

- `int`: entero con signo opcional, guiones bajos entre digitos, sin ceros a la
  izquierda (`0` si, `007` no). Tamano arbitrario. Se normaliza: `+5` -> `5`,
  `1_000` -> `1000`, `-0` -> `0`.
- `string`: comillas dobles, con los escapes `\\n`, `\\t`, `\\"`, `\\\\` y
  `\\uXXXX`. Se muestra con los escapes visibles (`\\n` literal) para que quepa
  en una linea.
- `bool`: `true` o `false`.
- `array`: corchetes, elementos separados por comas. Los elementos son todos
  enteros o todos cadenas. Se muestran normalizados y separados por comas.
  Un array vacio se escribe con valor vacio.

Reglas:

- Un `#` fuera de comillas empieza un comentario y se descarta.
- La clave admite letras, digitos, `_`, `.` y `-`.
- Cualquier otra cosa es un error (stderr, codigo 1).

Ejemplos:

```
puerto = 8080              ->  puerto|int|8080
nombre = "servidor"        ->  nombre|string|servidor
ids = [1, 2, 3]            ->  ids|array|1,2,3
activo = true              ->  activo|bool|true
big = 99999999999999999999 ->  big|int|99999999999999999999
```
