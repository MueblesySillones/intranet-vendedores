# Intranet de Vendedores — Muebles y Sillones

Guía para quien tome el mantenimiento de este sistema (persona o agente de IA).
**Este repositorio es público: nunca escribas credenciales, tokens ni claves acá.**

---

## 1. Qué es esto

Una intranet para los vendedores de las 5 sucursales de Muebles y Sillones. Entran
desde el celular, buscan material (fotos de producto, PDFs de promociones, videos,
manuales) y se lo reenvían a los clientes por WhatsApp.

La particularidad del proyecto: **quien carga el contenido no sabe programar.** Todo
el contenido se edita desde un panel de administración con interfaz visual, que
publica al sitio sin que nadie toque código. Cualquier cambio que hagas tiene que
respetar eso — si una mejora sólo se puede mantener editando código a mano, no sirve.

---

## 2. Las piezas

| Pieza | Qué es | Dónde vive |
|---|---|---|
| **Sitio** | HTML/CSS/JS sin framework, estático | `intranet/` |
| **Panel** | App de escritorio en Python, empaquetada como `.exe` | `herramientas/panel/` |
| **Cerebro** | Cloudflare Worker que recibe del panel y escribe en GitHub | `herramientas/cerebro/` |
| **Reporte de vendedores** | App aparte, con base de datos | repo `MueblesySillones/reporte-vendedores` |

**Producción:** https://intranet-vendedores.vercel.app/intranet/ — Vercel redespliega
solo con cada push a `main` (~30 s). `vercel.json` redirige `/` a `/intranet/`.

### Cómo viaja un cambio de contenido

```
Alguien edita en el Panel  →  Worker "cerebro" (Cloudflare)  →  commit a GitHub  →  Vercel  →  sitio
```

El panel **nunca tiene el token de GitHub**. El token vive sólo como secreto dentro
del Worker. El panel se autentica contra el Worker con una clave de equipo. Esto es
deliberado: mantenelo así.

El Worker sólo acepta escribir en `intranet/modulos.js`, `intranet/galerias.js` y las
carpetas `assets/` y `css/` (ver `herramientas/cerebro/src/worker.js`). Esa lista vive
en el servidor, no en el cliente, justamente para que un panel comprometido no pueda
tocar nada más.

---

## 3. Archivos que NO se editan a mano

- **`intranet/modulos.js`** — lo genera el panel. Tiene todo el contenido (módulos,
  publicaciones de la cartelera, tutoriales, ajustes). Si lo editás a mano, el próximo
  guardado del panel te lo pisa. Es un archivo de ~285 KB: no lo leas entero sin
  necesidad.
- **`intranet/galerias.js`** — lo genera `herramientas/actualizar_galerias.py` leyendo
  las carpetas de `intranet/assets/`.

Lo que sí se edita a mano es **`intranet/index.html`** (la aplicación en sí: navegación,
visor de imágenes, lógica de compartir) y los CSS de `intranet/css/`.

---

## 4. Trampas conocidas

Cada una de éstas costó un bug en producción. Leelas antes de tocar nada.

1. **La API de GitHub cachea 60 segundos.** Si leés el estado publicado por la API
   REST justo después de publicar, te devuelve lo viejo y resucitás cosas borradas.
   El panel lee el commit por `git/info/refs`, que no tiene esa demora.
2. **Publicar combina, no pisa.** Varias computadoras (central + sucursales) publican
   contra el mismo repo. `herramientas/panel/fusion.py` combina los cambios locales
   con lo que ya está publicado. No lo reemplaces por una escritura directa.
3. **Los tutoriales viven en `modulos.js`.** Una vez un cambio ahí borró todos los
   módulos. Cualquier script que reescriba ese archivo tiene que preservar el resto.
4. **El HTML de las publicaciones está guardado, no se genera al vuelo.** Cada
   publicación tiene sus `bloques` (la fuente) y un `html` ya renderizado. Si cambiás
   cómo se dibuja un bloque, hay que regenerar el `html` de las publicaciones viejas
   con un script; si no, las nuevas se ven distinto de las viejas.
5. **El panel corre desde un `.exe` compilado.** Cambiar el `.py` no alcanza: hay que
   recompilar y publicar el release, o las sucursales siguen con la versión vieja.
6. **En el celular el botón de descarga de las galerías está oculto** por CSS
   (`css/sitio.css`, dentro del `@media (max-width:640px)`). El camino real en celular
   es el visor de imagen ampliada. Si tocás la lógica de descarga, acordate de eso.
7. **No hay detección por `userAgent` en ningún lado, y está bien así.** El código
   pregunta por capacidad (`navigator.canShare`), no por marca de teléfono. No
   introduzcas sniffing de `userAgent`: el iPad moderno se reporta como Mac.

---

## 5. Trabajar en el proyecto

**Ver el sitio local:** `Ver sitio (preview).bat` (levanta un servidor con Python y
abre el navegador). Requiere Python 3.12.

**Publicar contenido:** desde el panel, no a mano.

**Publicar una versión nueva del panel:** `herramientas/panel/publicar_web3.py`.
Sube el release y actualiza `panel/version.json`, que es lo que leen las sucursales
para ofrecer el botón Actualizar.

**Documentación más profunda:** `herramientas/documentacion/LEEME-PRIMERO.md` y
`herramientas/GUIA-OTRA-COMPUTADORA.md`.

---

## 6. Accesos

Los accesos **no están en este repositorio y nunca deben estar.** El inventario
completo (qué cuentas existen, quién es dueño de cada una, qué se rompe si se pierde)
lo tiene la gerencia de Muebles y Sillones en el documento de traspaso. Pedilo por el
canal interno.

Para trabajar con un agente de IA hace falta un `.mcp.json` con los servidores MCP
oficiales de GitHub, Vercel y Supabase. **No está en este repositorio a propósito.**
Lo genera el Panel de administración: *Ajustes → Kit de recuperación*, que produce un
archivo cifrado con contraseña. Adentro viene la configuración lista para copiar, más
el inventario de accesos.

Pedile ese kit a quien administre el panel. Los servidores MCP no llevan credenciales
—cada quien se autentica con su propia cuenta—, pero para que devuelvan algo tu cuenta
tiene que estar invitada antes a la organización de GitHub, al equipo de Vercel y a la
organización de Supabase.

Hay pendientes de seguridad conocidos y documentados en el documento de traspaso.
Si vas a tomar el mantenimiento, leelos primero.
