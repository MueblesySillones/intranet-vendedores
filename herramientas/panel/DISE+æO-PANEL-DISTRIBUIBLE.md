# DOCUMENTO DE DISEÑO TÉCNICO — Panel Centralizado "Muebles y Sillones"

Sistema: panel .exe gratis, centralizado, autoactualizable, controlado por MCP.

---

## 1) RESUMEN PARA EL DUEÑO (no técnico)

**Qué vamos a construir.** Hoy el panel corre solo en tu PC y vos publicás a la intranet. Lo vamos a convertir en un programa instalable (`.exe`) que abren 3 a 6 personas del equipo en sus propias computadoras Windows, sin instalar nada raro. Cada uno edita las placas/productos desde una ventana simple, aprieta "Publicar", y la intranet de los vendedores se actualiza sola.

**Por qué es gratis (cero costo mensual).**
- La "llave" de GitHub (la credencial que publica) ya no se reparte en las 6 PCs: vive en **un único servicio en la nube de Cloudflare** que tiene un plan gratuito para uso comercial. Las computadoras del equipo nunca tocan esa llave.
- Las actualizaciones del programa se sirven desde **GitHub gratis** (mismo modelo que ya usás).
- La intranet sigue en Vercel/GitHub como hoy.
- No hay servidor pago, no hay suscripción.

**Qué tenés que crear vos (todo gratis, una sola vez).**
1. Una **cuenta de Cloudflare** (gratis) → ahí vive el "cerebro" que organiza las publicaciones.
2. Un **token fino de GitHub** (fine-grained PAT) limitado al repo de la intranet, permiso "Contents: leer y escribir", con vencimiento. Se carga UNA vez en Cloudflare.
3. Un **repositorio público de GitHub para las actualizaciones** del panel (no guarda nada secreto, solo los archivos del programa nuevo).
4. Conservar en TU PC unas **claves de firma** (las genero yo) que garantizan que solo vos podés publicar una versión nueva del panel. Se guardan con contraseña y backup (pendrive/gestor de contraseñas).

Con eso, vos (trabajando conmigo vía un MCP) publicás mejoras y el equipo las recibe con un popup "Hay una actualización → Actualizar".

**Lo único que NO es gratis y es opcional:** "firmar" el .exe para que Windows no muestre la advertencia azul de SmartScreen. No es necesario para uso interno; el equipo aprieta "Más información → Ejecutar de todos modos" una vez por versión. Se puede agregar después (~USD 10/mes validando la mueblería como empresa).

---

## 2) ARQUITECTURA

### Componentes

```
┌──────────────────────────────────────────────────────────────────────┐
│  PCs DEL EQUIPO (3–6, Windows, gente no técnica)                       │
│                                                                        │
│   Panel .exe "delgado" (PyInstaller --onedir)                          │
│   ├─ UI web local: http.server en 127.0.0.1:8124 (como hoy)           │
│   ├─ Pillow: normaliza imagen (RGB/RGBA, <=1568px) y la pasa a base64 │
│   ├─ tufup-client: autoupdate (root.json embebido)                     │
│   └─ token POR USUARIO guardado cifrado (Windows DPAPI/keyring)        │
└───────────────┬───────────────────────────────────┬───────────────────┘
                │ HTTPS  POST /publish               │ HTTPS (solo lectura)
                │ Authorization: <token-usuario>     │ GET metadata+targets
                │ JSON {archivos[], mensaje, sha}    │
                ▼                                     ▼
┌──────────────────────────────────────┐   ┌──────────────────────────────┐
│ CEREBRO — Cloudflare Worker          │   │ REPO GitHub de UPDATES (público)│
│ + Durable Object (cola/mutex único)  │   │ GitHub Pages sirve estáticos: │
│                                      │   │  metadata/*.json + targets/*  │
│ Secretos (cifrados, solo acá):       │   │  (.tar.gz + .patch firmados)  │
│  • GITHUB_TOKEN (fine-grained PAT)   │   └──────────────────────────────┘
│  • tabla tokens por usuario          │
│  • admin-token (para el MCP)         │
│  Audit log: quién publicó qué        │
└───────────────┬──────────────────────┘
                │ GitHub Git Data API (sin git instalado)
                │ ref → blobs(base64) → tree(base_tree) → commit → PATCH ref
                ▼
┌──────────────────────────────────────┐
│ REPO GitHub de la INTRANET           │──auto-deploy──► VERCEL (intranet
│ (HTML/JS estático que ya existe)     │                 que ven los vendedores)
└──────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  PC DEL DESARROLLADOR (vos + Claude)                                   │
│   MCP "mys-control" (stdio, local, NO expuesto a internet)            │
│   ├─ publicar_version() → PyInstaller + tufup add_bundle + firmar     │
│   │                        + push al repo de updates                   │
│   ├─ ver_estado() / historial() / quien_publico_ultimo()             │
│   ├─ listar/agregar/revocar_usuario()  (admin del cerebro)           │
│   └─ rotar_credencial_github()                                        │
│   Claves TUF (root/targets) OFFLINE acá, con passphrase + backup     │
└──────────────────────────────────────────────────────────────────────┘
```

### Flujo de una publicación, de punta a punta

1. El editor abre un ítem en el panel → el cliente pide al cerebro el **estado/contenido actual** (read-through) y el **SHA base**.
2. Edita texto y/o sube imagen. Pillow la normaliza (RGB/RGBA, <=1568px) y el **cliente la codifica a base64** (descarga de CPU del Worker).
3. El cliente hace `POST /publish` al Worker con `Authorization: <token-usuario>` y `{ archivos:[{path, encoding, content}], mensaje, sha_base }`.
4. El Worker valida el token. El **Durable Object único encola** la request → se procesan de a una (sin carreras).
5. El Worker comitea con la **Git Data API**: lee ref → crea blobs → crea tree (con `base_tree`) → crea commit (`parents=[ref]`) → `PATCH ref` con `force:false`. Si hubo conflicto (non-fast-forward 422), **re-lee y reintenta** con backoff.
6. Registra en el **audit log** {usuario, sha, timestamp} y responde OK (o "conflicto: recargá").
7. GitHub dispara el **auto-deploy de Vercel** → la intranet queda actualizada.

---

## 3) DECISIONES TÉCNICAS (con justificación)

### Cerebro: **Cloudflare Workers + Durable Object** ✅ gratis + comercial
- **Gratis y uso comercial permitido explícitamente** (a diferencia de Vercel Hobby, que prohíbe uso comercial → quedaría descartado para una mueblería).
- **Body hasta 100 MB** (imágenes de ~2 MB sobran), **sin cold start** (popup y publicación instantáneos), **secretos cifrados nativos** (`wrangler secret put`).
- El **Durable Object único** da el "servidor que organiza solo": procesa **una request a la vez** (`blockConcurrencyWhile`) → serialización nativa sin inventar locking. Es el requisito #3 resuelto de raíz.
- **Único riesgo:** el límite de **10 ms de CPU** del plan free. Mitigación de diseño: el **cliente** hace el base64 (Pillow ya corre ahí); el Worker solo orquesta llamadas de red (la espera de I/O a GitHub NO cuenta como CPU). Escape si molesta: Workers Paid (USD 5/mes, comercial) o Deno Deploy (50 ms CPU, gratis).
- **Por qué Git Data API y no Contents API:** la Git Data API hace **commit atómico multi-archivo** (texto + imágenes binarias en base64) y no tiene el tope práctico de 1 MB/archivo de la Contents API.

### Empaquetado .exe: **PyInstaller `--onedir --noupx`** + **Inno Setup** (sin admin) ✅ minimiza antivirus
- **`--onedir`, NO `--onefile`:** el patrón "un solo .exe que se autoextrae en temp" de onefile es justo lo que disparan los antivirus y SmartScreen. onedir arranca más rápido, levanta menos falsos positivos, y es **lo que tufup necesita** para reemplazar archivos limpio.
- **Sin UPX** (disparador clásico de heurísticas) y **PyInstaller siempre actualizado** (bootloader nuevo, aún no en listas de AV).
- **Inno Setup** con `PrivilegesRequired=lowest`, instalando en **`%LOCALAPPDATA%\MueblesYSillonesPanel`**. Crítico: en LocalAppData el panel **puede sobrescribir sus archivos sin pedir admin** (habilita el autoupdate). Esconde la carpeta onedir detrás de un `Setup.exe` con acceso directo, simple para no técnicos.
- **Excluir tkinter** y plugins de Pillow no usados (bundle más chico, menos superficie). Cuidar el hidden import de `PIL` (la distro es `pillow`, el import es `PIL`). **Probar el build en una PC limpia sin Python.**
- **Code signing:** NO al inicio (gratis no existe; EV ya no da reputación instantánea en 2025). Plan B si los AV insisten aún con onedir: migrar a **Nuitka** (binario compilado, casi sin falsos positivos), manteniendo Inno Setup + tufup.

### Autoupdate: **tufup** (sobre TUF) ✅ gratis + seguro + incremental
- Sucesor mantenido de PyUpdater (archivado). Delega la seguridad a **TUF** (firmas por rol: root/targets/snapshot/timestamp).
- **Backend gratis:** el repo de updates son **solo dos carpetas estáticas** (`metadata/` + `targets/`) servidas por **GitHub Pages**. Sin backend dinámico.
- **Descarga incremental:** el cliente baja un `.patch` (solo lo que cambió) en vez del .exe entero. Si cambian 200 KB, baja ~200 KB.
- **Setear expiraciones de metadata largas** (timestamp ~365 días) para no romper clientes si pasás tiempo sin publicar.

### MCP de control: **SDK oficial `mcp` (FastMCP), transporte stdio, local** ✅
- Corre como proceso local en tu PC, **NO expuesto a internet**, hablando JSON-RPC por stdin/stdout con Claude. Las credenciales sensibles (clave `targets` de TUF, admin-token) viven en variables de entorno locales del dev. El SDK oficial alcanza (no se necesitan los extras de auth de FastMCP standalone para un MCP local).

---

