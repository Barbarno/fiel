# Target: url

Escribe `parse(url: str) -> str` y un `main()` que lea una URL por stdin.

La salida es una sola linea con siete campos separados por `|`:

```
esquema|usuario|host|puerto|ruta|query|fragmento
```

Reglas:

- Sin `://` es un error (salida por stderr, codigo 1).
- El esquema se pasa a minusculas. Solo admite letras, digitos y `+.-`;
  tiene que empezar por letra.
- El fragmento empieza en `#` y la query en `?`. Si no existen, el campo es `-`.
- Si no hay ruta, la ruta es `/`.
- El usuario va antes de `@`. Si no hay, `-`.
- El puerto va despues del ultimo `:`. Si no hay, `-`. Si no son digitos o
  pasa de 65535, es un error.
- El puerto por defecto del esquema (80 en `http`, 443 en `https`) se escribe
  como `-`, igual que hace un navegador.
- Un host IPv6 va entre corchetes: `[::1]`. El puerto, si lo hay, va despues
  del corchete: `[::1]:8080`.

Ejemplos:

```
https://example.com:8443/a/b?q=1#top  ->  https|-|example.com|8443|/a/b|q=1|top
http://example.com:80/a                ->  http|-|example.com|-|/a|-|-
ftp://ana@host/x                       ->  ftp|ana|host|-|/x|-|-
```
