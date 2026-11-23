"""Reduccion de un caso que diverge hasta el minimo que sigue divergiendo.

Saber que el caso c0031 falla esta bien. Saber que falla por ocho caracteres
concretos es lo que permite arreglarlo. Esto es ddmin (Zeller y Hildebrandt,
2002) con una pasada de ventanas cortas delante: se prueban trozos, sus
complementos y las subcadenas mas pequenas que aun reproducen la misma
divergencia. El resultado es 1-minimo: quitarle un solo caracter deja de fallar.

    fiel shrink --pair mano-url --case c0007
    fiel shrink --pair mano-url --all
    fiel shrink --pair mano-url --case c0007 --write

`--write` anade la entrada minima al corpus como caso permanente, para que el
arreglo no pueda volver a romperse sin que salte la comprobacion.
"""

from __future__ import annotations

import base64
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from . import corpus as corpus_mod
from .compare import CompareError, Divergence, compare
from .corpus import Case
from .runner import ERR, OK, run
from .spec import Pair, Project

# Techo de ejecuciones por caso. Un corpus de una linea de 200 bytes se reduce
# en menos de 200 pruebas; el techo existe para que una entrada de 20 KB no
# convierta el comando en una tarde.
PRESUPUESTO = 300

# Hasta que tamano se buscan subcadenas sueltas antes de reducir. 8 cubre
# 'a#b', '[::1]:80' y casi cualquier token que dispare una regla distinta.
VENTANA = 8

# Por encima de esto la busqueda de ventanas no compensa: se va directo a ddmin.
LIMITE_VENTANAS = 512


class ShrinkError(Exception):
    pass


@dataclass(frozen=True)
class ShrinkResult:
    pair_id: str
    case_id: str
    antes: bytes
    despues: bytes
    divergencia_antes: Divergence
    divergencia_despues: Divergence | None
    ejecuciones: int
    segundos: float
    completo: bool

    @property
    def ahorro(self) -> int:
        return len(self.antes) - len(self.despues)


class _SinPresupuesto(Exception):
    """Se agoto el numero de ejecuciones: se devuelve lo reducido hasta ahora."""


def _caso_vacio(pair: Pair, payload: bytes) -> Case:
    """compare() solo mira el id y el estado; el estado se pone para pasar la
    guarda y nunca se usa para decidir, porque aqui no hay nada grabado."""
    return Case(id=pair.id, input=payload, status="ok", output=b"")


class EjecutorPar:
    """Lanza los dos lados de la pareja a la vez.

    Cada lado es un proceso distinto y `subprocess.run` suelta el GIL mientras
    espera, asi que el coste por prueba es el de un arranque, no el de dos.
    """

    def __init__(self) -> None:
        self.pool = ThreadPoolExecutor(max_workers=2)

    def __enter__(self) -> "EjecutorPar":
        return self

    def __exit__(self, *_exc) -> bool:
        self.pool.shutdown(wait=True)
        return False

    def observar(self, pair: Pair, project: Project, payload: bytes):
        original = self.pool.submit(
            run, pair.original.resolved(), payload, pair.timeout_ms, pair.original.working_dir(project.root)
        )
        port = self.pool.submit(
            run, pair.port.resolved(), payload, pair.timeout_ms, pair.port.working_dir(project.root)
        )
        return original.result(), port.result()


def predicado(
    pair: Pair,
    project: Project,
    firma: str | None,
    cualquier: bool = False,
    ejecutor: EjecutorPar | None = None,
):
    """Devuelve una funcion que dice si esa entrada sigue divergiendo.

    El ejecutor se pasa desde fuera para que un solo hilo acompanie a todas las
    pruebas del caso; si no se pasa, este se cierra al terminar la ultima.
    """
    activo = ejecutor or EjecutorPar()
    propio = ejecutor is None

    def falla(payload: bytes) -> bool:
        original, port = activo.observar(pair, project, payload)
        return _divergen(pair, payload, original, port, firma, cualquier)

    if propio:
        falla.cerrar = activo.pool.shutdown  # type: ignore[attr-defined]
    return falla


def _divergen(pair, payload, original, port, firma, cualquier) -> bool:
    try:
        divergencia = compare(_caso_vacio(pair, payload), original, port, pair.normalize, pair.errors)
    except CompareError:
        return False
    if divergencia is None:
        return False
    if cualquier or firma is None:
        return True
    return divergencia.signature == firma