## 4) FLUJO DE AUTOACTUALIZACIÓN (detallado) y la restricción de Windows

### UX (popup → descargar → reemplazar → reiniciar)
1. **Al abrir el panel**, el cliente llama `client.check_for_updates()` (baja solo metadata, KB). Endpoint interno `GET /api/check-update`.
2. Si hay versión nueva → **modal HTML de marca** en la UI web del panel (más prolijo que Tkinter, consistente con el panel): "Hay una nueva versión (vX.Y) → Actualizar", con changelog en español (campo `custom` de TUF).
3. Al aceptar → `POST /api/apply-update` lanza en un thread `client.download_and_apply_update(skip_confirmation=True, progress_hook=...)`. El progreso se muestra por **SSE/websocket** (barra de descarga del `.patch`).
4. tufup **verifica las firmas TUF** antes de aplicar nada. Si la firma no valida o expiró, rechaza.

### Cómo se sortea la restricción de Windows (archivos en uso)
En Windows no se puede sobrescribir el `.exe`/DLLs mientras el proceso corre. tufup usa el patrón **updater externo desacoplado**:
1. Descomprime la versión nueva a un directorio temporal.
2. Genera un **.bat** desde un template, lo lanza con `CREATE_NEW_CONSOLE`/`CREATE_NO_WINDOW` (proceso separado que sobrevive al padre).
3. El panel hace **`sys.exit(0)`** → libera los locks.
4. El .bat hace **`robocopy /move /w:2`** (reintenta cada 2 s si un archivo sigue bloqueado) sobre el INSTALL_DIR en `%LOCALAPPDATA%` (sin admin).
5. El .bat **se auto-borra**.

**Relaunch (reinicio en la versión nueva):** el template por defecto de tufup NO relanza la app. Hay que **inyectar un `batch_template` custom** con `start "" "{new_exe_path}"` vía `batch_template_extra_kwargs`. Es trivial pero **hay que testearlo en una PC real** (el propio maintainer no lo probó). Para el usuario: ve el popup, acepta, la ventana se cierra un segundo y vuelve a abrir actualizada. El modal web debe reintentar `fetch` al panel cada 1–2 s y recargar cuando vuelve.

---

## 5) MODELO DE SEGURIDAD y SINCRONIZACIÓN

### La única credencial de GitHub
- **Fine-grained PAT** (no classic), apuntado a **un solo repo** (la intranet), permiso **Contents: read/write** y nada más, con **expiración** (ej. 90 días → fuerza rotación).
- Vive **solo** como **Secret del Worker** (`wrangler secret put`). Nunca en el .exe ni en las PCs. → Requisito #3 cumplido.

### Auth de los clientes (editores): **tokens por usuario** (no contraseña compartida)
- El cerebro guarda `{user_id, token_hash (argon2/bcrypt), activo, nombre}` en el storage del DO/KV.
- El cliente guarda su token cifrado (Windows DPAPI / `keyring`), no en texto plano. En el primer arranque se pide una vez.
- **Revocar a una persona** = `activo=false` vía MCP, inmediato, sin tocar las otras PCs. Permite **auditoría** (quién publicó qué). Todo sobre **HTTPS** + rate-limiting en el Worker.

### Claves de firma de updates (TUF)
- **root** (raíz de confianza) y **targets** (firma los bundles): **offline en TU PC**, con passphrase + backup (pendrive cifrado / gestor de contraseñas). El `root.json` inicial va **embebido en el .exe**.
- `snapshot`/`timestamp` se firman también en tu PC en cada publicación (todo offline para tu escala).

### Threat model + mitigaciones

| Amenaza | Mitigación |
|---|---|
| Se filtra un .exe | No contiene PAT ni claves de firma; sin token de usuario válido no publica |
| Descubren la URL del cerebro | Todo endpoint exige token (401 sin él); rate-limit; el DO se satura controladamente ante flood |
| Roban token de un usuario | Revocación inmediata vía MCP; tokens con expiración; audit log identifica daño |
| **Update malicioso** (.exe troyano a las 6 PCs) | **TUF lo bloquea**: el cliente solo acepta bundles firmados por la clave `targets` offline. Sin ella no se forja metadata válida. Protege también rollback/freeze/replay |
| Compromiso del Worker | PAT limitado a 1 repo + contents:write (no borra repo ni toca otros); rotar PAT vía MCP |
| Compromiso de tu PC | Punto más crítico (tiene `targets`): passphrase + idealmente hardware token; root offline permite re-emitir targets |

### Sincronización sin conflictos (3–6 editores, 1 repo)
- **El cerebro serializa, no los clientes:** Durable Object único → una publicación a la vez. Elimina carreras de git de raíz.
- **Optimistic concurrency con SHA** por robustez: commit atómico con `parents=[ref_actual]` + `PATCH ref force:false`; si non-fast-forward → re-leer y reintentar (3–5 intentos con backoff).
- **El cliente NO clona el repo** (es delgado; el cerebro es el único que comitea) → no necesita `git pull`.
- **A nivel aplicación:** el cliente lee el estado fresco al abrir un ítem y manda el **SHA base** sobre el que editó. Si ese ítem cambió desde entonces, el cerebro responde "conflicto: recargá" en vez de pisar el trabajo de otro.

---

## 6) PLAN POR FASES

### Fase 0 — Setup de cuentas (lo hace el USUARIO, gratis, ~1 hora)
- Crear cuenta **Cloudflare** (gratis) e instalar `wrangler` (lo guío).
- Generar **fine-grained PAT** en GitHub (1 repo, Contents R/W, expiración 90 días).
- Crear **repo público de updates** en GitHub + activar **GitHub Pages**.
- *Yo entrego:* checklist exacto paso a paso con capturas de qué clickear.

### Fase 1 — Cerebro mínimo (lo construyo YO)
- Worker con endpoint `POST /publish` + Durable Object cola + auth por token + Git Data API (blobs→tree→commit→ref con reintento) + audit log.
- *Usuario:* cargar el PAT como secret (`wrangler secret put GITHUB_TOKEN`), desplegar (`wrangler deploy`).
- **Hito:** publicar un cambio de prueba a la intranet desde un `curl`.

### Fase 2 — Cliente .exe delgado (lo construyo YO)
- Adaptar el panel actual: en vez de `git push`, hace `POST /publish` al Worker; Pillow + base64 en el cliente; guardado cifrado del token de usuario (DPAPI).
- Empaquetar con **PyInstaller --onedir --noupx** + **Inno Setup** (LocalAppData, sin admin).
- **Probar en PC limpia sin Python** (Pillow carga, publica OK).
- *Usuario:* probar el `Setup.exe` en una PC del equipo.
- **Hito:** una persona no técnica instala y publica.

### Fase 3 — Autoupdate (lo construyo YO)
- `tufup init` (genero claves, root.json embebido), integrar `Client` con las 2 URLs de GitHub Pages, endpoints `/api/check-update` + `/api/apply-update`, modal HTML + SSE, **batch_template custom con relaunch**, expiraciones largas.
- **Testear el ciclo completo en PC real** (popup → patch → cierra → relanza vX+1).
- *Usuario:* guardar las claves `root`/`targets` con backup.
- **Hito:** publico una v2 y una PC del equipo se actualiza sola con popup.

### Fase 4 — MCP de control (lo construyo YO)
- MCP stdio `mys-control` con tools: `publicar_version`, `ver_estado`, `historial`, `quien_publico_ultimo`, `listar/agregar/revocar_usuario`, `rotar_credencial_github`.
- *Usuario:* registrar el MCP en Claude Desktop/Code (config local), tokens admin en env vars.
- **Hito:** publicás una mejora end-to-end diciéndomelo a mí, sin tocar terminal.

### Fase 5 — Rollout al equipo (3–6 personas)
- Emitir un token por persona (`agregar_usuario`), distribuir el `Setup.exe`, cada uno ingresa su token una vez.
- Documento de "primera vez" (incluye el "Más información → Ejecutar de todos modos" de SmartScreen).

---

## 7) RIESGOS y LÍMITES (honestos)

1. **CPU 10 ms en Cloudflare free.** Riesgo real solo si el Worker hiciera base64 de imágenes; lo evitamos haciéndolo en el cliente. Escape: Workers Paid USD 5/mes o Deno Deploy. **Validar con una imagen real en Fase 1.**
2. **Falsos positivos de antivirus/SmartScreen.** Mitigados con onedir + sin UPX + PyInstaller al día, pero **pueden seguir apareciendo**. Plan B real: migrar a Nuitka. Sin firma, el equipo verá un warning una vez por versión.
3. **Relaunch de tufup en Windows no es "de fábrica"** — requiere batch_template custom y testeo en PC real; el maintainer mismo no lo probó. Es el punto más frágil del autoupdate.
4. **Expiración de metadata TUF.** Si pasás mucho sin publicar y las expiraciones fueran cortas, los clientes rechazan updates. Mitigación: timestamp ~365 días.
5. **Tu PC es el punto crítico de seguridad** (tiene la clave `targets`). Si se compromete, se pueden firmar updates maliciosos. Passphrase + backup de root/targets es no negociable.
6. **GitHub Releases no sirve como backend de tufup** (no da el layout metadata/targets) → usar GitHub Pages, repo público.
7. **Code signing desde Argentina:** Azure Artifact Signing "Individual" no está disponible (solo USA/Canadá); habría que validar la mueblería como **organización** (~USD 10/mes). Por eso el plan base **no depende de firma**.
8. **El cliente es delgado a propósito:** si el Worker está caído, nadie publica (single point of failure). Aceptable para el caso; Cloudflare tiene alta disponibilidad y sin cold start.

---

# ANEXO — Investigaciones completas (crudas)


## Anexo 1 — El cerebro serverless gratis

I have enough to synthesize. Here is my report.

---

# INVESTIGADOR #1 — El "Cerebro" Serverless Gratis

## Veredicto corto

