# Guion de la demostración

Duración: **unos 6 minutos** de reloj, 5 de ellos hablando. Diez actos.
Todo pasa en tu portátil. No hace falta internet, ni GitHub, ni permisos.
El único acto que usa el navegador es el 7 (abre un HTML local) y el 10
(enseña el pull request ya abierto en otra pestaña).

---

## Antes de empezar (5 minutos antes, en el pasillo)

1. Abre una terminal **nueva** en `C:\Users\Dano\Documents\Default Project\fiel`.
2. Comprueba que responde: `fiel --version` → debe decir `fiel 0.2.0`.
   Si no responde: `python -m fiel --version` y usa esa forma en todo el guion.
3. Ten abierta en el navegador, en otra pestaña, esta dirección:
   `https://github.com/Barbarno/fiel/pull/1`
4. Sube el tamaño de letra de la terminal: **Ctrl + rueda del ratón**. Que se lea desde la última fila.
5. Comprueba que los binarios en Rust están compilados:

```powershell
@(
  "examples\rust-demo\rust-port\target\x86_64-pc-windows-gnu\release\cron-rs.exe",
  "examples\targets\url\rust-port\target\x86_64-pc-windows-gnu\release\url-rs.exe",
  "examples\real-semver\rust-port\target\x86_64-pc-windows-gnu\release\semver-rs.exe",
  "examples\real-semver\rust-port\target\x86_64-pc-windows-gnu\release\precedence.exe"
) | ForEach-Object { "$(Test-Path $_)  $_" }
```

Deben salir cuatro `True`. Si alguno dice `False`:

```powershell
cargo build --release --target x86_64-pc-windows-gnu --manifest-path examples\rust-demo\rust-port\Cargo.toml
cargo build --release --target x86_64-pc-windows-gnu --manifest-path examples\targets\url\rust-port\Cargo.toml
cargo build --release --target x86_64-pc-windows-gnu --manifest-path examples\real-semver\rust-port\Cargo.toml
```

El acto 9 no necesita compilar nada: son dos scripts de Python.

6. Si algo va mal, tienes el plan B al final de este documento.

---

## Acto 1 — El problema (45 segundos, sin tocar el teclado)

Di esto, mirando al tribunal:

> "Cuando una empresa reescribe código en otro lenguaje, hoy usa IA para
> traducirlo. Y luego comprueba que funciona con los tests que tenga.
> El problema es que los tests no cubren lo que nadie pensó.
> Mi proyecto comprueba otra cosa: que el código nuevo hace **exactamente**
> lo mismo que el viejo. Y lo comprueba otra vez en cada cambio."

No abras nada todavía. Deja que se asiente.

---

## Acto 2 — El port fiel (40 segundos)

Lanza:

```powershell
fiel --root examples/demo check --pair cron-fiel
```

Aparece:

```
cron-fiel: 10/10 fieles  [OK]
```

> "Este es un port fiel. Diez casos grabados del original, todos coinciden.
> La puerta está abierta."

---

## Acto 3 — La línea que lo rompe (60 segundos) ← **el momento**

Abre el fichero:

```powershell
notepad examples\demo\port.py
```

Busca la línea `return list(range(start, end + 1))` y quita el `+ 1`.
Guarda, cierra el bloc de notas, y lanza:

```powershell
fiel --root examples/demo check --pair cron-fiel
```

Aparece:

```
cron-fiel: 8/10 fieles  [2 divergencias]

Divergencias (2), primeras 2:
  [output] caso c0004: original='5,6,7,8,9' port='5,6,7,8'
  [output] caso c0005: original='0' port=''
```

Y el código de salida es 1.

> "Un carácter. El programa compila, arranca y no lanza ninguna excepción.
> Pasa cualquier test que no pruebe justo este caso.
> Y aquí sale el caso exacto: la entrada, lo que hacía el original y lo que
> hace ahora."

Pausa de dos segundos. Que se lea.

---

## Acto 4 — Se restaura (20 segundos)

```powershell
git checkout -- examples/demo/port.py
fiel --root examples/demo check --pair cron-fiel
```

Vuelve a `10/10 fieles`.

