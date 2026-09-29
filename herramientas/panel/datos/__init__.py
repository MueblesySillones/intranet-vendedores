# -*- coding: utf-8 -*-
"""Todo lo que el panel necesita para entender una planilla.

  analizador   — que es cada columna (fecha, lista, numero, CONTACTO...)
  revisor      — que esta mal cargado, con la fila donde esta
  lecturas     — las conclusiones, cada una con su cuenta a la vista
  fuentes      — de donde salen las filas: CSV o Excel, con cache
  google_sheets— la planilla privada de Drive, por OAuth
  reporte      — el mismo material, en Word y en HTML para imprimir

Todo con biblioteca estandar: el panel se distribuye como .exe y cada
dependencia lo engorda. `openpyxl` es la unica excepcion, y es opcional.

⚠️ Este paquete ve datos de clientes. Vive adentro de `herramientas/`, que
   esta en .gitignore y en .vercelignore, asi que no puede llegar al sitio
   publico. Lo que se publica lo decide una persona, numero por numero.
"""
