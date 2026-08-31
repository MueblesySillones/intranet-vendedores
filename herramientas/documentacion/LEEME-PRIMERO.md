# Plataforma Muebles y Sillones — código, arquitectura y cómo se construyó

**Respaldo del 29 de agosto de 2026.** Este archivo explica qué es todo esto, cómo
está pensado, cómo está construido y cómo se edita y se vuelve a publicar. Leelo
antes que nada.

> ⚠️ **DOS AVISOS IMPORTANTES**
>
> 1. **Este ZIP es el ÚNICO respaldo del panel afuera de la computadora donde se
>    construyó.** La carpeta `herramientas/` (el panel, el cerebro y las pruebas)
>    **NO está en GitHub** (está excluida a propósito). Si se pierde esta copia,
>    se pierde el código del panel. Guardalo en un lugar seguro (y hacé una copia
>    más).
> 2. **Contiene una clave.** El instalador `herramientas/panel/PanelMyS.iss` tiene
>    embebida la clave de publicación del equipo. **No subas este ZIP a ningún
>    lugar público** (ni Drive compartido, ni GitHub, ni WhatsApp de grupos).

---

## 1. Qué es

Tres cosas que juntas forman un producto:

- **La intranet** — el sitio que ven los vendedores (novedades, materiales, promos,
  reportes). Es una web pública.
- **El panel** — un programa de escritorio para editar la intranet **sin tocar
  código**. Lo usa el equipo de marketing.
- **El cerebro + el sistema de actualización** — lo que publica los cambios al sitio
  y mantiene los paneles al día solos.

En términos de mercado: una **intranet de comunicación interna + sales enablement**,
con un **CMS sin código** propio, pensada para venderse como **SaaS vertical**.

---

## 2. El mapa: cómo se conectan las piezas

```
   [ Panel .exe ]  (cada PC del equipo)
        │  el usuario edita y aprieta "Publicar"
        ▼
   [ Cerebro ]  Cloudflare Worker  (mys-cerebro.mueblesysillones.workers.dev)
        │  valida la clave, arma un commit
        ▼
   [ GitHub ]  MueblesySillones/intranet-vendedores   (rama main)
        │  cada push dispara un deploy
        ▼
   [ Vercel ]  intranet-vendedores.vercel.app  →  lo ven los vendedores

   ── Actualización del PANEL ─────────────────────────────
   La central publica el programa nuevo en la web:
      panel/version.json  +  panel/PanelMyS-vNN.zip   (en el mismo GitHub → Vercel)
   Cada panel pregunta por internet si hay versión nueva y se actualiza solo.
   Respaldo: si internet falla, lo pide a la PC central por Tailscale (puerto 8125).
```

**Central vs. Colaborador:** hay una PC "central" (la del administrador) y las demás
son "colaboradores". Todos publican directo al cerebro con su clave. La diferencia
es que la central además puede servir actualizaciones por Tailscale como respaldo.

---

## 3. Cómo está construido (el stack)

| Pieza | Tecnología | Dónde vive |
|---|---|---|
| **Intranet** | HTML + CSS + JavaScript **plano** (sin framework, sin build) | `intranet/` |
| **Panel (backend)** | **Python** (servidor `http.server`), empaquetado en `.exe` con **PyInstaller** | `herramientas/panel/panel_server.py` |
| **Panel (frontend)** | HTML/CSS/JS plano, sin build | `herramientas/panel/web2/` |
| **Sección Datos** | Python: integración Google Sheets, generación de Word/PDF, deck | `herramientas/panel/datos/` |
| **Cerebro** | **Cloudflare Worker** (JavaScript) + Durable Object (cola única) | `herramientas/cerebro/src/worker.js` |
| **Actualización auto.** | `subir_update.py` (publica el paquete) + `updater/aplicar.bat` (hace el cambio) | `herramientas/panel/` |
| **Instaladores** | **Inno Setup 6** (`.iss`) | `herramientas/panel/PanelMyS.iss` |
| **Pruebas (QA)** | **Playwright** + **axe-core** (accesibilidad) | `herramientas/qa/` |

Detalle clave del panel: **no corre desde el código, corre desde el `.exe`
compilado**. Editar los `.py` o `web2/` no cambia nada hasta recompilar.

---

## 4. Cómo editar y volver a publicar cada parte