class Buscador:
    """ddmin con memoria: el mismo candidato no se ejecuta dos veces.

    Los dos lados de la pareja se lanzan a la vez. Cada uno es un proceso
    distinto y `subprocess.run` suelta el GIL, asi que en la practica el coste
    por prueba es el de un arranque, no el de dos.
    """

    def __init__(self, falla, presupuesto: int = PRESUPUESTO) -> None:
        self.falla = falla
        self.presupuesto = presupuesto
        self.cache: dict = {}
        self.ejecuciones = 0
        self.agotado = False

    def prueba(self, candidato) -> bool:
        clave = candidato if isinstance(candidato, bytes) else tuple(candidato)
        if clave in self.cache:
            return self.cache[clave]
        if self.ejecuciones >= self.presupuesto:
            self.agotado = True
            raise _SinPresupuesto
        self.ejecuciones += 1
        valor = self.falla(candidato)
        self.cache[clave] = valor
        return valor

    # ------------------------------------------------------------------ ddmin

    def ddmin(self, datos):
        actual = datos
        vacio = datos[:0]

        def unir(partes):
            if isinstance(vacio, bytes):
                return vacio.join(partes)
            return [elemento for trozo in partes for elemento in trozo]

        n = 2
        while len(actual) >= 2:
            trozos = _trozos(actual, n)
            reducido = False

            # 1. un trozo solo ya reproduce la divergencia: quedarse con el
            for trozo in trozos:
                if len(trozo) and len(trozo) < len(actual) and self.prueba(trozo):
                    actual = trozo
                    n = 2
                    reducido = True
                    break

            # 2. el complemento de un trozo reproduce la divergencia: quitarlo
            if not reducido:
                for indice in range(len(trozos)):
                    resto = unir(trozos[:indice] + trozos[indice + 1:])
                    if len(resto) and len(resto) < len(actual) and self.prueba(resto):
                        actual = resto
                        n = max(n - 1, 2)
                        reducido = True
                        break

            # 3. ni una cosa ni la otra: subir la granularidad
            if not reducido:
                if n >= len(actual):
                    break
                n = min(n * 2, len(actual))
        return actual

    # --------------------------------------------------------------- ventanas

    def mejor_ventana(self, datos: bytes, tope: int = VENTANA) -> bytes | None:
        """La subcadena mas corta que sigue divergiendo, o None.

        ddmin es 1-minimo pero no minimo global: desde una entrada de 17 bytes
        puede no encontrar el `a#b` que reproduce el fallo, porque para llegar
        ahi hay que cambiar caracteres, no solo borrarlos. Esto es el atajo.
        """
        if len(datos) > LIMITE_VENTANAS:
            return None
        for tamano in range(1, min(len(datos), tope) + 1):
            for inicio in range(0, len(datos) - tamano + 1):
                trozo = datos[inicio:inicio + tamano]
                if self.prueba(trozo):
                    return trozo
        return None

    # --------------------------------------------------------------- completo

    def reducir(self, datos: bytes) -> bytes:
        actual = datos
        try:
            # Fase 1: la ventana mas corta que ya falla. Es el atajo que evita
            # quedarse en un minimo local cuando la entrada es corta.
            atajo = self.mejor_ventana(actual)
            if atajo is not None and len(atajo) < len(actual):
                actual = atajo

            # Fase 2: lineas, para entradas de varias lineas.
            if b"\n" in actual:
                lineas = actual.split(b"\n")
                if len(lineas) > 1:
                    reducidas = self.ddmin(lineas)
                    actual = b"\n".join(reducidas)

            # Fase 3: bytes.
            if len(actual) > 1:
                actual = self.ddmin(actual)

            # Fase 4: extremos que no cambian nada.
            for recorte in (actual.rstrip(), actual.lstrip()):
                if recorte and len(recorte) < len(actual) and self.prueba(recorte):
                    actual = recorte
                    break
        except _SinPresupuesto:
            return actual
        return actual


