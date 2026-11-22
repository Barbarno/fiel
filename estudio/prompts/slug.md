# Target: slug

Escribe `slug(texto: str) -> str` y un `main()` que lea un texto por stdin y
escriba una sola linea: la version utilizable como parte de una URL.

Reglas, en este orden:

1. Recorta los espacios de los extremos. Si no queda nada, es un error
   (stderr, codigo 1).
2. Quita los acentos: `Café` -> `Cafe`, `Ñandú` -> `Nandu`, `über` -> `uber`.
   La forma correcta es normalizar a NFD y descartar las marcas diacriticas.
3. Pasa a minusculas.
4. Todo lo que no sea letra o digito se convierte en `-`.
5. Colapsa los guiones repetidos y recorta los de los extremos.
6. Si el resultado queda vacio, es un error.

Ejemplos:

```
"Hola Mundo"                  ->  hola-mundo
"Rust: rapido y seguro!"      ->  rust-rapido-y-seguro
"Café con Leche"              ->  cafe-con-leche
"  --hola--  "                ->  hola
```
