# -*- coding: utf-8 -*-
"""Prueba quien firma una publicacion: los sectores y donde se guardan.

Por que existe: el autor era un rotulo fijo en el HTML del panel que decia
siempre "Marketing" y no lo tocaba nadie, asi que un aviso de Administracion
salia firmado por Marketing igual.

Y hay una trampa con DONDE se guarda la lista. El primer intento la puso en
`content.sectores` de la cartelera; no funciona: validar_content() de
panel_server.py sanea la cartelera y devuelve un dict CERRADO
(tipo, docs, papelera), asi que el campo desaparecia solo en el primer
guardado, sin error y sin aviso. Por eso vive en los ajustes globales, que si
tienen su validador y viajan en cada persistModulos.

Lo que se verifica:
  1. validar_ajustes() conserva los sectores, con Marketing primero
  2. el saneado de la cartelera efectivamente se come cualquier campo de mas
     (o sea: la trampa sigue ahi, y por eso la lista no puede volver)
  3. el panel lee la lista de AJUSTES y no del contenido del modulo

    python test_sectores_autor.py
"""
import importlib.util
import io
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.abspath(os.path.join(AQUI, "..", "panel"))
SERVER = os.path.join(PANEL, "panel_server.py")
MURO = os.path.abspath(os.path.join(PANEL, "web3", "muro.js"))


def cargar():
    # panel_server importa sus vecinos (fusion, clave_equipo): sin esto,
    # cargarlo desde otra carpeta falla con ModuleNotFoundError
    if PANEL not in sys.path:
        sys.path.insert(0, PANEL)
    spec = importlib.util.spec_from_file_location("ps_test", SERVER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    if not os.path.isfile(SERVER):
        print("no encuentro panel_server.py"); return 1
    ps = cargar()
    va = ps.validar_ajustes
    PRIN = ps.SECTOR_PRINCIPAL

    casos = [
        ("el principal va primero aunque venga ultimo",
         va({"sectores": ["Tapicería", PRIN]})["sectores"], [PRIN, "Tapicería"]),
        ("no repite",
         va({"sectores": ["Ventas", "Ventas", PRIN]})["sectores"], [PRIN, "Ventas"]),
        ("limpia los espacios de mas",
         va({"sectores": ["  Posventa  "]})["sectores"], [PRIN, "Posventa"]),
        ("descarta los vacios",
         va({"sectores": ["", "   ", None]})["sectores"], [PRIN]),
        ("sin el campo: repone los de fabrica",
         va({})["sectores"], list(ps.SECTORES_POR_DEFECTO)),
        ("lista vacia SI se respeta (dejaron solo el principal)",
         va({"sectores": []})["sectores"], [PRIN]),
        ("un nombre larguisimo no entra",
         va({"sectores": ["x" * 41]})["sectores"], [PRIN]),
        ("no se lleva puesto el otro ajuste",
         va({"novedad_horas": 48, "sectores": ["Ventas"]})["novedad_horas"], 48),
    ]

    ok = 0
    for nombre, real, esperado in casos:
        bien = real == esperado
        ok += bien
        print("%s | %-48s %s%s" % ("PASS" if bien else "FALLA", nombre, real,
                                   "" if bien else "  (esperaba %s)" % esperado))

    # --- la trampa: la cartelera se come los campos de mas ---
    saneado = ps.validar_content({"tipo": "cartelera", "docs": [], "sectores": ["Ventas"]})
    bien = isinstance(saneado, dict) and "sectores" not in saneado
    ok += bien
    print("%s | %-48s %s" % ("PASS" if bien else "FALLA",
          "la cartelera descarta campos de mas (por eso no va ahi)",
          sorted(saneado.keys()) if isinstance(saneado, dict) else saneado))

    # --- y el panel lee de los ajustes ---
    fuente = io.open(MURO, encoding="utf-8").read()
    # se busca el ACCESO (".content.sectores"), no la palabra suelta: el
    # comentario de muro.js nombra content.sectores justamente para explicar
    # por que la lista no vive ahi
    bien = "AJUSTES.sectores" in fuente and ".content.sectores" not in fuente
    ok += bien
    print("%s | %-48s" % ("PASS" if bien else "FALLA",
          "muro.js lee AJUSTES.sectores, no content.sectores"))

    total = len(casos) + 2
    print("\n%d/%d PASS" % (ok, total))
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
