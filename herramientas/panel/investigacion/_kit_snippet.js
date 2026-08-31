
/* ===================================================================
   KIT DE RECUPERACIÓN
   Genera UN archivo .html autocontenido y cifrado con la info necesaria
   para retomar el control del sistema si esta computadora se pierde.
   Se abre con doble clic en cualquier navegador: no necesita el panel,
   ni internet, ni instalar nada.
   El cifrado lo hace el navegador (WebCrypto: PBKDF2-SHA256 + AES-GCM),
   así la contraseña nunca sale de acá ni queda guardada en ningún lado.
   =================================================================== */
const KIT_ITERACIONES = 250000;

function kitB64(buf) {
  let s = '';
  new Uint8Array(buf).forEach(b => { s += String.fromCharCode(b); });
  return btoa(s);
}

async function kitCifrar(texto, clave) {
  const cod = new TextEncoder();
  const sal = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const base = await crypto.subtle.importKey('raw', cod.encode(clave), 'PBKDF2', false, ['deriveKey']);
  const k = await crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt: sal, iterations: KIT_ITERACIONES, hash: 'SHA-256' },
    base, { name: 'AES-GCM', length: 256 }, false, ['encrypt']);
  const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, k, cod.encode(texto));
  return { sal: kitB64(sal), iv: kitB64(iv), ct: kitB64(ct), iter: KIT_ITERACIONES };
}

/* El visor que se descarga. Se arma como lista de líneas (sin backticks
   adentro) para que el JavaScript del visor no se mezcle con el de acá. */
function kitVisorHTML(paquete, fecha) {
  const datos = JSON.stringify(paquete).replace(/</g, '\\u003c');
  const cierreScript = '<' + '/script>';
  return [
    '<!doctype html><html lang="es"><head><meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width,initial-scale=1">',
    '<title>Kit de recuperación - Muebles y Sillones</title><style>',
    'body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#F7F5F1;color:#2C2A26;',
    'margin:0;padding:28px 18px;line-height:1.5}',
    '.caja{max-width:820px;margin:0 auto;background:#fff;border:1px solid #E4DFD6;border-radius:16px;padding:26px 28px}',
    'h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:26px 0 8px;color:#5A5348}',
    '.sub{color:#6E6E6E;font-size:13px;margin:0 0 20px}',
    'input{font:inherit;padding:10px 12px;border:1px solid #E4DFD6;border-radius:9px;width:240px}',
    'button{font:inherit;padding:10px 18px;border:0;border-radius:9px;background:#2C2A26;color:#fff;cursor:pointer}',
    '.err{color:#B5503F;font-size:13px;margin-top:10px;min-height:18px}',
    '.dato{display:flex;gap:10px;padding:7px 0;border-bottom:1px solid #F0EDE7;font-size:14px;flex-wrap:wrap}',
    '.dato b{min-width:170px;color:#5A5348;font-weight:600}',
    '.dato span{font-family:ui-monospace,Consolas,monospace;word-break:break-all}',
    '.serv{border:1px solid #E4DFD6;border-radius:11px;padding:13px 15px;margin-bottom:10px}',
    '.serv h3{margin:0 0 5px;font-size:14px}.serv p{margin:3px 0;font-size:13px;color:#4A463F}',
    '.serv p b{color:#2C2A26}',
    'ol{padding-left:20px;font-size:14px}ol li{margin:6px 0}',
    '.aviso{background:#FBF0EC;border:1px solid #E6C9C3;border-radius:11px;padding:13px 15px;margin-top:18px;font-size:13.5px}',
    '.aviso li{margin:5px 0}.oculto{display:none}',
    '</style></head><body><div class="caja">',
    '<h1>Kit de recuperación</h1>',
    '<p class="sub">Intranet de vendedores &middot; Muebles y Sillones &middot; generado el ', fecha, '</p>',
    '<div id="login"><p>Escribí la contraseña con la que se generó este archivo.</p>',
    '<input type="password" id="p" autofocus> <button id="b">Abrir</button>',
    '<div class="err" id="e"></div></div>',
    '<div id="cont" class="oculto"></div></div>',
    '<script>var PAQ=', datos, ';',
    'function d(b){var s=atob(b),a=new Uint8Array(s.length);for(var i=0;i<s.length;i++)a[i]=s.charCodeAt(i);return a;}',
    'function fila(k,v){var x=document.createElement("div");x.className="dato";',
    'var b=document.createElement("b");b.textContent=k;var s=document.createElement("span");s.textContent=v;',
    'x.appendChild(b);x.appendChild(s);return x;}',
    'function h2(t){var e=document.createElement("h2");e.textContent=t;return e;}',
    'async function abrir(){',
    ' var e=document.getElementById("e");e.textContent="Descifrando...";',
    ' try{',
    '  var cod=new TextEncoder();',
    '  var base=await crypto.subtle.importKey("raw",cod.encode(document.getElementById("p").value),"PBKDF2",false,["deriveKey"]);',
    '  var k=await crypto.subtle.deriveKey({name:"PBKDF2",salt:d(PAQ.sal),iterations:PAQ.iter,hash:"SHA-256"},',
    '    base,{name:"AES-GCM",length:256},false,["decrypt"]);',
    '  var pt=await crypto.subtle.decrypt({name:"AES-GCM",iv:d(PAQ.iv)},k,d(PAQ.ct));',
    '  pintar(JSON.parse(new TextDecoder().decode(pt)));',
    ' }catch(x){e.textContent="Esa contraseña no es la correcta.";}',
    '}',
    'function pintar(K){',
    ' document.getElementById("login").className="oculto";',
    ' var c=document.getElementById("cont");c.className="";',
    ' c.appendChild(h2("Datos del sistema"));',
    ' [["Repositorio",K.sitio],["Rama",K.repo.rama],["Cerebro (publicador)",K.cerebro_url],',
    '  ["Clave de publicación",K.publish_token||"(sin clave cargada)"],',
    '  ["Carpeta del proyecto",K.proyecto],["Computadora",K.pc+" ("+K.rol+")"],',
    '  ["Versión del panel",String(K.version_panel)]].forEach(function(f){c.appendChild(fila(f[0],f[1]));});',
    ' c.appendChild(h2("Cuentas: qué desbloquea cada una"));',
    ' K.servicios.forEach(function(s){var x=document.createElement("div");x.className="serv";',
    '  var t=document.createElement("h3");t.textContent=s.nombre;x.appendChild(t);',
    '  [["Qué es",s.que_es],["Desbloquea",s.desbloquea],["Dónde está",s.donde],',
    '   ["Si lo perdés",s.si_lo_perdes]].forEach(function(p){',
    '    var e=document.createElement("p");var b=document.createElement("b");b.textContent=p[0]+": ";',
    '    e.appendChild(b);e.appendChild(document.createTextNode(p[1]));x.appendChild(e);});',
    '  c.appendChild(x);});',
    ' c.appendChild(h2("Cómo retomar el control, paso a paso"));',
    ' var ol=document.createElement("ol");',
    ' K.pasos.forEach(function(p){var li=document.createElement("li");',
    '  li.textContent=p.replace(/^\\d+\\.\\s*/,"").replace("<CEREBRO>",K.cerebro_url);ol.appendChild(li);});',
    ' c.appendChild(ol);',
    ' var av=document.createElement("div");av.className="aviso";',
    ' var t=document.createElement("b");t.textContent="Importante";av.appendChild(t);',
    ' var ul=document.createElement("ul");',
    ' K.avisos.forEach(function(a){var li=document.createElement("li");li.textContent=a;ul.appendChild(li);});',
    ' av.appendChild(ul);c.appendChild(av);',
    '}',
    'document.getElementById("b").onclick=abrir;',
    'document.getElementById("p").addEventListener("keydown",function(ev){if(ev.key==="Enter")abrir();});',
    cierreScript, '</body></html>',
  ].join('');
}

