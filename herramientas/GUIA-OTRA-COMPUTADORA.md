# Seguir desde otra computadora

Qué hacer si la computadora central se pierde, se rompe o ya no está disponible.
Con esto se puede **publicar contenido** y **publicar versiones nuevas del panel**
desde cualquier PC con Windows.

Lo mismo, con la clave ya puesta en el paso 4, está en el archivo que genera el
panel: *Configuración → Para desarrolladores* (sección «Seguir desde otra
computadora»).

---

## 1. Lo que hay que tener antes

- **El archivo «Para desarrolladores»** que genera el panel. Es lo único que trae
  la **clave de publicación**, que no está en GitHub a propósito (este repo es
  público). Generalo HOY y guardalo en dos lugares privados.
  Si se perdió, hay que hacer una clave nueva: cambiar el secreto del Worker en
  Cloudflare y recompilar el panel.
- **Una cuenta de GitHub invitada a la organización `MueblesySillones`** con
  permiso de escritura. La invita el dueño en github.com/MueblesySillones →
  People → Invite.
- Una computadora con Windows 10 u 11 y internet.

## 2. Instalar los programas (una sola vez)

1. **Git**: git-scm.com, con todas las opciones como vienen.
2. **Python 3.12**: python.org. En la primera pantalla del instalador marcá
   **«Add python.exe to PATH»** antes de apretar Install.
3. Cerrá y volvé a abrir el cmd, y escribí:
   ```
   python --version
   git --version
   pip install pyinstaller pillow certifi openpyxl
   ```
4. Opcional, para armar los instaladores de las sucursales: **Inno Setup 6**
   (jrsoftware.org).
5. Opcional, sólo para tocar el cerebro: **Node.js** (nodejs.org).

## 3. Bajar el proyecto

```
cd %USERPROFILE%\Documents
git clone https://github.com/MueblesySillones/intranet-vendedores
cd intranet-vendedores
git config user.name "Tu nombre"
git config user.email "tu-correo-de-github@ejemplo.com"
```

La primera vez que subas algo, Git abre una ventana para entrar con tu cuenta de
GitHub.

## 4. Poner la clave

En `herramientas\panel\` creá un archivo `clave-equipo.iss` (que no quede
`clave-equipo.iss.txt`: en el Explorador activá *Vista → Extensiones de nombre de
archivo*) con esta única línea:

```
#define PubKey "LA_CLAVE_DEL_ARCHIVO_PARA_DESARROLLADORES"
```

Está en el `.gitignore`. **Nunca lo subas.**

## 5. Publicar contenido

1. Instalá el panel con `Instalar Panel MyS.exe` y elegí **Central**. Si no tenés
   el instalador, armalo con el paso 7.
2. Cuando pregunte por la carpeta del proyecto, elegí la del paso 3.
3. Si pide la clave de publicación, pegá la del archivo.
4. Se publica como siempre, con el botón Publicar.

## 6. Publicar una versión nueva del panel

Cuando cambió el código del panel (por ejemplo, un arreglo que hizo Claude).
Si Claude dejó los cambios en una rama, reemplazá `NOMBRE-DE-LA-RAMA`; si ya
están en `main`, salteá esa línea.

```
cd %USERPROFILE%\Documents\intranet-vendedores
git checkout main
git pull
git merge --ff-only origin/NOMBRE-DE-LA-RAMA
cd herramientas\panel
python publicar_web3.py
```

- `publicar_web3.py` sube la versión, compila, prueba el `.exe` y publica. Si
  frena, **no publicó nada**: leé lo que dice.
- Arriba de todo en `publicar_web3.py` tienen que estar los textos de **esta**
  versión (`NUEVA_PUBLICA`, `NUEVO_LABEL`, `NUEVAS_NOTAS`, `NUEVOS_ARREGLOS`,
  `NUEVAS_MEJORAS`). Si son los de la anterior, frena.
- Hace push a `main`: correlo parado en `main`.
- Al terminar, las sucursales ven el cartel «Debés actualizar».

## 7. Armar los instaladores

`publicar_web3.py` los arma solo al final si Inno Setup 6 está instalado. Aparte:

```
cd %USERPROFILE%\Documents\intranet-vendedores\herramientas\panel
python armar_instalador.py
```

Quedan en `Escritorio\Proyecto Intranet\Panel MyS`. El de sucursal usa una clave
de Tailscale (login.tailscale.com → Settings → Keys).

## 8. El cerebro (casi nunca)

Sólo si cambió `herramientas\cerebro\src\worker.js`. Hace falta Node.js y la
cuenta de Cloudflare del negocio:

```
cd %USERPROFILE%\Documents\intranet-vendedores\herramientas\cerebro
npx wrangler login
npx wrangler deploy
```

## 9. Si algo sale mal

| Mensaje | Qué hacer |
|---|---|
| `not a git repository` | El cmd no está en la carpeta del proyecto: hacé el `cd` del paso 6. |
| `There is no tracking information` | `git branch --set-upstream-to=origin/main main` y otra vez `git pull`. |
| `Your local changes ... would be overwritten` | Hay cambios sin guardar en esa PC: `git stash push -u` (no se borran) y seguí. |
| `falta clave-equipo.iss` / `el cerebro rechaza la clave` | Revisá el paso 4. |
| `falta la carpeta datos/` | El proyecto está viejo: `git pull`. |
| `NO SE PUDO ACTUALIZAR ... (codigo 11)` en una PC con v99 o anterior | Bajá y abrí https://intranet-vendedores.vercel.app/panel/ACTUALIZAR-PANEL-MyS.bat (doble clic). Desde la v100 no pasa más. |
| `los reportes no cargan` | Falta una librería: `pip install <la que diga el mensaje>`. |

Para cualquier otra cosa: abrí Claude, conectá el repositorio y pegale el error.

---

### Nota: la carpeta `herramientas/panel/datos/`

Es el código de los reportes (sección Datos). Hasta el 29-sep-2026 **no estaba en
GitHub**: vivía sólo en la PC central. Desde la v100, `publicar_web3.py` la sube
con cada versión y frena si falta o si no carga. Si una PC nueva clona el repo
antes de esa primera publicación, no la va a tener.
