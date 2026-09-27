// ============================================================================
//  CEREBRO — Muebles y Sillones  (Cloudflare Worker)
//  Recibe los cambios del panel (.exe) y los comitea al repo de la intranet
//  usando la ÚNICA credencial de GitHub (vive acá como secreto, nunca en las PCs).
//  Un Durable Object serializa las publicaciones → "el servidor organiza solo",
//  sin conflictos de git aunque publiquen 6 personas a la vez.
//
//  Endpoints:
//    GET  /health    -> ping (sin auth)
//    POST /publish   -> publica un commit atómico (auth con token de usuario)
//    GET  /audit     -> últimas publicaciones (auth)
//    GET  /datos     -> los reportes de la sección Datos, compartidos (auth)
//    POST /datos     -> guarda los reportes (auth, con la versión de la que parte)
//    PUT/GET /datos/archivo/<sha256> -> una planilla subida desde una PC (auth)
//
//  Secretos (wrangler secret put):  GITHUB_TOKEN, PUBLISH_TOKENS
//  Vars (wrangler.toml):            REPO_OWNER, REPO_NAME, REPO_BRANCH
// ============================================================================

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    try {
      if (url.pathname === '/health') return json({ ok: true, ts: Date.now() });

      // --- auth: Bearer token de usuario ---
      const token = (request.headers.get('Authorization') || '').replace(/^Bearer\s+/i, '').trim();
      const usuario = identificarUsuario(token, env);
      if (!usuario) return json({ ok: false, error: 'token inválido o ausente' }, 401);

      // todo pasa por el Durable Object único (cola que serializa)
      const stub = env.BRAIN.get(env.BRAIN.idFromName('singleton'));

      if (url.pathname === '/publish' && request.method === 'POST') {
        const body = await request.json();
        if (!Array.isArray(body.archivos) || !body.archivos.length)
          return json({ ok: false, error: 'no mandaste archivos' }, 400);
        // El servidor NO confia en el cliente. Antes se aceptaba cualquier ruta:
        // con una clave valida se podia escribir un workflow de GitHub Actions o
        // el vercel.json, y Vercel lo desplegaba solo. La lista de lo que se
        // puede tocar tiene que vivir ACA, no en el panel.
        const mala = body.archivos.find(a => !rutaPermitida(a && a.path));
        if (mala) return json({ ok: false,
          error: 'ruta no permitida: ' + String(mala && mala.path).slice(0, 120) }, 400);
        if (body.archivos.length > 60)
          return json({ ok: false, error: 'demasiados archivos en un lote' }, 400);
        const res = await stub.fetch('https://brain/commit', {
          method: 'POST',
          body: JSON.stringify({ ...body, usuario }),
        });
        return new Response(await res.text(), { status: res.status, headers: { 'content-type': 'application/json' } });
      }

      if (url.pathname === '/audit') {
        const res = await stub.fetch('https://brain/audit');
        return new Response(await res.text(), { status: res.status, headers: { 'content-type': 'application/json' } });
      }

      // --- presencia -------------------------------------------------------
      // Cada panel saluda cada tanto con su clave. Responde algo que hasta ahora
      // no se podia saber: quien esta y quien no. Publicar decia quien PUBLICO,
      // que no es lo mismo: una sucursal puede estar prendida y sin novedades
      // que comunicar durante semanas.
      if (url.pathname === '/saludo' && request.method === 'POST') {
        let d = {};
        try { d = await request.json(); } catch (e) { d = {}; }
        const res = await stub.fetch('https://brain/saludo', {
          method: 'POST',
          body: JSON.stringify({ usuario, version: d.version, publica: d.publica, pc: d.pc }),
        });
        return new Response(await res.text(), { status: res.status, headers: { 'content-type': 'application/json' } });
      }

      // --- Datos compartidos (26-sep-2026) ------------------------------
      // Lo que una computadora conecta en la sección Datos (los reportes, a
      // qué sucursal va cada vendedor y los Excel subidos desde la PC) lo
      // tienen que ver TODAS, sin cargarlo de nuevo en cada una. Vive acá,
      // en el almacenamiento privado del Durable Object, y NO en el repo:
      // el repo es público y esto tiene nombres y números del equipo.
      if (url.pathname === '/datos' || url.pathname.startsWith('/datos/archivo/')) {
        const conCuerpo = request.method === 'POST' || request.method === 'PUT';
        if (conCuerpo) {
          const largo = parseInt(request.headers.get('content-length') || '0', 10);
          if (largo > MAX_ARCHIVO_DATOS) return json({ ok: false, error: 'el archivo es demasiado grande' }, 413);
        }
        const res = await stub.fetch('https://brain' + url.pathname, {
          method: request.method,
          headers: { 'x-usuario': usuario },
          body: conCuerpo ? await request.arrayBuffer() : undefined,
        });
        return new Response(res.body, { status: res.status, headers: res.headers });
      }

      // El listado completo es solo para la central: una sucursal no tiene por
      // que ver el estado de las demas.
      if (url.pathname === '/estado') {
        if (usuario !== 'central')
          return json({ ok: false, error: 'solo la central' }, 403);
        const res = await stub.fetch('https://brain/estado');
        return new Response(await res.text(), { status: res.status, headers: { 'content-type': 'application/json' } });
      }

      return json({ ok: false, error: 'ruta no encontrada' }, 404);
    } catch (e) {
      return json({ ok: false, error: String((e && e.message) || e) }, 500);
    }
  },
};