**Recomendación: Cloudflare Workers** como cerebro, comiteando vía la **GitHub Git Data API** (blobs base64 → tree → commit → update ref con optimistic locking), y serializando con **Durable Objects** (o un simple reintento sobre el SHA del ref). Es la única opción que cumple los 4 requisitos duros sin asteriscos: gratis de verdad, **uso comercial permitido**, body de hasta **100 MB** (sobra para imágenes de 2 MB), secretos cifrados nativos y arranque sin cold start.

El descarte importante: **Vercel Functions NO sirve** — su plan Hobby es explícitamente **no comercial**, y la mueblería es uso comercial. Tendrías que pagar Pro (USD 20/mes), lo que rompe el requisito #1.

---

## 1) Comparativa de plataformas

| Plataforma | ¿Comercial gratis? | Límite body (subir img) | Invocaciones / CPU | Cold start | Secretos |
|---|---|---|---|---|---|
| **Cloudflare Workers** | ✅ **Sí**, explícito | **100 MB** (límite de cuenta, no de Workers) | 100.000 req/día; **10 ms CPU**/req (pero el I/O esperando a GitHub NO cuenta como CPU) | **~0 ms** (sin cold start) | `wrangler secret put`, cifrados; 64 vars/Worker, 5 KB c/u |
| **Deno Deploy** | ✅ Sí | No documenta límite explícito de body; memoria 512 MB | 1 M req/mes; **50 ms CPU**/req | Bajo | Env vars cifradas en dashboard |
| **Supabase Edge Functions** | ✅ Sí | No documentado oficialmente (usuarios reportan límite); idle 150 s | 500.000 invocaciones/mes; **2 s CPU**/req; 150 MB RAM | Moderado (Deno) | Project secrets vía Dashboard/CLI |
| **Val.town** | ⚠️ No aclara restricción comercial en free (verificar); pensado para prototipos | Modesto (plataforma de "vals" cortos) | 100.000 runs/día | Moderado | Env/secrets en la plataforma |
| **GitHub Actions** (`repository_dispatch`) | ✅ Repos públicos: minutos ilimitados. Privados: 2.000 min/mes | El payload del dispatch es chico (~64 KB de `client_payload`) → **NO sirve para mandar imágenes de 2 MB inline** | Cola de jobs, arranque del runner ~lento (segundos) | Lento (levanta VM) | GitHub Secrets nativos |
| **Vercel Functions** | ❌ **Hobby = NO comercial**; comercial exige Pro USD 20/mes | 4.5 MB body en funciones | — | Bajo | Env vars cifradas |

### Notas honestas por plataforma

- **Cloudflare Workers (la elegida).** El único "pero" es el **10 ms de CPU** en free. Suena aterrador, pero **el tiempo esperando respuestas de la API de GitHub (subrequests/fetch) NO cuenta como CPU** — solo cuenta el cómputo real de tu JS. Comitear es 95% espera de red. El riesgo real de CPU es **codificar a base64** imágenes grandes en JS; para 2 MB son pocos milisegundos con `btoa`/buffers, así que entra cómodo. Si alguna vez te pasás, el plan pago es USD 5/mes (no gratis, pero barato y con uso comercial). Sin cold start es ideal para el popup de autoupdate y para que la gente no espere.
- **Deno Deploy.** Segundo lugar y muy digno: 50 ms de CPU (5× Cloudflare) y comercial permitido. No publica límite de body claro, lo cual es un riesgo a validar antes de comprometerse. Si Cloudflare te incomodara por el CPU, este es el plan B.
- **Supabase Edge Functions.** Generoso en CPU (2 s) y comercial OK, pero es más pesado de operar (proyecto Supabase entero, que además **se pausa por inactividad** en free) para algo que solo necesita comitear a GitHub. Overkill.
- **GitHub Actions / `repository_dispatch`.** Tentador porque el secreto vive en GitHub Secrets y no necesitás otro servicio. **Problema fatal para tu caso:** el `client_payload` del dispatch está limitado a ~64 KB, así que **no podés mandar la imagen binaria por ahí**. Además el runner tarda segundos en levantar. Sirve solo como disparador, no como receptor de imágenes.
- **Vercel Functions.** Descartado por licencia (Hobby no comercial). No lo uses para el cerebro.
- **Val.town.** Bueno para prototipar en minutos, pero no me consta que el free habilite uso comercial sin restricciones y los límites de cómputo/almacenamiento son chicos. No lo pondría en producción para 6 personas.

---

## 2) Cómo comitear a GitHub desde serverless SIN git instalado

Se usa la **GitHub Git Data API** (REST, low-level). Un commit atómico multi-archivo (texto + imágenes binarias) son **5 llamadas**:

1. **Leer el ref actual** — `GET /repos/{owner}/{repo}/git/ref/heads/{branch}` → te da el `sha` del último commit (= base para optimistic locking).
2. **Crear blobs** — `POST /repos/{owner}/{repo}/git/blobs` por cada archivo.
   - Texto (HTML/JS): `{"content": "...", "encoding": "utf-8"}`.
   - **Imágenes binarias**: `{"content": "<base64>", "encoding": "base64"}`. Acá es donde entra Pillow del cliente: normaliza, y el cliente o el Worker codifica a base64.
3. **Crear el tree** — `POST /repos/{owner}/{repo}/git/trees` con `base_tree` = tree del commit base, y un array de entradas `{path, mode:"100644", type:"blob", sha:<blob_sha>}`. Esto preserva el resto del repo y solo cambia los archivos tocados → **commit atómico de N archivos**.
4. **Crear el commit** — `POST /repos/{owner}/{repo}/git/commits` con `message`, `tree` (el del paso 3) y `parents:[<sha del paso 1>]`.
5. **Mover el ref** — `PATCH /repos/{owner}/{repo}/git/refs/heads/{branch}` con `{"sha": <nuevo commit>, "force": false}`. Con `force:false`, GitHub **rechaza con 422 si no es fast-forward** → este es el candado de concurrencia (ver punto 3).

Una vez movido el ref, **Vercel auto-deploya** la intranet como hoy.

### Límites de tamaño de la API (clave para imágenes)
- **Blob individual:** hasta **100 MB**.
- **Payload de la request:** **40 MiB por llamada** (aplica a todos los endpoints; lo notás al crear blobs/trees grandes). Tus imágenes son ~2 MB → sin problema. Ojo: **base64 infla ~33%**, así que 2 MB binario ≈ 2.7 MB en la request. Sigue holgadísimo.
- Si algún día subieran muchísimas imágenes de golpe y un tree pasara los 40 MiB, se chunkea el tree en varias llamadas encadenadas (cada tree referencia al anterior). No es tu caso con 1-pocas imágenes por publicación.
- **No conviene la Contents API** (`PUT /contents/{path}`): tiene tope práctico de **1 MB** por archivo y solo edita 1 archivo por llamada (no atómico multi-archivo). La Git Data API es la correcta.

---

## 3) Serializar publicaciones concurrentes (3-6 personas, sin conflictos)

El mecanismo nativo es **optimistic locking con el SHA del ref**:

- Cada publicación parte del `sha` leído en el paso 1. Al hacer `PATCH .../refs` con `force:false`, si **otra persona comiteó en el medio**, el ref ya no apunta a tu base → GitHub responde **error de non-fast-forward (422)**. Ese es tu detector de conflicto (equivalente al 409 de concurrencia: "está en SHA X pero esperabas SHA Y").
- **Estrategia de reintento:** al recibir el rechazo, el Worker **re-lee el ref, re-arma tree/commit sobre la nueva base y reintenta** (con backoff y un par de intentos). Como cada quien toca archivos distintos (distintas placas/productos), el merge lógico casi siempre es trivial y el reintento pasa solo.
- **Para garantizar orden estricto** y evitar tormentas de reintentos con 6 personas publicando a la vez, en Cloudflare usás un **Durable Object** como mutex/cola: un único DO serializa las publicaciones (una a la vez), de modo que nunca hay dos PATCH compitiendo. Es el "servidor que organiza solo" que pediste. Los Durable Objects tienen capa gratuita en el plan Workers.
- Alternativa sin DO: una **cola en memoria/KV** dentro del Worker + el reintento optimista. Funciona para 6 personas, pero el DO es más limpio y determinista.

---

## 4) Autenticar a los clientes (que SOLO el equipo publique)

El token de GitHub **nunca** va al cliente (ese es todo el punto de centralizar). El cliente se autentica contra **tu** Worker:

- **Opción simple (recomendada para arrancar):** un **secreto de aplicación compartido** (una "API key" larga generada por vos) que el .exe envía en un header `Authorization`. El Worker lo compara (en tiempo constante) contra un secreto guardado con `wrangler secret put`. Si no coincide → 401. El token de GitHub también vive como secreto del Worker. Riesgo honesto: una sola clave para todos → si se filtra, la rotás y reempaquetás el .exe (o la entregás por config, no hardcodeada).
- **Opción mejor (por usuario):** **un token por persona** (6 strings), guardados como un JSON en un secreto del Worker o en **Workers KV**. Así podés **revocar a una sola persona** sin romper a los demás, y además logueás quién publicó cada cambio (auditoría). Es poco más de trabajo y vale la pena para un equipo.
- **Dónde guardar la clave en el cliente:** no la hardcodees en el .exe. Mejor: en el primer arranque el panel pide la clave una vez y la guarda cifrada en el perfil del usuario (Windows DPAPI / Credential Manager). Así el binario es el mismo para todos y la credencial es por-PC.
- Reforzá con: **HTTPS obligatorio** (Workers ya es TLS), rate-limiting básico por clave, y opcionalmente restringir por algo identificable. No expongas el endpoint sin auth ni un segundo.

---

## Arquitectura concreta recomendada