def _trozos(datos, n: int) -> list:
    """Parte en como mucho n trozos contiguos lo mas iguales posible."""
    if n <= 0 or not len(datos):
        return [datos]
    tamano = max(1, -(-len(datos) // n))
    return [datos[i:i + tamano] for i in range(0, len(datos), tamano)]


def reducir(
    pair: Pair,
    project: Project,
    caso: Case,
    divergencia: Divergence,
    presupuesto: int = PRESUPUESTO,
    cualquier: bool = False,
) -> ShrinkResult:
    firma = None if cualquier else divergencia.signature
    with EjecutorPar() as ejecutor:
        falla = predicado(pair, project, firma, cualquier, ejecutor)
        buscador = Buscador(falla, presupuesto)
        inicio = time.perf_counter()
        minimo = buscador.reducir(caso.input)

    despues = _divergencia_de(pair, project, minimo)
    return ShrinkResult(
        pair_id=pair.id,
        case_id=caso.id,
        antes=caso.input,
        despues=minimo,
        divergencia_antes=divergencia,
        divergencia_despues=despues,
        ejecuciones=buscador.ejecuciones,
        segundos=time.perf_counter() - inicio,
        completo=not buscador.agotado,
    )


def _divergencia_de(pair: Pair, project: Project, payload: bytes) -> Divergence | None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        original = pool.submit(
            run, pair.original.resolved(), payload, pair.timeout_ms, pair.original.working_dir(project.root)
        )
        port = pool.submit(
            run, pair.port.resolved(), payload, pair.timeout_ms, pair.port.working_dir(project.root)
        )
    try:
        return compare(_caso_vacio(pair, payload), original.result(), port.result(), pair.normalize, pair.errors)
    except CompareError:
        return None


def _legible(datos: bytes, limite: int = 90) -> str:
    if not datos:
        return "(vacio)"
    texto = datos.decode("utf-8", "replace")
    texto = texto.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    if len(texto) > limite:
        texto = texto[:limite] + "..."
    return repr(texto)


def console(resultado: ShrinkResult, pair: Pair) -> str:
    lineas = [
        f"{pair.id} / {resultado.case_id}",
        f"  antes      {len(resultado.antes):>3} B  {_legible(resultado.antes)}",
        f"  despues    {len(resultado.despues):>3} B  {_legible(resultado.despues)}",
    ]
    if resultado.divergencia_despues:
        lineas.append(f"  sigue      {resultado.divergencia_despues.one_line()}")
    else:
        lineas.append("  sigue      ya no reproduce (revisar el presupuesto)")
    if resultado.ahorro > 0:
        porcentaje = resultado.ahorro * 100.0 / max(len(resultado.antes), 1)
        lineas.append(f"  recorte    {resultado.ahorro} B ({porcentaje:.0f}%)")
    else:
        lineas.append("  recorte    ninguno: la entrada ya es minima")
    final = "" if resultado.completo else "  (presupuesto agotado: esto es lo mas pequeno que se encontro)"
    lineas.append(f"  pruebas    {resultado.ejecuciones} en {resultado.segundos:.2f}s{final}")
    return "\n".join(lineas)


def markdown(resultados: list[ShrinkResult]) -> str:
    filas = ["| pareja | caso | antes | despues | recorte | pruebas |", "|---|---|---:|---:|---:|---:|"]
    for r in resultados:
        filas.append(
            f"| `{r.pair_id}` | `{r.case_id}` | {len(r.antes)} | {len(r.despues)} | {r.ahorro} | {r.ejecuciones} |"
        )
    return "\n".join(filas)


def as_json(resultados: list[ShrinkResult]) -> list[dict]:
    return [
        {
            "pair": r.pair_id,
            "case": r.case_id,
            "input_before_b64": base64.b64encode(r.antes).decode("ascii"),
            "input_after_b64": base64.b64encode(r.despues).decode("ascii"),
            "bytes_before": len(r.antes),
            "bytes_after": len(r.despues),
            "runs": r.ejecuciones,
            "seconds": round(r.segundos, 3),
            "complete": r.completo,
            "signature": r.divergencia_despues.signature if r.divergencia_despues else None,
        }
        for r in resultados
    ]


def escribir_caso(project: Project, pair: Pair, resultado: ShrinkResult) -> str:
    """Anade la entrada minima al corpus, grabada como la deja el original."""
    ruta = project.root / pair.corpus
    casos = corpus_mod.read(ruta)
    existentes = {caso.id for caso in casos}

    base = f"{resultado.case_id}-min"
    nuevo_id = base
    sufijo = 2
    while nuevo_id in existentes:
        nuevo_id = f"{base}{sufijo}"
        sufijo += 1

    observacion = run(
        pair.original.resolved(),
        resultado.despues,
        pair.timeout_ms,
        pair.original.working_dir(project.root),
    )
    if observacion.status not in (OK, ERR):
        raise ShrinkError(
            f"el original no deja una salida grabable para esta entrada ({observacion.status})"
        )

    casos.append(Case(id=nuevo_id, input=resultado.despues, status=observacion.status, output=observacion.output))
    corpus_mod.write(ruta, casos)
    return nuevo_id


def shrink_casos(
    project: Project,
    pairs: list[str] | None,
    casos: list[str] | None,
    presupuesto: int = PRESUPUESTO,
    cualquier: bool = False,
    todos: bool = False,
) -> list[ShrinkResult]:
    """Reduce los casos pedidos. Sin `casos`, hace falta `todos`."""
    from . import check as check_mod

    seleccion = [p for p in project.pairs if not pairs or p.id in set(pairs)]
    if not seleccion:
        raise ValueError(f"ninguna pareja coincide con {pairs}")

    resultado = check_mod.check(Project(root=project.root, pairs=tuple(seleccion), baseline=project.baseline))
    por_id = {p.pair_id: p for p in resultado.pairs}

    salida: list[ShrinkResult] = []
    for pair in seleccion:
        encontrado = por_id.get(pair.id)
        if encontrado is None:
            continue
        divergencias = encontrado.divergences
        if casos:
            pedidos = set(casos)
            divergencias = [d for d in divergencias if d.case_id in pedidos]
            faltan = pedidos - {d.case_id for d in divergencias}
            if faltan:
                raise ValueError(
                    f"{pair.id}: estos casos no divergen (o no existen): {', '.join(sorted(faltan))}"
                )
        elif not todos:
            raise ValueError("indica un caso con --case o reduce todos con --all")

        if not divergencias:
            continue

        corpus_path = project.root / pair.corpus
        indice = {caso.id: caso for caso in corpus_mod.read(corpus_path)}
        for divergencia in divergencias:
            caso = indice.get(divergencia.case_id)
            if caso is None:
                continue
            salida.append(reducir(pair, project, caso, divergencia, presupuesto, cualquier))

    return salida
