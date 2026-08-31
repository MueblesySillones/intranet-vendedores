# Cómo trabajar con este código desde tu computadora

Este repositorio es **tu herramienta**: el código del **panel**, el **cerebro** y
las **pruebas (QA)**. (La intranet en sí vive en el GitHub de Muebles y Sillones,
aparte — esto es lo que NO estaba en ningún git y ahora sí.)

## 1. Traerlo a tu compu
```
git clone <URL-de-tu-repo-privado>
cd herramientas
```

## 2. Instalar una sola vez
- **Python 3.12** → después: `pip install pyinstaller`
- **Node.js** (para las pruebas y para el cerebro)
- **Inno Setup 6** (para compilar el instalador del panel)
- **Git**

## 3. El ciclo de trabajo
1. **Editar** `panel/panel_server.py` o `panel/web2/` (el frontend).
2. **Compilar** el programa: `cd panel && python -m PyInstaller PanelMyS.spec --noconfirm`
3. **Publicar la actualización**: `python subir_update.py` y `git push` en el repo de
   la intranet (esto hace que a los paneles les aparezca "Actualizar").
4. **El cerebro** (si tocás `cerebro/src/worker.js`): `wrangler deploy`.

El instructivo completo, con el mapa de cómo se conecta todo, está en
`documentacion/LEEME-PRIMERO.md`.

## 4. La clave del equipo (importante)
Para que el instalador deje la clave puesta, necesita el archivo
`panel/clave-equipo.iss` — que **NO está en el repo a propósito** (es un secreto).
- En la PC central ese archivo ya existe.
- Si clonás en otra máquina y querés compilar el instalador **con** la clave:
  copiá `panel/clave-equipo.iss.ejemplo` como `panel/clave-equipo.iss` y pegá la
  clave real adentro.
- Sin ese archivo, el instalador compila igual, pero sin la clave baked.

⚠️ **Nunca subas `clave-equipo.iss` a ningún lado.** Ya está en el `.gitignore`.

## 5. Respaldos
Hoy el código del panel tiene dos respaldos: **este repo** y el **ZIP**
(`MyS-plataforma-codigo.zip`). Mantené los dos.