```
.exe cliente (UI + Pillow, normaliza imagen a <=1568px, RGB/RGBA)
   │  POST https://panel-mys.<sub>.workers.dev/publish
   │  Header: Authorization: <token-por-usuario>
   │  Body JSON: { archivos:[{path, encoding, content/base64}], mensaje }
   ▼
Cloudflare Worker  ──(Durable Object = cola/mutex)──► serializa
   │  secretos: GITHUB_TOKEN (fine-grained PAT, solo este repo, scope contents:write)
   │            + lista de tokens del equipo
   ▼
GitHub Git Data API: ref → blobs(base64) → tree(base_tree) → commit → PATCH ref (force:false)
   │  conflicto? → re-lee ref, reintenta
   ▼
GitHub repo  ──auto-deploy──►  Vercel (intranet que ven los vendedores)
```

**Costo: USD 0/mes** en uso real (6 personas, decenas de publicaciones/día están MUY por debajo de 100.000 req/día). Uso comercial permitido. Sin cold start. El `GITHUB_TOKEN` debe ser un **fine-grained PAT** limitado a ese único repo con permiso `Contents: read/write`, para minimizar daño si algo se filtra.

**Único riesgo a tener en el radar:** el límite de **10 ms de CPU** de Cloudflare free. Mitigación: que el **cliente** (que ya corre Pillow) haga el base64 y mande el JSON listo, dejando al Worker solo orquestar llamadas de red (I/O, que no cuenta como CPU). Si aun así molesta, Workers Paid (USD 5/mes, comercial) o Deno Deploy (50 ms CPU, gratis) son escapes inmediatos sin rediseñar.

---

## Fuentes

