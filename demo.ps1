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
    Paso "7. El informe: los mismos numeros, en una pantalla"
    Comando "python -m fiel --spec fiel.estudio.toml report --out informe.html --open"
    Fiel --spec fiel.estudio.toml report --out informe.html --open
    Write-Host ""
    Write-Host "  177 casos, 20 divergencias, cada una con su entrada exacta." -ForegroundColor Green
    Pausa

    # ---------------------------------------------------------------
    Paso "8. El registro: un pull request real con el check en rojo"
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
