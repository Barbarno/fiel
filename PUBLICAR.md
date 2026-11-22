# Publicar fiel en GitHub

Tres pasos. El tercero solo lo puedes hacer tú, porque necesita tu cuenta.

## 1. Crear el repositorio local (ya está hecho si existe .git)

```powershell
cd "C:\Users\Dano\Documents\Default Project\fiel"
git status
```

Si no existe, se crea en el paso 2.

## 2. Primer commit

```powershell
cd "C:\Users\Dano\Documents\Default Project\fiel"
git init
git add -A
git commit -m "fiel 0.1: guardian de equivalencia para ports"
```

## 3. Subirlo (necesita tu cuenta)

1. Entra en https://github.com/new
2. Nombre: `fiel`
3. Visibilidad: **Public** (necesario para tener minutos de Actions ilimitados)
4. No marques "Add a README", "Add .gitignore" ni "Choose a license": ya los tienes
5. Copia los comandos que GitHub te muestra y ejecútalos:

```powershell
git remote add origin https://github.com/TU-USUARIO/fiel.git
git branch -M main
git push -u origin main
```

## 4. Ver la Action funcionando

En cuanto subas el código:

1. Ve a la pestaña **Actions** del repositorio
2. Verás el workflow `fiel` ejecutándose
3. Debe salir en verde: instala el paquete, pasa 41 pruebas y comprueba el ejemplo

Si quieres ver la puerta cerrándose de verdad:

1. Abre un pull request con cualquier cambio
2. Añade una línea al final de `examples/demo/port.py` que rompa la salida
3. Espera 40 segundos
4. El check aparece en rojo con el caso exacto

Ese check en rojo, en la captura de pantalla, es material directo para la memoria.

## Nota sobre el ejemplo en Rust

`examples/rust-demo` no está en el workflow porque su `fiel.toml` apunta al
binario de Windows y GitHub Actions corre sobre Linux. Para comprobarlo en CI
habría que añadir un job con `cargo build --release` y una variante del
`fiel.toml` con la ruta de Linux. Es un trabajo de veinte minutos si lo quieres
para la memoria.
