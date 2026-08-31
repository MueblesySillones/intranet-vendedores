# -*- coding: utf-8 -*-
"""Arma el sandbox sobre el que corre TODA la suite.

Por qué existe: los tests crean, editan y borran publicaciones de verdad
(escriben modulos.js) y el panel guarda estado (identity, cachés). Nada de
eso puede tocar ni la intranet real ni el estado real de la máquina. El
sandbox es una copia descartable:

    QA_SANDBOX/
      proyecto/
        intranet/      <- copia de QA_PROYECTO/intranet (o del snapshot)
        herramientas/  <- carpeta vacía: panel_server exige que exista
                          para reconocer la raíz como "proyecto"
      estado/          <- copia de fixtures/estado-base

El estado sale de fixtures/estado-base (copiado UNA sola vez desde
%LOCALAPPDATA%/PanelMyS_state) y no de AppData directo: así la suite corre
igual en cualquier máquina y ninguna corrida depende de —ni ensucia— la
configuración real del panel instalado.
"""
import os
import shutil
import sys

import arnes


def _borrar_sandbox_viejo():
    """Borra el sandbox anterior. El chequeo de la ruta es paranoia sana:
    un QA_SANDBOX mal puesto (p.ej. la raíz del proyecto) + rmtree sería
    un desastre, así que solo se borra si la ruta se llama 'sandbox'."""
    if not os.path.isdir(arnes.SANDBOX):
        return
    if "sandbox" not in os.path.basename(arnes.SANDBOX).lower():
        raise SystemExit("QA_SANDBOX=%r no parece un sandbox (la carpeta no se "
                         "llama 'sandbox'); no lo borro por las dudas." % arnes.SANDBOX)
    shutil.rmtree(arnes.SANDBOX)


def crear():
    estado_base = os.path.join(arnes.FIXTURES, "estado-base")
    if not os.path.isdir(estado_base):
        raise SystemExit(
            "Falta el fixture de estado: %s\n"
            "Se copia UNA sola vez desde el estado real:\n"
            '  robocopy "%%LOCALAPPDATA%%\\PanelMyS_state" "%s" /E\n'
            "y de ahí en más la suite usa siempre esa copia." % (estado_base, estado_base))

    origen_intranet = os.path.join(arnes.PROYECTO, "intranet")
    if not os.path.isfile(os.path.join(origen_intranet, "modulos.js")):
        raise SystemExit("QA_PROYECTO=%r no tiene intranet/modulos.js; "
                         "¿apunta a la raíz correcta?" % arnes.PROYECTO)

    print("sandbox: %s" % arnes.SANDBOX)
    print("  intranet desde: %s" % origen_intranet)
    print("  estado desde:   %s" % estado_base)
    _borrar_sandbox_viejo()

    destino = os.path.join(arnes.SANDBOX, "proyecto")
    # copia de la intranet completa (con assets: los tests miran imágenes reales)
    shutil.copytree(origen_intranet, os.path.join(destino, "intranet"))
    # panel_server.encontrar_proyecto() pide intranet/ Y herramientas/: la
    # segunda puede estar vacía, solo tiene que existir
    os.makedirs(os.path.join(destino, "herramientas"), exist_ok=True)
    shutil.copytree(estado_base, os.path.join(arnes.SANDBOX, "estado"))

    n = sum(len(fs) for _, _, fs in os.walk(arnes.SANDBOX))
    print("  listo: %d archivos copiados" % n)
    return arnes.SANDBOX


if __name__ == "__main__":
    crear()
    sys.exit(0)