// PUBLISH_TOKENS = "ana:tok_aaa,juan:tok_bbb"  (secreto)  -> devuelve el nombre o null
function identificarUsuario(token, env) {
  if (!token) return null;
  for (const par of (env.PUBLISH_TOKENS || '').split(',')) {
    const i = par.indexOf(':');
    if (i < 0) continue;
    const nombre = par.slice(0, i).trim();
    const tok = par.slice(i + 1).trim();
    if (tok && eqConstante(tok, token)) return nombre || 'desconocido';
  }
  return null;
}

// Lo unico que se puede escribir es el CONTENIDO del sitio. Nada de workflows,
// de configuracion de despliegue ni de herramientas internas.
// Los acentos y la ñ van a proposito: `sanear()` del panel los conserva (los
// nombres de las placas los escribe una persona, no un sistema), asi que una
// lista sin ellos rechazaria "Promocion Otoño.png" y dejaria al equipo sin
// poder publicar. Probado contra los 132 archivos publicables del repo.
function rutaPermitida(p) {
  if (typeof p !== 'string' || !p) return false;
  if (p.indexOf('..') >= 0) return false;                      // salto hacia arriba
  if (p.indexOf('\\') >= 0) return false;                      // separador de Windows
  if (p.charAt(0) === '/') return false;                       // ruta absoluta
  if (p.indexOf(String.fromCharCode(0)) >= 0) return false;    // byte nulo
  return p === 'intranet/modulos.js'
      || p === 'intranet/galerias.js'
      || /^intranet\/(assets|css)\/[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ _.\-()/]+$/.test(p);
}

// comparación de tiempo constante (evita filtrar el token por tiempos de respuesta)
function eqConstante(a, b) {
  if (a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

const MAX_ARCHIVO_DATOS = 25 * 1024 * 1024;   // una planilla de 25 MB ya es enorme
const PEDAZO = 1024 * 1024;                   // el almacenamiento guarda de a 2 MB como mucho

async function sha256hex(buf) {
  const h = await crypto.subtle.digest('SHA-256', buf);
  return Array.from(new Uint8Array(h)).map(b => b.toString(16).padStart(2, '0')).join('');
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), { status, headers: { 'content-type': 'application/json' } });
}

