# demo.ps1 - guion de la presentacion, paso a paso.
#
# Uso normal (presentando):   .\demo.ps1
# Uso sin pausas (ensayo):    .\demo.ps1 -NoPause
#
# No necesita red. No necesita permisos. Deja los ficheros como estaban.
# No depende de que 'fiel' este en el PATH: usa el paquete del repositorio.

param([switch]$NoPause)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$puerto = Join-Path $root "examples\demo\port.py"
$copia = Join-Path $root "examples\demo\port.py.bak"

function Fiel {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$argumentos)
    & python -m fiel @argumentos
}

function Paso([string]$texto) {
    Write-Host ""
    Write-Host ("=" * 62) -ForegroundColor DarkGray
    Write-Host "  $texto" -ForegroundColor Cyan
    Write-Host ("=" * 62) -ForegroundColor DarkGray
}

function Pausa([string]$texto = "Enter para seguir") {
    if ($NoPause) { return }
    Write-Host ""
    Write-Host "  [$texto] " -ForegroundColor Yellow -NoNewline
    Read-Host
}

function Comando([string]$texto) {
    Write-Host ""
    Write-Host "  > $texto" -ForegroundColor White
    Write-Host ""
}

try {
    Write-Host ""
    Write-Host "  fiel - la equivalencia no se demuestra una vez" -ForegroundColor Green
    Write-Host "  se mantiene" -ForegroundColor DarkGray

    # ---------------------------------------------------------------
    Paso "1. El port fiel, comprobado contra el original"
    Comando "python -m fiel --root examples/demo check --pair cron-fiel"
    Fiel --root examples/demo check --pair cron-fiel
    Write-Host ""
    Write-Host "  Todo coincide con el original. Puerta abierta." -ForegroundColor Green
    Pausa

    # ---------------------------------------------------------------
    Paso "2. Alguien cambia una linea"
    Comando "list(range(start, end + 1))  ->  list(range(start, end))"
    Copy-Item $puerto $copia -Force
    $contenido = Get-Content $puerto -Raw
    $roto = $contenido.Replace("return list(range(start, end + 1))", "return list(range(start, end))")
    Set-Content -Path $puerto -Value $roto -NoNewline
    Write-Host "  (un caracter menos, el compilador no se queja)" -ForegroundColor DarkYellow
    Pausa "Enter para comprobar"

    # ---------------------------------------------------------------
    Paso "3. La puerta se cierra"
    Comando "python -m fiel --root examples/demo check --pair cron-fiel"
    Fiel --root examples/demo check --pair cron-fiel
    Write-Host ""
    Write-Host "  Codigo de salida 1. Con eso GitHub marca el pull request en rojo." -ForegroundColor Red
    Pausa

    # ---------------------------------------------------------------
    Paso "4. Se restaura y vuelve a estar fiel"
    Copy-Item $copia $puerto -Force
    Remove-Item $copia -Force
    Comando "python -m fiel --root examples/demo check --pair cron-fiel"
    Fiel --root examples/demo check --pair cron-fiel
    Pausa

    # ---------------------------------------------------------------
    Paso "5. Un port real, compilado en Rust"
    Comando "python -m fiel --root examples/rust-demo check"
    Fiel --root examples/rust-demo check
    Write-Host ""
    Write-Host "  Diez casos base. Todo fiel." -ForegroundColor Green
    Pausa

    # ---------------------------------------------------------------
    Paso "6. Casos trampa: donde Python y Rust no coinciden"
    Comando "python -m fiel demo"
    Fiel demo
    Pausa

    # ---------------------------------------------------------------
    Paso "7. Cuanto del original queda sin probar"
    Comando "python -m fiel --spec fiel.estudio.toml coverage --pair url"
    Fiel --spec fiel.estudio.toml coverage --pair url
    Write-Host ""
    Write-Host "  61 sentencias, 42 ejecutadas por el corpus. Las 19 que faltan" -ForegroundColor DarkYellow
    Write-Host "  son el hueco real: ahi un port puede desviarse sin que se vea." -ForegroundColor DarkYellow
    Pausa

    # ---------------------------------------------------------------
    Paso "8. La entrada que dicta el tribunal"
    $entrada = "http://host/a#b"
    Write-Host ""
    Write-Host "  Esta URL no esta en ningun corpus. Se escribe ahora mismo." -ForegroundColor DarkGray
    if (-not $NoPause) {
        Write-Host "  Escribe una (Enter para dejar $entrada): " -ForegroundColor Yellow -NoNewline
        $leida = Read-Host
        if ($leida) { $entrada = $leida }
    }
    Comando "python -m fiel --root estudio/portes probe --pair mano-url --input ""$entrada"""
    Fiel --root estudio/portes probe --pair mano-url --input $entrada
    Write-Host ""
    Write-Host "  Esa es la reescritura a mano. La misma entrada, contra el port" -ForegroundColor DarkGray
    Write-Host "  bueno de Rust:" -ForegroundColor DarkGray
    Comando "python -m fiel --spec fiel.estudio.toml probe --pair url --input ""$entrada"""
    Fiel --spec fiel.estudio.toml probe --pair url --input $entrada
    Write-Host ""
    Write-Host "  Dos veredictos distintos con la misma entrada, en menos de un segundo." -ForegroundColor Green
    Pausa

    # ---------------------------------------------------------------
    Paso "9. El informe: los mismos numeros, en una pantalla"
    if ($NoPause) {
        Comando "python -m fiel --spec fiel.estudio.toml report --out informe.html"
        Fiel --spec fiel.estudio.toml report --out informe.html
    }
    else {
        Comando "python -m fiel --spec fiel.estudio.toml report --out informe.html --open"
        Fiel --spec fiel.estudio.toml report --out informe.html --open
    }
    Write-Host ""
    Write-Host "  312 casos, 66 divergencias, cada una con su entrada exacta." -ForegroundColor Green
    Pausa

    # ---------------------------------------------------------------
    Paso "10. Dos bibliotecas reales del mismo estandar"
    Comando "python -m fiel --root examples/real-semver check --pair semver-real-trampas"
    Fiel --root examples/real-semver check --pair semver-real-trampas
    Write-Host ""
    Write-Host "  python-semver dice 0 (misma precedencia); semver-rs dice 1." -ForegroundColor DarkYellow
    Pausa "Enter para ver el arreglo"
    Comando "python -m fiel --root examples/real-semver check --pair semver-real-fijo"
    Fiel --root examples/real-semver check --pair semver-real-fijo
    Write-Host ""
    Write-Host "  cmp -> cmp_precedence: una linea, cero divergencias." -ForegroundColor Green
    Pausa

    # ---------------------------------------------------------------
    Paso "11. Seis funciones de la stdlib reescritas a mano"
    Comando "python -m fiel --root estudio/portes check --pair mano-csv --pair mano-csv-trampas"
    Fiel --root estudio/portes check --pair mano-csv --pair mano-csv-trampas
    Write-Host ""
    Write-Host "  6 de 6 en lo corriente; las comillas no las entiende." -ForegroundColor DarkYellow
    Write-Host "  Las seis parejas: 36/36 normal, 41 de 46 trampas divergen." -ForegroundColor DarkYellow
    Pausa

    # ---------------------------------------------------------------
    Paso "12. El registro: un pull request real con el check en rojo"
    $url = "https://github.com/Barbarno/fiel/pull/1"
    Write-Host ""
    Write-Host "  $url" -ForegroundColor Blue
    Write-Host ""
    Write-Host "  El check 'fidelidad' esta en rojo con el caso exacto" -ForegroundColor DarkGray
    Write-Host "  que rompio la equivalencia. Se cerro sin fusionar." -ForegroundColor DarkGray
    if (-not $NoPause) {
        Write-Host ""
        Write-Host "  [Enter para abrirlo en el navegador] " -ForegroundColor Yellow -NoNewline
        Read-Host | Out-Null
        Start-Process $url
    }
    Pausa "Fin. Enter para cerrar"

    Write-Host ""
    Write-Host "  La migracion con IA demuestra el dia uno." -ForegroundColor Green
    Write-Host "  Esto demuestra el dia mil." -ForegroundColor Green
    Write-Host ""
}
finally {
    if (Test-Path $copia) {
        Copy-Item $copia $puerto -Force
        Remove-Item $copia -Force
        Write-Host "  (port.py restaurado)" -ForegroundColor DarkGray
    }
    Set-Location $root
}

# Un acto termina con el check en rojo a proposito (la entrada que no es fiel).
# El guion, como pieza, sale siempre bien.
exit 0
