# Cerebro MyS — Puesta en marcha (Fase 0 + Fase 1)

El "cerebro" es un servicio gratis en Cloudflare que guarda la ÚNICA credencial de
GitHub y publica los cambios de la intranet. Las PCs del equipo nunca tocan esa llave.

Esto se hace **una sola vez**. Tiempo estimado: ~30–45 min. Todo gratis.

---

## 1) Crear el token de GitHub (la única credencial)

1. Entrá a GitHub → tu foto (arriba a la derecha) → **Settings**.
2. Abajo de todo: **Developer settings** → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**.
3. Completá:
   - **Token name:** `cerebro-mys`
   - **Expiration:** 90 días (después se rota; te aviso cuando toque).
   - **Repository access:** *Only select repositories* → elegí **el repo de la intranet** (el que despliega Vercel).
   - **Permissions** → *Repository permissions* → **Contents: Read and write**. (Nada más.)
4. **Generate token** → **copiá el token** (empieza con `github_pat_...`). Guardalo un momento, lo vas a pegar en el paso 4.

> ⚠️ Ese token puede publicar a la intranet. No lo pegues en ningún chat ni archivo. Solo va dentro de Cloudflare (paso 4).

---

## 2) Crear la cuenta de Cloudflare e instalar la herramienta

1. Creá una cuenta gratis en https://dash.cloudflare.com/sign-up
2. Instalá Node.js (si no lo tenés): https://nodejs.org (botón "LTS").
3. Abrí una terminal en esta carpeta (`herramientas/cerebro`) y poné:
   ```
   npm install -g wrangler
   wrangler login
   ```
   Se abre el navegador → **Allow** para conectar wrangler con tu Cloudflare.

---

## 3) Poner tus datos del repo

Abrí `wrangler.toml` y reemplazá en la sección `[vars]`:
- `REPO_OWNER` = tu usuario/organización de GitHub (ej. `mueblesysillones`)
- `REPO_NAME`  = el nombre del repo de la intranet
- `REPO_BRANCH` = la rama que publica Vercel (normalmente `main`)

---

## 4) Cargar los secretos (NO van en ningún archivo)

En la terminal, dentro de `herramientas/cerebro`:

```
wrangler secret put GITHUB_TOKEN
```
Pega el token de GitHub del paso 1 y Enter.

```
wrangler secret put PUBLISH_TOKENS
```
Pega los tokens del equipo en este formato (inventá claves largas, una por persona):
```
ana:clave-larga-secreta-1,juan:clave-larga-secreta-2,vos:clave-larga-secreta-3
```
(En la Fase 4, el MCP te deja agregar/quitar personas sin hacer esto a mano.)

---

## 5) Desplegar el cerebro

```
wrangler deploy
```
Al final te da una URL tipo:
```
https://mys-cerebro.TU-SUBDOMINIO.workers.dev
```
**Guardá esa URL** — es la dirección del cerebro (la usará el panel para publicar).

---

## 6) Probar que funciona

Ping (no necesita token):
```
curl https://mys-cerebro.TU-SUBDOMINIO.workers.dev/health
```
Debe responder `{"ok":true,...}`.

Prueba de publicación real (cambia un archivo de prueba en la intranet):
```
curl -X POST https://mys-cerebro.TU-SUBDOMINIO.workers.dev/publish \
  -H "Authorization: Bearer clave-larga-secreta-3" \
  -H "Content-Type: application/json" \
  -d '{"mensaje":"prueba cerebro","archivos":[{"path":"intranet/_prueba.txt","content":"hola","encoding":"utf-8"}]}'
```
Si responde `{"ok":true,"commit":"..."}` → **funcionó**: mirá el repo en GitHub, va a estar el commit, y Vercel redeploya. (Después borrás `intranet/_prueba.txt`.)

> El `Authorization` lleva SOLO la clave de la persona (la parte DESPUÉS de los dos puntos; en `PUBLISH_TOKENS` el nombre es solo una etiqueta que el cerebro usa para el registro). En el panel esto se carga una sola vez por persona.

---

## ¿Qué sigue?

- **Fase 2:** convierto el panel para que "Publicar" le hable a esta URL (en vez de git local) y lo empaqueto como `.exe` instalable.
- **Fase 3:** autoactualización con el popup "Hay una nueva actualización".
- **Fase 4:** tu MCP para publicar versiones y administrar usuarios.

Cuando tengas la URL del cerebro andando (paso 5/6), avisame y sigo con la Fase 2.
