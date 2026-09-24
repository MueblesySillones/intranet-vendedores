import io, os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
ps = io.open(os.path.join(AQUI, "actualizar_ps.txt"), encoding="utf-8").read()
cab = ("@echo off\r\n"
       "title Actualizar el Panel MyS\r\n"
       "REM Actualiza el Panel MyS a la ultima version publicada, sin depender del panel viejo.\r\n"
       "REM Baja panel/version.json + el zip del sitio, verifica el sha256, copia encima de la\r\n"
       "REM instalacion (sin tocar panel_config.json, proyecto.txt, identity.json ni aprobaciones),\r\n"
       "REM lo vuelve a abrir y confirma la version. 23-sep-2026.\r\n"
       "powershell -NoProfile -ExecutionPolicy Bypass -Command \"$l = Get-Content -LiteralPath '%~f0'; "
       "$i = [array]::IndexOf($l, '#PS#'); iex ($l[($i+1)..($l.Length-1)] -join [char]10)\"\r\n"
       "echo.\r\n"
       "pause\r\n"
       "exit /b\r\n"
       "#PS#\r\n")
cuerpo = ps.replace("\r\n", "\n").replace("\n", "\r\n")
todo = cab + cuerpo
assert all(ord(c) < 128 for c in todo), "solo ASCII: el bat corre en cmd"
dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ["USERPROFILE"], "Desktop", "ACTUALIZAR PANEL MyS.bat")
open(dest, "wb").write(todo.encode("ascii"))
print(dest, os.path.getsize(dest), "bytes; lineas CRLF:", todo.count("\r\n"))