**La intranet (lo que ven los vendedores):**
1. Editar los archivos en `intranet/`.
2. `git add . && git commit && git push` → Vercel redespliega solo en ~30 s.
   (O directamente desde el panel, apretando Publicar.)

**El panel (el programa):**
1. Editar `panel_server.py` o los archivos de `web2/`.
2. Recompilar:  `python -m PyInstaller PanelMyS.spec --noconfirm`
3. Publicar la actualización:  `python subir_update.py`
   (arma `panel/version.json` + `panel/PanelMyS-vNN.zip`)
4. `git add panel && git commit && git push` → la web sirve la versión nueva.
5. Instalar en la central: cerrar el `.exe`, copiar `dist/PanelMyS/_internal` y
   `dist/PanelMyS/PanelMyS.exe` sobre `%LOCALAPPDATA%\PanelMyS` (NO pisar
   `panel_config.json` ni `proyecto.txt`).
6. Subir el número de versión en `panel_server.py` (`VERSION = NN`) para que a los
   demás les aparezca el botón "Actualizar".

**El instalador (para repartir a PCs nuevas):**
- Con Inno Setup 6:  `ISCC.exe PanelMyS.iss`  → sale `instalador/Instalar Panel MyS.exe`.
- Ya no pregunta nada: deja la PC como colaborador con la clave puesta.

**El cerebro (Cloudflare):**
- Editar `herramientas/cerebro/src/worker.js`.
- `wrangler deploy` (requiere iniciar sesión: `wrangler login`).
- Los secretos NO van en el código: se cargan con `wrangler secret`.

---

## 5. ⚠️ Secretos y cuentas (leer antes de tocar nada)

**Cuentas (hoy son de Muebles y Sillones):**
- **GitHub:** `MueblesySillones/intranet-vendedores` — el código de la intranet y los
  paquetes de actualización.
- **Vercel:** conectado a ese GitHub — hostea el sitio.
- **Cloudflare:** hostea el cerebro (Worker).
- **Dominio / Tailscale:** para la red entre las PCs.

**Claves (NO están todas acá, y está bien que así sea):**
- La **clave de publicación del equipo** está embebida en `PanelMyS.iss` (por eso
  este ZIP es privado).
- `GITHUB_TOKEN` y `PUBLISH_TOKENS` viven **en Cloudflare** (secretos del Worker),
  no en el código.
- La **authkey de Tailscale** y el **token de GitHub** no están en estos archivos.

Si alguna vez cambian de dueño o de manos, **rotá todas las claves** (generar nuevas
y reemplazar las viejas).

---

## 6. Qué NO está en este ZIP (y cómo conseguirlo)

Se dejó afuera lo pesado y **regenerable**, para que el ZIP sea liviano:

- **Las imágenes/videos de la intranet** (`intranet/assets/`, ~80 MB): están en el
  GitHub de MyS y en el sitio live. Para tener todo: `git clone` del repo.
- **El `.exe` compilado y los instaladores** (`dist/`, `build/`, `paquete/`,
  `instalador/`): se regeneran con los comandos de la sección 4.
- **Las capturas de la suite QA** (`baseline/`, `salida/`): se regeneran corriendo
  `python correr_todo.py` dentro de `herramientas/qa/`.

Nada de eso es código: todo se vuelve a generar. El código está completo acá.

---

## 7. Para editar desde tu computadora (ambiente de desarrollo)

Vas a necesitar instalar:
- **Python 3.12** + `pip install pyinstaller` (y las librerías que use `datos/`).
- **Node.js** (para las pruebas Playwright y para `wrangler` del cerebro).
- **Inno Setup 6** (para compilar el instalador).
- **Git** (para publicar la intranet y las actualizaciones).

El "código fuente de la verdad" del panel es esta carpeta `herramientas/`. El de la
intranet, además, vive en el GitHub de MyS. (Lo de cómo acceder a todo esto de forma
prolija desde tu propia máquina lo terminamos de armar aparte.)

---

## 8. Estado al 29-ago-2026

- Panel en **versión 25**, instalado en la central y publicado por internet.
- Última mejora: el selector de la Cartelera ahora deja elegir **por bloque** y es
  más compacto.
- La documentación completa de la auditoría y el rediseño está en la carpeta
  `documentacion/` de este ZIP.