> "La puerta se abre y se cierra sola. Eso es lo que se ejecuta en GitHub en
> cada pull request."

---

## Acto 5 — Un port de verdad, en Rust (50 segundos)

```powershell
fiel --root examples/rust-demo check
```

```
cron-rust: 10/10 fieles  [OK]
```

> "Este no es un ejemplo de juguete. Es un binario compilado en Rust,
> comparado contra el original en Python. Diez casos, todos fieles."

Si te preguntan si el Rust lo escribiste tú, di la verdad: lo generó una IA y
tú lo compilaste, lo probaste y lo mediste. El proyecto **no** escribe el port;
comprueba que el port es correcto. Eso está en el README.

---

## Acto 6 — El hallazgo real (60 segundos) ← **el segundo momento**

```powershell
fiel demo
```

Deja que corra (3 segundos) y señala el acto 5 de su salida:

```
cron-rust: 10/13 fieles
  - caso u0001: original='ok' port='err'   → 1_0
  - caso u0002: original='ok' port='err'   → "5 - 9"
  - caso u0003: original='ok' port='err'   → número de 20 dígitos
```

> "Estos tres los encontró la herramienta, no yo. En Python se pueden escribir
> `1_0` o `5 - 9` y los entiende. En Rust, no. Y un número de veinte dígitos
> cabe en Python y desborda en Rust.
> Nadie escribe un test con `1_0` dentro. Por eso los tests no lo encuentran
> y esto sí."

---

## Acto 7 — El informe, en una pantalla (40 segundos)

```powershell
fiel --spec fiel.estudio.toml report --out informe.html --open
```

Se abre el navegador con el informe. Señala las cuatro tarjetas de arriba y una
divergencia cualquiera.

> "Todo lo que han visto en la consola, aquí. Seis ejemplos, 312 comprobaciones
> y 66 divergencias, cada una con la entrada exacta que la provocó: `5-9`,
> `1_0`, `Café`, un número de veinte cifras, `"a,b",c`.
> Sin javascript y sin conexión: el fichero se adjunta a la memoria y se abre
> en cualquier ordenador."

Si no quieres abrir el navegador en medio: ejecuta sin `--open` y enseña el
fichero desde la carpeta.

---

## Acto 8 — Dos bibliotecas reales (40 segundos)

```powershell
fiel --root examples/real-semver check --pair semver-real-trampas
```

```
semver-real-trampas: 3/8 fieles  [5 divergencias]
  caso u0001: original='0' port='-1'
```

> "Esto no es un ejemplo mío. Son dos bibliotecas reales del mismo estándar:
> la de Python y la de Rust. Para el estándar, dos versiones que solo cambian
> en la metadata de build son iguales. Python lo hace así; el crate de Rust,
> con su comparación normal, no.
> Un port mecánico traduce `compare` por `cmp` y cambia el orden. Los 40 casos
> normales no lo ven. Estos tres, sí."

Y el arreglo:

```powershell
fiel --root examples/real-semver check --pair semver-real-fijo
```

> "La corrección es cambiar `cmp` por `cmp_precedence`. Una línea. Cero
> divergencias.
> Eso es lo que hace útil a la herramienta: no señala un problema, señala el
> arreglo."

---

## Acto 9 — Seis reescrituras a mano (35 segundos)

```powershell
fiel --root estudio/portes check --pair mano-csv --pair mano-csv-trampas
```

```
mano-csv:          6/6 fieles  [OK]
mano-csv-trampas:  2/8 fieles  [6 divergencias]
```

> "Y el caso más común de todos: no un modelo, no un cambio de lenguaje. Alguien
> reescribe `csv` a mano porque parece fácil. Seis casos corrientes, seis
> aciertos.
> Las comillas no las entiende. `"a,b",c` lo parte en tres.
> Hay seis parejas así: `csv`, `shlex`, `url`, `wrap`, `ip`, `casefold`. Las seis
> pasan lo corriente y fallan 41 de las 46 trampas.
> Una función de veinte líneas reescrita a mano ya no es equivalente."

---

## Acto 10 — El registro (30 segundos)

Cambia a la pestaña del navegador con el pull request.