// ============================================================================
//  Durable Object: cola única (mutex) + commit atómico a GitHub
// ============================================================================
export class Brain {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.cola = Promise.resolve();   // cadena de promesas = serializa las publicaciones
  }

  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === '/audit') {
      const log = (await this.state.storage.get('audit')) || [];
      return json({ ok: true, audit: log.slice(-50).reverse() });
    }
    if (url.pathname === '/saludo') {
      const d = await request.json();
      const vivos = (await this.state.storage.get('vivos')) || {};
      const antes = vivos[d.usuario] || {};
      const v = (d.version === undefined || d.version === null)
        ? (antes.version === undefined ? null : antes.version)
        : d.version;
      vivos[d.usuario] = {
        ts: Date.now(),
        version: v,
        publica: d.publica || antes.publica || '',
        pc: d.pc || antes.pc || '',
        // desde cuando lo venimos viendo: distingue a uno nuevo de uno que
        // vuelve despues de semanas apagado
        desde: antes.desde || Date.now(),
      };
      await this.state.storage.put('vivos', vivos);
      return json({ ok: true });
    }
    if (url.pathname === '/datos') return this.datos(request);
    if (url.pathname.startsWith('/datos/archivo/')) return this.archivo(request, url.pathname.slice(15));
    if (url.pathname === '/estado') {
      const vivos = (await this.state.storage.get('vivos')) || {};
      const log = (await this.state.storage.get('audit')) || [];
      // la ultima publicacion de cada uno, para verla al lado de la ultima senal
      const ultima = {};
      for (const e of log) if (e && e.usuario) ultima[e.usuario] = e.ts;
      const lista = Object.keys(vivos).map(function (u) {
        const x = vivos[u];
        return {
          usuario: u, ts: x.ts, version: x.version, publica: x.publica,
          pc: x.pc, desde: x.desde, ultima_publicacion: ultima[u] || null,
        };
      }).sort(function (a, b) { return b.ts - a.ts; });
      return json({ ok: true, ahora: Date.now(), paneles: lista });
    }
    // /commit  -> encolar detrás de la publicación anterior (uno a la vez)
    const body = await request.json();
    const anterior = this.cola;
    let liberar;
    this.cola = new Promise(r => (liberar = r));
    try {
      await anterior;
      const res = await this.commit(body).catch(e => ({ ok: false, error: String((e && e.message) || e) }));
      return json(res, res.ok ? 200 : (res.status || 500));
    } finally {
      liberar();
    }
  }

  // commit atómico multi-archivo con optimistic locking + reintento
  async commit(body) {
    const env = this.env;
    const { archivos, mensaje, usuario } = body;
    const owner = env.REPO_OWNER, repo = env.REPO_NAME, branch = env.REPO_BRANCH || 'main';
    const base = `/repos/${owner}/${repo}`;

    for (let intento = 1; intento <= 5; intento++) {
      // 1) ref actual de la rama -> SHA base
      const ref = await gh(env, `${base}/git/ref/heads/${branch}`);
      const baseSha = ref.object.sha;
      // 2) tree del commit base (para preservar todo lo demás)
      const baseCommit = await gh(env, `${base}/git/commits/${baseSha}`);
      // 3) un blob por archivo (texto utf-8 o imagen base64)
      const items = [];
      for (const a of archivos) {
        const blob = await gh(env, `${base}/git/blobs`, 'POST', {
          content: a.content,
          encoding: a.encoding === 'base64' ? 'base64' : 'utf-8',
        });
        items.push({ path: a.path, mode: '100644', type: 'blob', sha: blob.sha });
      }
      // 4) tree nuevo sobre el base (solo cambia lo tocado)
      const tree = await gh(env, `${base}/git/trees`, 'POST', { base_tree: baseCommit.tree.sha, tree: items });
      // 5) commit
      const commit = await gh(env, `${base}/git/commits`, 'POST', {
        message: (mensaje || 'Actualización desde el panel') + `\n\nPublicado por: ${usuario || '?'}`,
        tree: tree.sha,
        parents: [baseSha],
      });
      // 6) mover la rama (force:false -> 422 si alguien publicó en el medio)
      const patch = await ghRaw(env, `${base}/git/refs/heads/${branch}`, 'PATCH', { sha: commit.sha, force: false });
      if (patch.ok) {
        await this.registrar(usuario, commit.sha, mensaje);
        return { ok: true, commit: commit.sha };
      }
      if (patch.status === 422) continue;            // conflicto -> reintentar sobre la base nueva
      return { ok: false, status: patch.status, error: 'GitHub rechazó el push: ' + (await patch.text()) };
    }
    return { ok: false, error: 'conflicto persistente tras 5 intentos, probá de nuevo' };
  }

  /* ---- Datos compartidos ------------------------------------------------
     Un solo documento con versión. Guardar exige decir de qué versión se
     parte: si otra computadora guardó en el medio, se contesta 409 con lo
     nuevo y el panel combina antes de volver a intentar. Así dos PCs que
     guardan a la vez no se pisan. */
  async datos(request) {
    const vacio = { version: 0, ts: 0, por: '', reportes: [], vendedores: {} };
    const actual = (await this.state.storage.get('datos:doc')) || vacio;
    if (request.method === 'GET') return json({ ok: true, doc: actual });
    if (request.method !== 'POST') return json({ ok: false, error: 'método no permitido' }, 405);
    let d;
    try { d = JSON.parse(new TextDecoder().decode(await request.arrayBuffer())); }
    catch (e) { return json({ ok: false, error: 'no entendí lo que mandaste' }, 400); }
    if ((d.base | 0) !== actual.version)
      return json({ ok: false, conflicto: true, doc: actual }, 409);
    const reportes = Array.isArray(d.reportes) ? d.reportes.slice(0, 40) : [];
    const vendedores = (d.vendedores && typeof d.vendedores === 'object') ? d.vendedores : {};
    const nuevo = { version: actual.version + 1, ts: Date.now(),
                    por: request.headers.get('x-usuario') || '', reportes, vendedores };
    if (JSON.stringify(nuevo).length > 1800000)
      return json({ ok: false, error: 'los reportes ocupan demasiado' }, 413);
    await this.state.storage.put('datos:doc', nuevo);
    await this.barrerArchivos(reportes);
    return json({ ok: true, doc: nuevo });
  }

  // Las planillas se guardan por su huella (sha256): la misma no se sube dos
  // veces, y lo que se baja es exactamente lo que se subió.
  async archivo(request, sha) {
    if (!/^[0-9a-f]{64}$/.test(sha)) return json({ ok: false, error: 'huella inválida' }, 400);
    const st = this.state.storage;
    const meta = await st.get('datos:meta:' + sha);
    if (request.method === 'GET') {
      if (!meta) return json({ ok: false, error: 'no está' }, 404);
      const claves = [];
      for (let i = 0; i < meta.partes; i++) claves.push('datos:arch:' + sha + ':' + i);
      const trozos = await st.get(claves);
      const out = new Uint8Array(meta.size);
      let pos = 0;
      for (const k of claves) {
        const t = trozos.get(k);
        if (!t) return json({ ok: false, error: 'archivo incompleto' }, 500);
        out.set(new Uint8Array(t), pos); pos += t.byteLength;
      }
      return new Response(out, { headers: { 'content-type': 'application/octet-stream' } });
    }
    if (request.method !== 'PUT') return json({ ok: false, error: 'método no permitido' }, 405);
    if (meta) return json({ ok: true, ya: true });
    const buf = await request.arrayBuffer();
    if (!buf.byteLength || buf.byteLength > MAX_ARCHIVO_DATOS)
      return json({ ok: false, error: 'tamaño inválido' }, 400);
    if ((await sha256hex(buf)) !== sha)
      return json({ ok: false, error: 'el archivo llegó dañado, probá de nuevo' }, 400);
    const partes = Math.ceil(buf.byteLength / PEDAZO);
    for (let i = 0; i < partes; i++) {
      await st.put('datos:arch:' + sha + ':' + i, buf.slice(i * PEDAZO, (i + 1) * PEDAZO));
    }
    await st.put('datos:meta:' + sha, { size: buf.byteLength, partes, ts: Date.now() });
    return json({ ok: true });
  }

  // Borra las planillas que ya no usa ningún reporte. Se les da un día de
  // gracia: una PC sube el archivo ANTES de guardar el reporte que lo usa.
  async barrerArchivos(reportes) {
    const usadas = new Set();
    for (const r of reportes) {
      const c = r && r.fuente && r.fuente.compartido;
      if (c && c.sha) usadas.add(c.sha);
    }
    const st = this.state.storage;
    const metas = await st.list({ prefix: 'datos:meta:' });
    const viejo = Date.now() - 24 * 3600 * 1000;
    for (const [k, v] of metas) {
      const sha = k.slice(11);
      if (usadas.has(sha) || !v || v.ts > viejo) continue;
      const claves = [k];
      for (let i = 0; i < v.partes; i++) claves.push('datos:arch:' + sha + ':' + i);
      await st.delete(claves);
    }
  }

  async registrar(usuario, sha, mensaje) {
    const log = (await this.state.storage.get('audit')) || [];
    log.push({ usuario, sha, mensaje: mensaje || '', ts: Date.now() });
    await this.state.storage.put('audit', log.slice(-200));
  }
}

// ---- helpers GitHub REST (Git Data API) ----
async function gh(env, path, method = 'GET', body) {
  const r = await ghRaw(env, path, method, body);
  if (r.ok) return r.json();
  throw new Error(`GitHub ${method} ${path} -> ${r.status}: ${await r.text()}`);
}
function ghRaw(env, path, method = 'GET', body) {
  return fetch('https://api.github.com' + path, {
    method,
    headers: {
      'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'mys-cerebro',
      ...(body ? { 'content-type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
}
