# Seis reescrituras a mano

El caso más común de todos: alguien reescribe una función de la biblioteca
estándar porque le parece sencilla. No hay migración de lenguaje, no hay modelo,
no hay proyecto grande. Solo una función de veinte líneas escrita a mano.

Cada pareja tiene tres ficheros:

| fichero | qué es |
|---|---|
| `original.py` | la función real de Python (`csv`, `shlex`, `urlsplit`, `textwrap`, `ipaddress`, `unicodedata`) |
| `port.py` | la reescritura ingenua que haría cualquiera en cinco minutos |
| `normal.txt` / `trampas.txt` | las entradas de cada corpus, una por línea |

## Los seis pares

| pareja | qué hace | dónde falla la reescritura |
|---|---|---|
| `csv` | separa una línea CSV | comillas, comillas dobles, campos vacíos |
| `shlex` | separa argumentos de shell | comillas, escapes, `#` |
| `url` | separa las partes de una URL | fragmento, usuario, esquema en mayúsculas, `//` |
| `wrap` | parte texto en líneas de 10 | palabras largas, guiones, tabuladores |
| `ip` | normaliza una dirección IP | IPv6, ceros a la izquierda |
| `casefold` | minúsculas Unicode | `ß`, ligaduras, `İ` |

## Resultado

```
mano-csv:          6/6 fieles  [OK]     mano-csv-trampas:          2/8  [6 divergencias]
mano-shlex:        6/6 fieles  [OK]     mano-shlex-trampas:        1/8  [7 divergencias]
mano-url:          6/6 fieles  [OK]     mano-url-trampas:          0/11 [11 divergencias]
mano-wrap:         6/6 fieles  [OK]     mano-wrap-trampas:         0/6  [6 divergencias]
mano-ip:           6/6 fieles  [OK]     mano-ip-trampas:           0/5  [5 divergencias]
mano-casefold:     6/6 fieles  [OK]     mano-casefold-trampas:     2/8  [6 divergencias]
```

**36 de 36 casos corrientes, 41 de 46 trampas divergen.** Las seis pasan lo que
se le ocurre probar a quien las escribió.

## Reconstruirlo desde cero

```powershell
python estudio/portes/casos.py        # escribe normal.txt y trampas.txt
python estudio/portes/probe.py        # lista las entradas que divergen
```

`casos.py` tiene las dos listas fijas: las entradas corrientes y las raras. El
reparto no se hace mirando el resultado de `probe.py`; las listas están escritas
antes y el resultado es el mismo cada vez.

Para grabar los corpus en el formato de `fiel`:

```powershell
cd ../..
fiel --root estudio/portes add --pair mano-csv --file estudio/portes/csv/normal.txt
fiel --root estudio/portes add --pair mano-csv-trampas --file estudio/portes/csv/trampas.txt
```

Y lo mismo con `shlex`, `url`, `wrap`, `ip` y `casefold`.

## Comprobar

```powershell
fiel --root estudio/portes check
```

Sale con código 1 porque hay divergencias: es el resultado esperado, no un
fallo. Las parejas sin `-trampas` tienen que dar `[OK]`.

## Límite

El corpus es de 82 entradas. Cubre las decisiones que cada reescritura tomó sin
darse cuenta, no todas las que podría tomar. Un corpus más grande encuentra más;
la herramienta no puede demostrar lo que no ha probado.

El número exacto de divergencias depende de la versión de Unicode que traiga el
intérprete: `casefold` cambia cuando cambia la tabla. Con Python 3.13 salen 41;
con una versión anterior puede salir 40. Por eso el trabajo de GitHub exige al
menos 35 y no un número fijo: lo que protege es que las trampas sigan
divergiendo, no el recuento exacto.

Las dos versiones de cada pareja escriben su salida en UTF-8 de forma explícita.
Sin eso, en Windows la consola cp1252 tumbaba el proceso en las entradas con
`ß` o `İ` y el resultado dependía del idioma del sistema, no del código.
