# -*- mode: python ; coding: utf-8 -*-
# Empaqueta el Panel de administracion de Muebles y Sillones como app de Windows.
# Build:  python -m PyInstaller PanelMyS.spec --noconfirm
# Salida: dist/PanelMyS/PanelMyS.exe  (modo onedir: mas rapido y menos falsos positivos de antivirus)

block_cipher = None

a = Analysis(
    ['panel_server.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('web2', 'web2'),                   # el frontend actual: muro, modulos, DATOS, metricas
        ('web', 'web'),                     # el anterior, de red por si web2 no viajara
        ('originales.json', '.'),           # HTML original de los modulos del sistema
        ('updater', 'updater'),             # aplicar.bat (swap del auto-update) + launcher
    ],
    # Se importan en tiempo de ejecucion (adentro de funciones, o desde un hilo),
    # asi que hay que nombrarlos: PyInstaller arma la lista leyendo el codigo y
    # un import que vive adentro de un `if` de una funcion se le puede escapar.
    # Si falta uno, el panel abre igual —todos estan atras de un try— pero la
    # seccion Datos aparece vacia sin decir por que.
    hiddenimports=[
        'receptor_server',
        'datos_api',
        'datos', 'datos.analizador', 'datos.fuentes', 'datos.lecturas',
        'datos.reporte', 'datos.revisor',
        'datos.google_sheets', 'datos.google_cuenta', 'datos.google_link',
        'datos.encabezado',
        'datos.medidas',
        'datos.derivaciones', 'datos.deck',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pydoc', 'test', 'numpy', 'setuptools', 'pip'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PanelMyS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                              # sin UPX: menos falsos positivos de antivirus
    console=False,                          # SIN ventana negra: solo abre el panel; se cierra con el boton "Cerrar"
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='panel.ico',
    version='version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='PanelMyS',
)