- [Cloudflare Workers — Limits (oficial)](https://developers.cloudflare.com/workers/platform/limits/)
- [Cloudflare Workers — Pricing (oficial)](https://developers.cloudflare.com/workers/platform/pricing/)
- [Cloudflare Free Plan Limits 2026 (análisis)](https://eastondev.com/blog/en/posts/dev/20251201-cloudflare-pricing-compare/)
- [Vercel — Terms of Service (Hobby = no comercial)](https://vercel.com/legal/terms)
- [Vercel — Hobby Plan](https://vercel.com/docs/plans/hobby) · [Fair Use Guidelines](https://vercel.com/docs/limits/fair-use-guidelines)
- [Deno Deploy — Pricing and limitations](https://docs.deno.com/deploy/pricing_and_limits/)
- [Supabase — Edge Functions Limits](https://supabase.com/docs/guides/functions/limits) · [Secrets](https://supabase.com/docs/guides/functions/secrets) · [AUP](https://supabase.com/aup)
- [Val Town — Pricing](https://www.val.town/pricing) · [Limits](https://www.val.town/limits)
- [GitHub REST — Git blobs](https://docs.github.com/en/rest/git/blobs) · [Git trees](https://docs.github.com/en/rest/git/trees)
- [Commit signing con la Git Database API (flujo blob→tree→commit→ref)](https://peterevans.dev/posts/commit-signing-with-github-git-database-api/)
- [Gotchas con Git y la GitHub API (límite payload 40 MiB)](https://retool.com/blog/gotchas-git-github-api)
- [Commit a file con la GitHub API (Levi Botelho)](https://www.levibotelho.com/development/commit-a-file-with-the-github-api/)
- [GitHub — non-fast-forward / 409 en commits concurrentes (PyGithub #1787)](https://github.com/PyGithub/PyGithub/issues/1787)

## Anexo 2 — Empaquetado .exe Windows

He investigado los cuatro puntos. Acá va el informe.

---

# INVESTIGADOR #2 — Empaquetado .EXE para Windows (gente no técnica)

## RESUMEN EJECUTIVO (recomendación)

Para minimizar problemas de antivirus, ser gratis y simple para no técnicos:

**PyInstaller en modo `--onedir` (NO `--onefile`), sin UPX, empaquetado dentro de un instalador Inno Setup con `PrivilegesRequired=lowest` que instala en `%LOCALAPPDATA%`, + tufup para autoupdate.**

El factor #1 que dispara los antivirus y SmartScreen es el patrón "un solo .exe que se autoextrae en temp" de `--onefile`. Cambiando a `--onedir` (carpeta con el .exe + DLLs sueltas) desaparece la mayoría de los falsos positivos, el arranque es más rápido, y encima `--onedir` es lo que tufup necesita para autoactualizarse limpio. El instalador Inno Setup oculta el "desorden" de la carpeta onedir detrás de un `Setup.exe` con acceso directo, igual de simple para el usuario que un .exe suelto.

El code signing **no es obligatorio** pero ayuda; gratis no existe. La opción barata realista es Azure Trusted/Artifact Signing (~USD 9,99/mes) pero **OJO: para "Individual" hoy solo está habilitado en USA y Canadá** — un desarrollador en Argentina no califica como individuo (habría que validar como organización). Por eso el plan base debe funcionar SIN firma.

---

## 1) Empaquetar Python (http.server stdlib + Pillow) como .exe sin instalar Python

Las tres vías y su veredicto:

### PyInstaller — `--onefile` vs `--onedir`
- **`--onefile`**: genera UN solo `.exe`. En runtime se autoextrae a una carpeta temporal y ejecuta desde ahí. Ventaja: un único archivo para distribuir. Desventajas: **arranque más lento** (descomprime todo cada vez), y ese patrón "extraer-y-ejecutar" es exactamente lo que hacen los packers de malware → **muchos más falsos positivos de AV**.
- **`--onedir`** (el modo por defecto de PyInstaller): genera una carpeta con el `.exe` + el intérprete + DLLs sueltas. No extrae nada en runtime → **arranque más rápido y menos sospechoso para el AV**. Desventaja: es una carpeta con muchos archivos (por eso se envuelve en un instalador).
- PyInstaller analiza tu script, descubre los imports y copia el intérprete Python activo + librerías. Soporta bien dependencias binarias como Pillow "out of the box". Único contra real de onedir: estética/distribución (se resuelve con Inno Setup).

### Nuitka
- Es un **compilador real**: traduce Python → C → binario nativo. Por eso **dispara muchísimos menos falsos positivos** (es un binario compilado genuino, no "intérprete + script empaquetado") y puede correr más rápido.
- Contras: **compilación mucho más lenta y compleja** (necesita un toolchain C/MinGW o MSVC), y la integración con autoupdate (tufup) y con assets/binarios de Pillow es más artesanal. Para un equipo chico que necesita iterar rápido y autoupdate simple, agrega fricción.

### Embeddable Python + launcher
- Combinás el "Windows embeddable package" de python.org (intérprete mínimo) + tus wheels + un launcher (p.ej. `python-embedded-launcher`). Da mucho control y un buen arranque.
- Contras: **el embeddable no trae pip ni venv**, hay que armar todo a mano y escribir el launcher. Más trabajo de mantenimiento; no vale la pena frente a PyInstaller onedir para este caso.

**Tamaño/velocidad (orden general):** onedir arranca más rápido que onefile; Nuitka suele dar el binario más "liviano en comportamiento" pero compila lento; embeddable es liviano pero manual.

**Veredicto punto 1:** PyInstaller `--onedir`. Nuitka es el plan B "si los AV siguen molestando aún con onedir".

---

## 2) Falsos positivos de Antivirus / SmartScreen (el problema real)

**Qué tan grave:** real y frecuente con PyInstaller, sobre todo `--onefile`. Causas: (a) el patrón packer extraer-y-ejecutar; (b) el **bootloader de PyInstaller** quedó en listas de amenazas porque autores de malware también usan PyInstaller → "culpa por asociación". Windows Defender/SmartScreen y AVs de terceros (AVG, etc.) pueden marcar tu .exe sano como troyano.

**Mitigaciones GRATIS (en orden de impacto):**
1. **Usar `--onedir` en vez de `--onefile`** → la mitigación más efectiva y gratis. Elimina el comportamiento de autoextracción.
2. **NO usar UPX** (`--noupx` / no comprimir). La compresión UPX es un disparador clásico de heurísticas.
3. **Mantener PyInstaller actualizado**: el equipo recompila el bootloader periódicamente; una versión nueva todavía no está en las listas de los AV.
4. **Reportar el falso positivo** a cada vendor (Microsoft, AVG…): suelen whitelistear en pocos días.
5. **Construir reputación** (SmartScreen): hoy SmartScreen evalúa **reputación de publisher + reputación de hash de archivo**. Un archivo nuevo/desconocido = warning hasta acumular descargas/uso. Como ustedes lo instalan en 3-6 PCs internas, pueden convivir con eso (el usuario hace "Más información → Ejecutar de todos modos" una vez por versión).

**¿Code signing es necesario? ¿Cuánto cuesta? ¿Gratis?**
- **No es estrictamente necesario** para uso interno, pero reduce warnings y falsos positivos. **Gratis no hay** (la emisión/validación tiene costo real).
- **Dato clave 2025:** firmar con **EV ya NO da reputación SmartScreen instantánea** como antes. Tanto OV como EV deben **construir reputación igual**. O sea, pagar EV solo para evitar el warning **ya no se justifica**.
- Precios orientativos: **OV** desde ~USD 215-230/año (Sectigo/Comodo por reseller), **EV** desde ~USD 295/año.
- **Opción barata: Azure Trusted Signing / Artifact Signing ~USD 9,99/mes** (perfil "Public Trust" evita warnings de SmartScreen). **PERO la validación "Individual" hoy solo está disponible para desarrolladores de USA y Canadá**; la UE/UK solo para organizaciones, y otros países (Argentina) quedan afuera como individuo. Para usarlo desde Argentina probablemente haya que validar como **organización** (la mueblería como empresa), lo cual requiere documentación de la empresa y antigüedad. Dado el requisito "gratis", **el plan no debe depender de firma**.

**Conclusión punto 2:** onedir + sin UPX + PyInstaller al día + reportar falsos positivos. Firma = opcional/futuro, y si se hace, Azure Artifact Signing como organización (no EV caro).

---

## 3) Instalador: Inno Setup, por-usuario, sin admin, compatible con auto-update

- **Inno Setup** (gratis) crea un `Setup.exe` con acceso directo en Escritorio/Menú Inicio. Envuelve la carpeta `--onedir` para que el usuario vea una instalación limpia.
- **Sin admin / por-usuario:** en `[Setup]` poner **`PrivilegesRequired=lowest`** (o `none`). Con `lowest`, Setup no pide elevación, la info de desinstalación va a **`HKEY_CURRENT_USER`**, y las constantes de carpeta "common" se mapean a las "user". **No instalar nada en `{pf}`, `{win}`, `{sys}`**.
- **Carpeta escribible para auto-update:** instalar en **`{localappdata}`** (`%LOCALAPPDATA%\MueblesYSillonesPanel` o `{userappdata}`). Esto es **crítico** para el autoupdate: si instalás en `Program Files`, actualizar requiere admin; instalando en `%LOCALAPPDATA%` el propio panel puede **reemplazar sus archivos sin pedir permisos**.
- Conviene `DefaultDirName={localappdata}\...` y, si querés ser elegante, una sección `[Code]` que detecte si corre elevado y elija Program Files vs carpeta de usuario; pero para no técnicos, **fijar siempre `%LOCALAPPDATA%` es lo más simple y robusto**.

---

## 4) Integración con autoupdate (tufup) y con Pillow

### tufup (autoupdate)
- **tufup** es el sucesor de **PyUpdater** (PyUpdater está archivado/sin mantenimiento). Usa **TUF (The Update Framework)** por debajo → descargas firmadas/seguras de los bundles.
- **Independiente del empaquetador**: mueve "bundles de archivos de A a B" de forma segura; sirve para un script, un bundle PyInstaller, PEX, etc. Encaja perfecto con `--onedir` (la carpeta es el bundle).
- Hay **repo de ejemplo oficial** `dennisvang/tufup-example` con un `.spec` de PyInstaller que **incluye el `root.json`** (metadata raíz de TUF) dentro del bundle — ese es el gotcha principal: hay que empaquetar `root.json` en el app.
- Encaja con el flujo del usuario: al abrir, el panel chequea el repo de updates, si hay versión nueva muestra popup, descarga, aplica y reinicia. Como instala en `%LOCALAPPDATA%`, puede sobrescribirse sin admin. El "servidor de updates" puede ser estático/gratis (mismo modelo que ya usan con GitHub/Vercel: publicar los bundles + metadata como archivos estáticos).

### Pillow + PyInstaller (gotchas)
- **`ModuleNotFoundError: No module named 'PIL'`** es el problema típico: PyInstaller a veces no detecta PIL, o el nombre de distribución confunde (la distro es **`pillow`**, el paquete import es **`PIL`**). Solución: agregar **hidden imports** y/o el hook correcto. Si usás `--exclude`/hiding imports, podés romper PIL.
- **tkinter/Tcl-Tk:** PyInstaller bundlea las DLLs de tcl/tk; con `--onefile` se extraen al arrancar (más lento). Como tu panel abre el navegador (no usa GUI tkinter), conviene **excluir tkinter** (`--exclude-module tkinter`) y los plugins de PIL que no uses → bundle más chico y menos superficie para falsos positivos. Si en algún momento usás `PIL.ImageTk`, ahí sí necesitás tkinter.
- **Plugins de Pillow:** si usás formatos puntuales y PyInstaller no los incluye, agregar el plugin como hidden import (p.ej. los `*ImagePlugin`). Para normalizar RGB/RGBA y redimensionar (tu caso) el hook estándar de Pillow alcanza, pero **conviene un build de prueba en una PC limpia** (sin Python) para confirmar que Pillow carga.

---

## RECOMENDACIÓN FINAL (stack concreto)

1. **PyInstaller `--onedir --noupx`**, excluyendo tkinter si no se usa, PyInstaller siempre actualizado.
2. **Inno Setup** con `PrivilegesRequired=lowest`, instalando en **`%LOCALAPPDATA%`** (clave para autoupdate sin admin) + acceso directo.
3. **tufup** para el popup "Hay actualización → Actualizar", con `root.json` incluido en el `.spec`; bundles servidos como estáticos gratis (GitHub/Vercel).
4. **Sin code signing al inicio** (gratis no existe y EV ya no da reputación instantánea). Mitigar AV con onedir + sin UPX + reportar falsos positivos. Dejar la firma (Azure Artifact Signing, validando como **organización** la mueblería, ~USD 9,99/mes) como mejora futura si SmartScreen molesta mucho.
5. **Plan B** si los AV siguen molestando aún con onedir: migrar el build a **Nuitka** (binario compilado, casi sin falsos positivos), manteniendo Inno Setup + tufup.

---

## Fuentes

- [PyInstaller issue #6754 — onefile AV false positives](https://github.com/pyinstaller/pyinstaller/issues/6754)
- [CodersLegacy — PyInstaller EXE detected as virus: solutions](https://coderslegacy.com/pyinstaller-exe-detected-as-virus-solutions/)
- [PythonGUIs — Fix antivirus false positives with PyInstaller](https://www.pythonguis.com/faq/problems-with-antivirus-software-and-pyinstaller/)
- [DEV — From PyInstaller to Nuitka: convert to EXE without false positives](https://dev.to/weisshufer/from-pyinstaller-to-nuitka-convert-python-to-exe-without-false-positives-19jf)
- [CodersLegacy — Nuitka vs PyInstaller](https://coderslegacy.com/nuitka-vs-pyinstaller/)
- [Microsoft Learn — SmartScreen reputation for Windows app developers](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)
- [Microsoft Q&A — Reputation with OV vs EV certificates](https://learn.microsoft.com/en-us/answers/questions/417016/reputation-with-ov-certificates-and-are-ev-certifi)
- [SSL.com — Which code signing cert do I need, EV or OV](https://www.ssl.com/faqs/which-code-signing-certificate-do-i-need-ev-ov/)
- [CheapSSLSecurity — Code signing certificate pricing](https://cheapsslsecurity.com/sslproducts/codesigningcertificate.html)
- [Microsoft Learn — Artifact/Trusted Signing FAQ](https://learn.microsoft.com/en-us/azure/artifact-signing/faq)
- [Microsoft — Trusted Signing open for individual developers (Public Preview)](https://techcommunity.microsoft.com/blog/microsoft-security-blog/trusted-signing-is-now-open-for-individual-developers-to-sign-up-in-public-previ/4273554)
- [Inno Setup docs — PrivilegesRequired](https://documentation.help/Inno-Setup/topic_setup_privilegesrequired.htm)
- [Kinook — Creating a non-admin installer with Inno Setup](https://kinook.com/blog2/inno-setup.html)
- [tufup — GitHub](https://github.com/dennisvang/tufup) · [tufup-example](https://github.com/dennisvang/tufup-example)
- [PyInstaller issue #5856 — fails to load PIL after hiding imports](https://github.com/pyinstaller/pyinstaller/issues/5856)
- [PyInstaller docs — Hooks](https://pyinstaller.org/en/stable/hooks.html)
- [python-embedded-launcher — PyPI](https://pypi.org/project/python-embedded-launcher/0.3.1/)
- [PyInstaller docs — What PyInstaller does (onefile vs onedir)](https://pyinstaller.org/en/stable/operating-mode.html)

## Anexo 3 — Autoactualización (tufup)

# INVESTIGADOR #3 — AUTOACTUALIZACIÓN (tufup) — Informe

## 1) Qué es tufup y cómo funciona

**tufup** (`pip install tufup`, repo: `github.com/dennisvang/tufup`) es el sucesor directo y mantenido de PyUpdater (que está archivado). Está construido **encima de `python-tuf`** (The Update Framework, el estándar de seguridad de actualizaciones de la Linux Foundation/PyPI). La idea de diseño es clave: PyUpdater inventaba su propia criptografía; tufup delega TODA la seguridad a TUF y solo aporta las herramientas de alto nivel. Es **independiente del empaquetador**: le da igual si el "bundle" es un script, un PyInstaller onedir, un PEX, etc. — su trabajo es "mover bundles de A a B de forma segura".

**Modelo TUF (roles y firmas).** tufup usa los 4 roles top-level de TUF (no soporta delegations):
- `root` — la raíz de confianza; firma qué claves son válidas para los otros roles. El cliente se embarca con un `root.json` inicial.
- `targets` — firma los hashes/longitudes de los archivos reales (tus bundles).
- `snapshot` — firma la lista/versión de toda la metadata.
- `timestamp` — firma frecuente y de vida corta que dice "esta es la última metadata" (previene ataques de freeze/replay).

Cada rol tiene su **par de claves**. El cliente verifica la cadena de firmas antes de aplicar nada; si la firma no valida o la metadata expiró, **rechaza** la actualización. Esto te protege incluso si el servidor de updates es comprometido (el atacante no tiene las claves privadas).

**Archives vs Patches.** Internamente tufup maneja dos tipos de target:
- **Archives**: bundle completo comprimido, formato `<name>-<version>.tar.gz` (versiones en PEP440).
- **Patches**: diferencia binaria entre dos archives consecutivos, sufijo `.patch`.

El cliente **siempre intenta actualizar con patches** (más chicos = menos descarga). Pero si la suma de los patches necesarios pesa más que bajar el archive completo, hace un **full update**. Esto es exactamente el "descargar solo lo que cambió" que pedís: si entre v1.0 y v1.1 cambiaste 200 KB, el cliente baja un `.patch` de ~200 KB, no el .exe entero de 30 MB.

### ¿Sirve GitHub gratis como backend de updates? SÍ.

Esto es lo importante para tu requisito de costo cero. **El "repositorio de updates" de tufup es simplemente dos carpetas de archivos estáticos**: `metadata/` (los `root.json`, `targets.json`, `snapshot.json`, `timestamp.json`) y `targets/` (los `.tar.gz` y `.patch`). El cliente solo necesita **dos URLs base** (`metadata_base_url` y `target_base_url`) servidas por **HTTPS estático**. No hay backend dinámico.

Confirmado por el maintainer (discusión #30 de tufup-example): "tu servidor remoto simplemente necesita servir el contenido de `metadata` y `targets`, igual que lo hace el servidor local". Por lo tanto cualquier host estático sirve: **GitHub Pages, GitHub raw del repo, S3, Cloudflare Pages, Netlify**. 

- **GitHub Pages / raw**: gratis, HTTPS, perfecto para un equipo de 6 PCs. El repo debe ser **público** para servir por Pages/raw sin token (la metadata y los targets no son secretos; lo único secreto son las **claves privadas de firma**, que NUNCA van al repo).
- **GitHub Releases**: tufup **no** lo soporta nativamente como backend (issue #63 lo pidió; sigue sin soporte oficial) porque Releases no te da el layout de carpetas `metadata/targets` con paths predecibles. Pages o raw es el camino limpio.

**Caveat de TUF — expiración de metadata**: `timestamp` y `snapshot` tienen fechas de expiración cortas por diseño. Si publicás seguido no hay problema, pero si pasan semanas sin publicar, la metadata puede expirar y el cliente la rechazará. Solución: re-firmar/re-publicar periódicamente (un job que regenera timestamp), o setear expiraciones largas al inicializar el repo. Para tu caso (publicás mejoras vía el MCP cada tanto) conviene **expiraciones generosas** (ej. timestamp 365 días) para no romper clientes.

---

## 2) La UX exacta: chequeo → popup → descarga incremental → aplicar → reiniciar

### Instanciación del cliente (de tufup-example, `src/myapp/__init__.py`)

```python
from tufup.client import Client

client = Client(
    app_name=settings.APP_NAME,
    app_install_dir=settings.INSTALL_DIR,      # donde vive el .exe instalado
    current_version=settings.APP_VERSION,      # versión embebida en este build
    metadata_dir=settings.METADATA_DIR,        # cache local de metadata
    metadata_base_url=settings.METADATA_BASE_URL,  # ej. https://TUUSUARIO.github.io/panel-updates/metadata/
    target_dir=settings.TARGET_DIR,            # cache local de targets
    target_base_url=settings.TARGET_BASE_URL,  # ej. https://TUUSUARIO.github.io/panel-updates/targets/
    refresh_required=False,
)
```

### Flujo de dos pasos

**Paso A — chequear (rápido, solo metadata):**
```python
new_update = client.check_for_updates(pre=None)  # pre='a'/'b'/'rc' para canales beta
if new_update:
    # new_update.version  -> la versión nueva
    # new_update.custom    -> tu metadata custom (ej. changelog en español)
    mostrar_popup(new_update)
```
`check_for_updates()` solo baja metadata (KB), compara versiones PEP440 y por defecto **filtra pre-releases**. Devuelve `None` si estás al día.

**Paso B — al aceptar el popup, descargar+aplicar (esto baja los patches y reinicia):**
```python
client.download_and_apply_update(
    skip_confirmation=True,          # ya confirmó en TU popup
    progress_hook=progress_hook,     # callback de progreso
    purge_dst_dir=False,             # OJO: dejar False salvo install dir dedicado
    exclude_from_purge=None,
    log_file_name='install.log',
)
```
Por debajo: elige patch-vs-full, verifica firmas TUF, descomprime a un temp, lanza el script de instalación (ver punto 3) y hace `sys.exit(0)` del proceso actual.

**Progress hook** (firma exacta):
```python
def progress_hook(bytes_downloaded: int, bytes_expected: int):
    pct = bytes_downloaded / bytes_expected * 100
    # empujá esto a la UI web por websocket/SSE o a la barra Tkinter
```

### El popup — dos opciones

**Opción 1 — Tkinter nativo** (cero dependencias extra, ya viene con Python/PyInstaller):
```python
import tkinter as tk
from tkinter import messagebox

def mostrar_popup(new_update):
    root = tk.Tk(); root.withdraw()
    changelog = (new_update.custom or {}).get('changelog', '')
    if messagebox.askyesno(
        'Actualización disponible',
        f'Hay una nueva versión ({new_update.version}).\n\n{changelog}\n\n¿Actualizar ahora?'
    ):
        # opcional: ventana con barra ttk.Progressbar alimentada por progress_hook
        client.download_and_apply_update(skip_confirmation=True, progress_hook=progress_hook)
```

**Opción 2 — modal HTML en la UI web del panel (recomendado en tu caso, ya tenés http.server en 127.0.0.1:8124).** El frontend, al cargar, hace `fetch('/api/check-update')`; si hay versión, muestra un modal HTML de marca (consistente con el panel). Al hacer click en "Actualizar", llama a `/api/apply-update`, y el progreso se muestra por SSE/websocket. Bosquejo de los endpoints en tu `ThreadingHTTPServer`:

```python
# GET /api/check-update
def handle_check_update(self):
    upd = client.check_for_updates(pre=None)
    body = {'available': bool(upd)}
    if upd:
        body.update(version=str(upd.version), changelog=(upd.custom or {}).get('changelog',''))
    self._json(body)

# POST /api/apply-update  (lanzar en un thread; el proceso se va a morir solo)
def handle_apply_update(self):
    def run():
        client.download_and_apply_update(
            skip_confirmation=True,
            progress_hook=lambda d, e: PROGRESS_BUS.publish(d, e),  # -> SSE al browser
        )
    threading.Thread(target=run, daemon=True).start()
    self._json({'started': True})
```

> Nota UX importante con la opción web: cuando `download_and_apply_update` termina hace `sys.exit(0)` → el servidor local se cae y el browser pierde conexión. Mostrá en el modal "Aplicando y reiniciando…" y reintentá el `fetch` al panel cada 1-2 s; cuando el panel vuelve (ya en la versión nueva) recargás la página. Por eso conviene que el batch **relance** el panel (ver punto 3).

---

## 3) RESTRICCIÓN WINDOWS: archivos en uso. Cómo lo resuelve tufup

El problema: en Windows no podés sobrescribir el `.exe`/DLLs mientras el proceso corre (file lock). El patrón de tufup es el clásico **"updater externo desacoplado"**:

1. tufup descomprime el archive nuevo a un **directorio temporal**.
2. Genera un **script .bat** a partir de `WIN_BATCH_TEMPLATE`:
   ```bat
   @echo off
   {log_lines}
   echo Moving app files...
   robocopy "{src_dir}" "{dst_dir}" {robocopy_options}
   echo Done.
   {delete_self}
   ```
   donde `robocopy_options` por defecto es `/e /move /v /w:2` (`/move` borra el origen tras copiar; `/w:2` reintenta cada 2 s si un archivo está bloqueado).
3. Lanza el .bat con `subprocess.Popen(..., creationflags=CREATE_NEW_CONSOLE)` (proceso **separado**, sobrevive a la muerte del padre).
4. El proceso del panel hace **`sys.exit(0)`** → libera los locks.
5. El .bat, ya con la app cerrada, hace `robocopy` y mueve los archivos nuevos sobre el `INSTALL_DIR`. `robocopy /w:2` espera/reintenta si algún archivo tarda en liberarse.
6. El .bat **se auto-borra** con el truco `(goto) 2>nul & del "%~f0"` (`{delete_self}`).

**Reinicio (relaunch).** Punto crítico que confirmé leyendo el código fuente actual: **el template por defecto NO relanza la app**. Hace robocopy y se auto-borra; el padre solo hizo `sys.exit(0)`. Para tu requisito de "REINICIAR en la versión nueva" tenés que **inyectar el relaunch vos**, y `install_update`/`download_and_apply_update` lo permiten vía kwargs:

`_install_update_win` (en `tufup/utils/platform_specific.py`) acepta:
- `batch_template` — string de template propio.
- `batch_template_extra_kwargs` — variables extra para tu template.
- `robocopy_options_override` — reemplazar opciones de robocopy.
- `process_creation_flags` — ej. `subprocess.CREATE_NO_WINDOW` para no mostrar consola negra.
- `as_admin` — eleva con UAC (`ShellExecuteW`) si el install dir requiere permisos.
- `log_file_name` — loguea el output del .bat dentro de `dst_dir`.

Template custom con relaunch (este es el patrón que recomienda el maintainer en el issue #12, "no lo probé yo mismo" pero es estándar):
```python
WIN_BATCH_RELAUNCH = (
    '@echo off\n'
    '{log_lines}\n'
    'echo Moving app files...\n'
    'robocopy "{src_dir}" "{dst_dir}" {robocopy_options}\n'
    'echo Restarting application\n'
    'start "" "{new_exe_path}"\n'   # <-- relanza la versión nueva
    '{delete_self}\n'
)

client.download_and_apply_update(
    skip_confirmation=True,
    progress_hook=progress_hook,
    # kwargs reenviados a install_update:
    batch_template=WIN_BATCH_RELAUNCH,
    batch_template_extra_kwargs={'new_exe_path': str(settings.INSTALL_DIR / 'panel.exe')},
    process_creation_flags=subprocess.CREATE_NO_WINDOW,
)
```
Así el flujo completo queda: panel corriendo → popup "Actualizar" → baja patch → cierra panel → .bat copia y **relanza `panel.exe` nuevo** → .bat se borra. Para el usuario no técnico: ve el popup, acepta, la ventana se cierra un segundo y vuelve a abrir actualizada.

> Requisito de empaquetado: usá PyInstaller en modo **onedir** (no onefile). tufup actualiza una carpeta de archivos; onefile se auto-extrae a temp y complica el reemplazo. El onedir va dentro de `INSTALL_DIR` y el `root.json` inicial se incluye como dato del bundle.

---

## 4) Flujo del DESARROLLADOR para publicar una versión (y dónde van las claves)

tufup da el módulo `tufup.repo` y una CLI (`tufup ...`). Flujo típico (basado en los scripts `repo_init.py` / `repo_add_bundle.py` de tufup-example):

1. **Una sola vez — inicializar repo y generar claves** (`tufup init` / `Repository`):
   - Genera los pares de claves de los 4 roles (root, targets, snapshot, timestamp) y la metadata inicial.
   - Crea el layout `metadata/` + `targets/` y el `root.json` que vas a embeber en el cliente.

2. **Por cada release:**
   - Bumpear `APP_VERSION` y compilar el bundle con **PyInstaller (onedir)**, incluyendo el `root.json`.
   - **Agregar el bundle al repo** (`tufup targets add <version> <bundle_dir> <key_dir>` o `Repository.add_bundle(...)`): tufup crea el `.tar.gz`, genera el `.patch` contra el archive anterior, actualiza los hashes en `targets.json`.
   - **Firmar y publicar** (`Repository.publish_changes(private_key_dirs=[...])`): re-firma `targets`/`snapshot`/`timestamp` con las claves privadas.
   - **Subir** `metadata/` y `targets/` actualizados al host estático. En tu caso: `git add/commit/push` al repo público de updates (GitHub Pages lo deploya solo) — encaja perfecto con tu pipeline actual de "push → Vercel/Pages auto-deploy".

   El paso 5 (subir) **no lo cubre tufup** ("depends on the implementation"); lo hacés vos con git push / rsync / aws s3 sync.

**Dónde se guardan las claves de firma (lo más sensible):**
- Las **privadas** se guardan **fuera del repo de updates**, en el disco del desarrollador (por defecto `~/.tufup` o el dir que le pases). **NUNCA** se commitean al repo público.
- Conviene encriptarlas con passphrase. Las de `root` y `targets` son las críticas (rotación difícil); guardalas offline/backup (gestor de contraseñas, pendrive cifrado). Las de `timestamp`/`snapshot` se usan en cada publish y pueden vivir en la máquina/CI de build.
- **Encaja con tu arquitectura "cerebro centralizado"**: las claves de firma y el push a GitHub viven en UN solo lugar (tu máquina de dev / el cerebro serverless / un GitHub Action con secrets), no repartidas en las 6 PCs. Las 6 PCs solo tienen el cliente con el `root.json` público embebido. Tu **MCP de control** puede orquestar exactamente este flujo (add_bundle → publish → push) para "publicar mejoras".

---

## 5) Alternativas

- **PyUpdater** — ❌ **descartar**. Archivado/sin mantenimiento; criptografía propia; tufup nació explícitamente para reemplazarlo.
- **Updater casero contra GitHub Releases** — el cliente consulta `api.github.com/repos/.../releases/latest`, compara `tag_name` con su versión, baja el asset, y corre un .bat de reemplazo+relaunch (mismo patrón Windows del punto 3).
  - *Pros*: cero dependencias nuevas, Releases es gratis y trivial de publicar (`gh release create`), sin lidiar con expiración de metadata TUF, control total.
  - *Contras*: **vos** implementás versionado, descarga incremental (no hay patches gratis — bajás el bundle entero siempre), reintentos, y sobre todo **seguridad/firma** a mano (sin firmas, una cuenta de GitHub comprometida = push de un .exe malicioso a las 6 PCs). Perdés toda la protección de TUF (rollback/freeze/replay).
- **Squirrel.Windows / WinSparkle / NSIS web-installer** — robustos pero pensados para apps nativas/.NET; integrarlos con un bundle PyInstaller es más fricción que tufup. No aportan ventaja en tu stack Python.
- **Servir el repo tufup desde GitHub Pages** (no es "alternativa a tufup" sino el backend gratis) — es la combinación ganadora: tufup (seguridad + patches) + GitHub Pages (hosting estático gratis).

---

## RECOMENDACIÓN

**Usar tufup, con PyInstaller en modo onedir, hospedando el repo de updates en GitHub Pages (repo público de updates), claves privadas en tu máquina/MCP, y un `batch_template` custom que relance `panel.exe`.** Cumple los 5 requisitos:

1. **Gratis**: GitHub Pages/raw sirve metadata+targets estáticos sin costo.
2. **.EXE sin Python**: tufup es agnóstico al packaging; empaquetás con PyInstaller onedir y la gente no instala nada.
3. **Centralizado**: las claves de firma y el push viven en UN solo lugar (tu dev box / cerebro / GitHub Action); las 6 PCs solo llevan el cliente + `root.json` público.
4. **Autoactualización con tu UX exacta**: `check_for_updates()` al abrir → tu popup (modal HTML en el panel web es lo más prolijo) → `download_and_apply_update()` baja **solo el `.patch`** → batch reemplaza con la app cerrada → **relanza la versión nueva**.
5. **Control del dev vía MCP**: el flujo `add_bundle → publish_changes → git push` es scripteable; tu MCP lo dispara para publicar mejoras.

**Integración mínima a implementar:**
- En el cliente: instanciar `Client` con las dos URLs de GitHub Pages; al boot, `check_for_updates`; endpoints `/api/check-update` y `/api/apply-update` en tu `http.server`; modal HTML; `batch_template` con `start "" "panel.exe"` para el relaunch.
- En el dev/MCP: `tufup init` una vez (genera claves), y por release `tufup targets add` + `publish_changes` + `git push` al repo de updates.
- Cuidados: **onedir, no onefile**; setear **expiraciones de metadata largas** (timestamp ~365 días) para no romper clientes si pasás tiempo sin publicar; **claves privadas fuera del repo**, con backup de root/targets.

**Único riesgo a vigilar**: el relaunch automático en Windows no es funcionalidad "de fábrica" — hay que armar el `batch_template` custom (es trivial, está arriba) y testearlo en una PC real, porque el maintainer mismo dice que ese patrón "no lo probó él".

### Fuentes
- [github.com/dennisvang/tufup (README)](https://github.com/dennisvang/tufup)
- [tufup en PyPI](https://pypi.org/project/tufup/)
- [github.com/dennisvang/tufup-example](https://github.com/dennisvang/tufup-example)
- [tufup-example/src/myapp/__init__.py (cliente, check/apply, progress_hook)](https://raw.githubusercontent.com/dennisvang/tufup-example/master/src/myapp/__init__.py)
- [tufup/utils/platform_specific.py (WIN_BATCH_TEMPLATE, robocopy, kwargs, relaunch)](https://raw.githubusercontent.com/dennisvang/tufup/main/src/tufup/utils/platform_specific.py)
- [Discusión #30 — servir el repo en producción como estáticos](https://github.com/dennisvang/tufup-example/discussions/30)
- [Discusión #19 / Issue #12 — relanzar la app tras update en Windows](https://github.com/dennisvang/tufup-example/discussions/19)
- [Issue #63 — soporte de GitHub Releases / S3 (no nativo)](https://github.com/dennisvang/tufup/issues/63)
- [The Update Framework (TUF)](https://theupdateframework.io/) / [python-tuf en PyPI](https://pypi.org/project/tuf/)

## Anexo 4 — MCP + seguridad + sincronización

He completado la investigación. Aquí está el informe del Investigador #4.

---

# INVESTIGADOR #4 — MCP de Control + Seguridad + Sincronización

## RESUMEN EJECUTIVO (recomendación concreta)

El modelo que recomiendo: **cliente .exe delgado (PyInstaller + Pillow + tufup-client) → "cerebro" en un Cloudflare Worker con un Durable Object (DO) único como serializador → GitHub vía fine-grained PAT**. El MCP de control corre **local en la PC del dev** (stdio), no expuesto a internet. La firma de updates usa **tufup/TUF con clave `targets` offline en la PC del dev**; el cerebro solo sirve archivos estáticos firmados (puede ser otro repo público o un bucket R2).

Por qué Cloudflare Worker + Durable Object en vez de Vercel para el cerebro: el DO te da **serialización nativa "gratis"** (single-threaded, una request a la vez, `blockConcurrencyWhile`), que es exactamente el "servidor que organiza solo" que pide el usuario; en Vercel tendrías funciones concurrentes sin estado y necesitarías inventar el locking. Ambos tienen tier gratis, pero el DO resuelve el requisito #3 de raíz.

---

## 1) MCP DE CONTROL (para el desarrollador vía Claude)

**SDK actual (2026):** Hay dos opciones compatibles:
- El **SDK oficial** `modelcontextprotocol/python-sdk` (paquete `mcp`), que ya incorporó FastMCP 1.0 internamente. Trae `FastMCP` con decoradores `@mcp.tool()`, generación de schema desde type hints, y transportes stdio/SSE/Streamable-HTTP.
- **FastMCP** standalone (`PrefectHQ/fastmcp`, hoy 3.x) — superset del oficial, ~70% de los servers Python lo usan; agrega auth (JWT/OAuth) y utilidades. Para un MCP **local del dev** no necesitás esos extras; el oficial alcanza.

**Cómo corre y se conecta a Claude:** transporte **stdio**, que es el modo para integraciones locales de escritorio (Claude Desktop / Claude Code). Se registra en el `mcp.json`/config de Claude apuntando al ejecutable. NO se expone a internet: el MCP corre como proceso hijo en la PC del dev y habla JSON-RPC 2.0 por stdin/stdout. Las credenciales sensibles (clave `targets` de TUF, admin-token del cerebro) viven en variables de entorno locales del dev, nunca en los clientes.

**Esqueleto mínimo:**
```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("mys-control")

@mcp.tool()
def publicar_version(version: str, notas: str = "") -> str:
    """Empaqueta (PyInstaller), firma con la clave targets de TUF y sube el bundle con tufup."""
    ...

if __name__ == "__main__":
    mcp.run()  # transport="stdio" por defecto
```

**Herramientas que expondría el MCP (diseño):**

| Tool | Qué hace | Notas de seguridad |
|---|---|---|
| `publicar_version(version, notas)` | Corre PyInstaller → `repo.add_bundle()` de tufup → firma `targets`/`snapshot`/`timestamp` → push del repo TUF (a R2 o repo de updates) | Usa la clave `targets` **offline** en la PC del dev. Único punto donde se firma. |
| `ver_estado()` | Llama al cerebro (admin endpoint) y devuelve: versión publicada actual, último commit a la intranet, cola de publicaciones, salud del PAT | Solo lectura |
| `listar_usuarios()` / `agregar_usuario(nombre)` / `revocar_usuario(id)` | CRUD de credenciales de equipo en el storage del DO/KV | Si usás tokens por usuario, esto los emite/revoca |
| `rotar_credencial_github()` | Reemplaza el secreto PAT en el cerebro (lo seteás como secret del Worker) y opcionalmente dispara revocación del viejo | Acción de alto privilegio; requiere admin-token |
| `rotar_password_equipo()` | Cambia la contraseña de app compartida (si elegís ese modelo) | Invalida la cred en las 6 PCs hasta que la actualicen |
| `quien_publico_ultimo()` | Devuelve `{usuario, timestamp, commit_sha}` del último push exitoso a la intranet (audit log del DO) | Auditoría |
| `historial(n)` | Últimas N publicaciones con autor/sha | Auditoría |

El MCP es un **cliente HTTP autenticado del cerebro** (con un admin-token distinto al de los editores) + ejecutor local de tufup. Claude conduce; el dev aprueba.

---

## 2) MODELO DE SEGURIDAD END-TO-END

### Credencial única de GitHub
- **Fine-grained PAT**, no classic. Apuntado a **un solo repositorio** (el de la intranet), permiso **Contents: Read and write** y nada más (de >50 permisos granulares). Con **expiración** obligatoria (ej. 90 días) → fuerza rotación. Los fine-grained tokens solo acceden a los repos explícitamente otorgados, a diferencia de los classic.
- **Dónde vive:** como **Secret del Cloudflare Worker** (`wrangler secret put`), valores no visibles en dashboard ni Wrangler tras definirlos. En Vercel sería "Sensitive environment variable" (se guarda en formato ilegible). **Nunca** en el .exe ni en las PCs. Este es el requisito #3 (credencial centralizada) cumplido.

### Auth de los clientes (editores) — recomendación
**Tokens por usuario, NO contraseña compartida.** Aunque la contraseña compartida es más simple, viola el requisito de poder "revocar usuarios" sin afectar a los demás. Modelo concreto:
- El cerebro guarda en el DO/KV una tabla `{user_id, token_hash (argon2/bcrypt), activo, nombre}`.
- El cliente guarda su token en el keychain de Windows (DPAPI / `keyring`), no en texto plano.
- Cada request al cerebro manda el token; el cerebro valida hash y `activo`.
- Revocar = poner `activo=false` (vía MCP `revocar_usuario`). Inmediato, sin tocar las otras PCs.

### Firma de updates (tufup/TUF) — dónde viven las claves
TUF separa 4 roles, lo que da resiliencia ante compromiso:
- **root**: raíz de confianza, firma las claves de los otros roles. Clave **offline**, físicamente desconectada. Va embebida (la `root.json` inicial) en el .exe al compilar.
- **targets**: firma los artefactos (tu bundle). Clave **offline en la PC del dev** — es la que usa `publicar_version`.
- **snapshot**: puede ir offline.
- **timestamp**: clave **online** (alto riesgo, expira rápido). Si querés automatizar, esta es la única que podría vivir en el servidor; para tu escala podés firmar las 3 (targets/snapshot/timestamp) en la PC del dev en cada publicación y mantener TODO offline.
- TUF soporta **threshold signatures** (N de M claves) para más resiliencia, pero para un equipo chico una clave por rol alcanza.

### THREAT MODEL y mitigaciones

| Amenaza | Qué pasa | Mitigación |
|---|---|---|
| **Se filtra un .exe** | Atacante tiene el binario + `root.json` embebido, pero **no** el PAT (está en el cerebro) ni claves de firma | El .exe sin token de usuario válido no puede publicar. Pedir login al abrir. El binario no contiene secretos. |
| **Descubren la URL del cerebro** | Endpoint expuesto | Todo endpoint exige token válido; **rate-limit** por IP/token en el Worker; el DO devuelve overloaded si lo floodean. Sin token → 401. |
| **Roban el token de un usuario** | Puede publicar como ese usuario | Revocar vía MCP (`activo=false`), inmediato. Audit log identifica qué publicó. Tokens con expiración. TLS obligatorio. |
| **Roban la contraseña de equipo** (si usaras ese modelo) | Acceso total del equipo | Razón #1 para preferir tokens por usuario. Si igual usás contraseña: `rotar_password_equipo` + re-distribuir. |
| **Update malicioso** (atacante intenta empujar un .exe troyano) | Cliente actualizaría a binario hostil | **TUF lo bloquea**: el cliente solo acepta bundles firmados por la clave `targets`, que es offline en la PC del dev. Sin esa clave no se puede forjar metadata válida. Protege también de rollback/freeze (snapshot+timestamp). |
| **Compromiso del cerebro/Worker** | Atacante ve el PAT | PAT limitado a 1 repo + contents:write (no puede borrar repo, ni tocar otros). **Rotar PAT** vía MCP. Vercel daña el deploy estático, no permite ejecutar updates (esos los firma TUF aparte). |
| **Compromiso de la PC del dev** | Atacante tiene clave `targets` → puede firmar updates | Punto más crítico. Mitigación: clave protegida con passphrase, idealmente en hardware/token; root offline permite re-emitir targets out-of-band si se compromete. |

### Puntos de seguridad NO NEGOCIABLES
1. PAT **fine-grained, 1 repo, contents:write, con expiración** — jamás classic, jamás en el cliente.
2. Secreto del PAT **solo** en el cerebro (Worker secret / Vercel sensitive env).
3. Updates **firmados con TUF**, clave `targets` **offline** en la PC del dev. El cliente verifica firma antes de reemplazar y reiniciar.
4. `root.json` embebido en el .exe; rotación de root planificada antes de su expiración.
5. **Tokens por usuario revocables**, hasheados, sobre **TLS**. Nada de credenciales compartidas si se puede evitar.
6. **Audit log** inmutable de quién publicó (en el DO).
7. **Rate-limiting** en el cerebro.

---

## 3) SINCRONIZACIÓN MULTI-USUARIO (3–6 editores, UN repo)

### El cerebro serializa (no los clientes)
Con **Durable Object único** como "cola de publicación": cada instancia procesa **una request a la vez, secuencialmente**; `blockConcurrencyWhile` garantiza orden y previene carreras. Todos los "publicar" del equipo pegan al **mismo DO id** → se forman en fila automáticamente. Esto elimina los conflictos de git de raíz: nunca hay dos commits compitiendo en el mismo instante.

### Algoritmo de commit (optimistic concurrency con SHA)
Aun serializando, el commit a GitHub debe usar el patrón SHA por robustez:

**Para un solo archivo** (Contents API `PUT /repos/.../contents/{path}`):
1. GET del archivo → SHA actual.
2. PUT con `sha` = ese valor + contenido nuevo.
3. Si GitHub responde **409 Conflict** ("is at X but expected Y"), el archivo cambió: **re-leer SHA, re-aplicar, reintentar** (backoff, 3–5 intentos).

**Para varios archivos a la vez (recomendado) — Git Data API, commit atómico:**
1. Crear **blobs** de cada archivo → SHAs.
2. Crear **tree** con base en el tree del commit padre.
3. Crear **commit** con `parents=[SHA_actual_de_la_rama]`.
4. **Update ref** (`PATCH /git/refs/heads/main`). Si el ref ya no apunta al padre esperado → reintentar desde el paso del commit padre. Todos los archivos entran en **un solo commit atómico**.

### ¿El cliente necesita "pull" antes de editar?
- Para **no pisar el trabajo de otro**: la serialización del DO + el patrón SHA-padre ya evitan que un commit destruya otro a nivel git. **No hace falta `git pull` local**: el cliente es delgado y NO tiene clon del repo (el cerebro es el único que comitea).
- Para **no editar sobre una vista vieja** (que el editor B no trabaje horas sobre una versión que A ya cambió): conviene que el cliente, **al abrir un ítem para editar, pida al cerebro el estado/contenido actual** (read-through) y, al guardar, mande el **SHA base sobre el que editó**. Si el cerebro detecta que ese ítem cambió desde entonces, devuelve "conflicto: alguien editó esto, recargá" en vez de pisarlo. Esto es optimistic concurrency a nivel aplicación, por encima del de git.

**Patrón final:** cliente lee estado fresco al abrir → edita → manda cambio + SHA base → DO serializa → cerebro hace commit atómico con SHA-padre → reintenta en 409 → registra autor en audit log → responde OK/conflicto.

---

## Fuentes

- [MCP Python SDK oficial (modelcontextprotocol/python-sdk)](https://github.com/modelcontextprotocol/python-sdk)
- [FastMCP (PrefectHQ/fastmcp)](https://github.com/PrefectHQ/fastmcp)
- [Build an MCP server — modelcontextprotocol.io](https://modelcontextprotocol.io/docs/develop/build-server)
- [tufup (dennisvang/tufup)](https://github.com/dennisvang/tufup) · [tufup docs](https://tufup.readthedocs.io/en/latest/) · [tufup-example serve in production (claves online/offline)](https://github.com/dennisvang/tufup-example/discussions/30)
- [TUF FAQ — roles y claves offline](https://theupdateframework.io/docs/faq/) · [TUF Roles and metadata](https://theupdateframework.io/docs/metadata/) · [TUF Security](https://theupdateframework.io/docs/security/)
- [Introducing fine-grained PATs — GitHub Blog](https://github.blog/security/application-security/introducing-fine-grained-personal-access-tokens-for-github/) · [Managing your PATs — GitHub Docs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) · [Permissions required for fine-grained PATs](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens)
- [Cloudflare Workers Secrets](https://developers.cloudflare.com/workers/configuration/secrets/) · [Vercel Sensitive environment variables](https://vercel.com/docs/environment-variables/sensitive-environment-variables)
- [Cloudflare Durable Objects — Rules / serialización](https://developers.cloudflare.com/durable-objects/best-practices/rules-of-durable-objects/) · [DO Limits / free plan](https://developers.cloudflare.com/durable-objects/platform/limits/)
- [GitHub 409 conflict en Contents API (community #62198)](https://github.com/orgs/community/discussions/62198)
- [Push multiple files in a single commit via Git Data API](https://siddharthav.medium.com/push-multiple-files-under-a-single-commit-through-github-api-f1a5b0b283ae) · [REST API for Git trees — GitHub Docs](https://docs.github.com/en/rest/git/trees)