> "Esto es el mismo proceso, de verdad, en un repositorio público.
> Abrí un pull request con una regresión a propósito.
> GitHub puso el check en rojo en diez segundos, con el caso exacto.
> Se cerró sin fusionar para dejar la rama principal en verde.
> El registro queda ahí y lo puede ver cualquiera."

---

## Cierre (20 segundos)

> "La migración con IA demuestra la equivalencia el día que migras.
> Esto la demuestra el día mil."

Fin. No digas nada más. Deja que pregunten.

---

## Las ocho preguntas que te van a hacer

**"¿Esto no existe ya?"**
> `rust-anything`, con 7.800 estrellas, hace la migración y demuestra la
> equivalencia ese día. Su propio README dice que solo detecta lo que cubre la
> grabación. Yo trabajo a partir de ahí: corpus versionado, baseline para
> adoptarlo en proyectos que ya venían con fallos, y `bisect` para encontrar el
> commit que la rompió.

**"¿Por qué no usas los tests normales?"**
> Un test dice "esto funciona". Esto dice "esto sigue comportándose igual que
> el original". Son cosas distintas. Además los tests se escriben una vez y se
> olvidan; el corpus se amplía solo con `fiel add` cada vez que aparece un fallo.

**"¿Qué pasa si el corpus no cubre un caso?"**
> Que no lo detecta. Es el límite y está en el README. Por eso `fiel add`
> existe: cada fallo real se añade y queda cubierto para siempre. La garantía
> crece con el uso, no nace completa.

**"¿Cómo sabes que la comparación es justa?"**
> Normalizando antes de comparar. `text` iguala saltos de línea y quita espacios
> al final; `json` ordena claves; `bytes` compara exacto. Sin eso, el 90% de los
> avisos serían diferencias de formato y la herramienta sería inservible.

**"¿Qué es el baseline?"**
> Si llegas a un proyecto que ya tenía divergencias, la herramienta te bloquea
> el primer día y la tiras a la basura. El baseline acepta las que ya existen y
> solo falla con las nuevas. Es lo que hace que se pueda adoptar.

**"¿Cómo encuentra el commit?"**
> Recorre los commits de un rango en un worktree temporal, de viejo a nuevo, y
> se queda con el primero que falla. Lineal, no binario, a propósito: la
> fidelidad no tiene por qué ser monótona y una búsqueda binaria puede mentir.

**"¿Cuánto tarda?"**
> Los 312 casos, tres segundos. La demo entera, menos de dos. En GitHub, el
> trabajo completo tarda entre veinte y treinta segundos, y la mayoría es
> instalar y compilar.

**"¿Qué harías con más tiempo?"**
> Completar el estudio con dos modelos gratuitos más (el generador ya está
> hecho; faltan las claves), y adaptar el corpus de `rust-anything` para medir
> ports que no sean míos. Lo que no haría es añadir funciones: cinco ejemplos y
> seis reescrituras a mano ya cubren los cuatro modos de fallo que me interesan
> —números, texto, Unicode y decisiones de API.

---

## Plan B

| si falla | qué haces |
|---|---|
| `fiel` no se reconoce | usa `python -m fiel` en todos los comandos |
| un binario de Rust no está compilado | salta ese acto: el 6 avisa de que falta, el 8 solo necesita `semver-rs`, el 9 no compila nada |
| no hay internet | los actos 1 a 9 no lo necesitan (el 7 abre un HTML local); el 10 lo cuentas de palabra |
| `fiel demo` falla | ejecuta los actos 2 a 4 a mano; son el 80% de la demo |
| el informe no se abre | ejecuta `fiel --spec fiel.estudio.toml report --out informe.html` y ábrelo desde la carpeta |
| se te va el tiempo | actos 3, 6 y 9 son los que hay que enseñar sí o sí |

---

## Lo que no hagas

- No leas la salida en voz alta línea por línea. Señala el número que importa.
- No te disculpes por nada. Si algo falla, lo dices en una frase y sigues.
- No digas "esto es muy simple". Di qué problema resuelve.
- No prometas lo que el README dice que no hace. Los límites declarados suman.
