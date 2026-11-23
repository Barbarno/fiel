# Resultados

Generado por `python estudio/estudio.py medir`. No se edita a mano.

La primera fila son los ports de Rust del repositorio: los escribió un
asistente de IA en una pasada, a partir de la especificación de cada
función. La segunda compara dos bibliotecas reales del mismo estándar. La
tercera son seis funciones de la biblioteca estándar reescritas a mano.
Las filas de modelos aparecen al ejecutar `generar` con una clave.

| modelo | casos normales | fieles | trampas | divergencias en trampas | % fiel | tiempo |
|---|---|---|---|---|---|---|
| port de IA (Rust, una pasada) | 120 | 120 | 24 | 15 | 89.6% | 1.41 s |
| bibliotecas reales (python-semver vs semver-rs) | 40 | 40 | 8 | 5 | 89.6% | 0.9 s |
| reescritura a mano (stdlib, sin dependencias) | 36 | 36 | 46 | 41 | 50.0% | 1.48 s |

Detalle por target:

| modelo | target | casos | fieles | trampas | divergencias |
|---|---|---|---|---|---|
| port de IA (Rust, una pasada) | url | 40 | 40 | 9 | 5 |
| port de IA (Rust, una pasada) | toml | 40 | 40 | 8 | 5 |
| port de IA (Rust, una pasada) | slug | 40 | 40 | 7 | 5 |
| bibliotecas reales (python-semver vs semver-rs) | semver | 40 | 40 | 8 | 5 |
| reescritura a mano (stdlib, sin dependencias) | csv | 6 | 6 | 8 | 6 |
| reescritura a mano (stdlib, sin dependencias) | shlex | 6 | 6 | 8 | 7 |
| reescritura a mano (stdlib, sin dependencias) | url | 6 | 6 | 11 | 11 |
| reescritura a mano (stdlib, sin dependencias) | wrap | 6 | 6 | 6 | 6 |
| reescritura a mano (stdlib, sin dependencias) | ip | 6 | 6 | 5 | 5 |
| reescritura a mano (stdlib, sin dependencias) | casefold | 6 | 6 | 8 | 6 |
