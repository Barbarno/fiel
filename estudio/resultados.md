# Resultados

Generado por `python estudio/estudio.py medir`. No se edita a mano.

La primera fila son los ports de Rust del repositorio: los escribió un
asistente de IA en una pasada, a partir de la especificación de cada
función. Las demás filas aparecen al ejecutar `generar` con un modelo.

| modelo | casos normales | fieles | trampas | divergencias en trampas | % fiel |
|---|---|---|---|---|---|
| port de IA (Rust, una pasada) | 120 | 120 | 24 | 15 | 89.6% |

Detalle por target:

| modelo | target | casos | fieles | trampas | divergencias |
|---|---|---|---|---|---|
| port de IA (Rust, una pasada) | url | 40 | 40 | 9 | 5 |
| port de IA (Rust, una pasada) | toml | 40 | 40 | 8 | 5 |
| port de IA (Rust, una pasada) | slug | 40 | 40 | 7 | 5 |