(function initKit() {
  const modal = $('#kitModal'); if (!modal) return;
  const abrir = () => {
    $('#kitPass').value = ''; $('#kitPass2').value = ''; $('#kitAviso').textContent = '';
    modal.hidden = false; $('#kitPass').focus();
  };
  const cerrar = () => { modal.hidden = true; };
  const btn = $('#btnKit'); if (btn) btn.onclick = abrir;
  modal.querySelectorAll('[data-cerrar-kit]').forEach(b => { b.onclick = cerrar; });

  $('#kitGenerar').onclick = async () => {
    const av = $('#kitAviso');
    const p1 = $('#kitPass').value, p2 = $('#kitPass2').value;
    av.style.color = 'var(--danger)';
    if (p1.length < 8) { av.textContent = 'Poné al menos 8 caracteres.'; return; }
    if (p1 !== p2) { av.textContent = 'Las dos contraseñas no coinciden.'; return; }
    av.style.color = 'var(--ink3)'; av.textContent = 'Generando…';
    try {
      const kit = await api('/api/kit-recuperacion', { method: 'POST' });
      const paquete = await kitCifrar(JSON.stringify(kit), p1);
      const html = kitVisorHTML(paquete, kit.generado);
      const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Kit de recuperacion MyS - ' + kit.generado.slice(0, 10).replace(/\//g, '-') + '.html';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 4000);
      cerrar();
      toast('Kit generado. Guardalo en dos lugares distintos.', 'ok');
    } catch (e) {
      av.style.color = 'var(--danger)';
      av.textContent = e.message || 'No se pudo generar el kit.';
    }
  };
})();
