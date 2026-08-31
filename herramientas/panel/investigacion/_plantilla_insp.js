function plantillaInspector(bk) {
  migrarPlantilla(bk);
  const cont = insCol();
  const refrescar = () => { renderCanvas(); renderInspector(); };
  const soloCanvas = () => {
    renderCanvas();
    $('#gbDoc').querySelector(`.gb-block[data-i="${SEL}"]`)?.classList.add('is-selected');
  };

  // ---- categoría (la que define Meta al aprobarla) ----
  cont.appendChild(lbl('Categoría de la plantilla'));
  const fc = document.createElement('div'); fc.className = 'bk-row';
  Object.entries(WA_CATS).forEach(([v, n]) => {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = n;
    b.className = 'ctipo' + (bk.categoria === v ? ' sel' : '');
    b.onclick = () => { bk.categoria = v; refrescar(); };
    fc.appendChild(b);
  });
  cont.appendChild(fc);
  cont.appendChild(insNota({
    marketing: 'Promos, novedades y reactivar clientes fríos. <b>Necesita que el cliente haya aceptado recibir</b>.',
    utilidad: 'Seguimiento de algo que el cliente ya hizo: una compra, una visita agendada.',
    autenticacion: 'Solo códigos de verificación.',
  }[bk.categoria] || '', 'insp-ayuda'));

  // ---- formato ----
  cont.appendChild(lbl('Formato'));
  const ff = document.createElement('div'); ff.className = 'bk-row';
  [['simple', 'Un mensaje'], ['carrusel', 'Carrusel de tarjetas']].forEach(([v, n]) => {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = n;
    b.className = 'ctipo' + (bk.formato === v ? ' sel' : '');
    b.onclick = () => { bk.formato = v; refrescar(); };
    ff.appendChild(b);
  });
  cont.appendChild(ff);

  // ---- encabezado (solo en formato simple; el carrusel lo lleva cada tarjeta) ----
  if (bk.formato !== 'carrusel') {
    cont.appendChild(lbl('Encabezado'));
    const fe = document.createElement('div'); fe.className = 'bk-row';
    [['ninguno', 'Sin encabezado'], ['texto', 'Texto'], ['imagen', 'Imagen']].forEach(([v, n]) => {
      const b = document.createElement('button'); b.type = 'button'; b.textContent = n;
      b.className = 'ctipo' + (bk.encabezado.tipo === v ? ' sel' : '');
      b.onclick = () => { bk.encabezado.tipo = v; refrescar(); };
      fe.appendChild(b);
    });
    cont.appendChild(fe);
    if (bk.encabezado.tipo === 'texto') {
      cont.appendChild(campoContado(bk.encabezado, 'texto', 60, 'Título corto del mensaje', soloCanvas));
    } else if (bk.encabezado.tipo === 'imagen') {
      const caja = insCaja();
      const b = document.createElement('button'); b.type = 'button'; b.className = 'btn btn-ghost';
      b.textContent = bk.encabezado.src ? 'Cambiar imagen' : 'Subir imagen';
      const inp = document.createElement('input'); inp.type = 'file'; inp.accept = 'image/*'; inp.hidden = true;
      b.onclick = () => inp.click();
      inp.onchange = () => { if (inp.files[0]) subirImgPlantilla(bk.encabezado, inp.files[0]); inp.value = ''; };
      caja.append(b, inp);
      if (bk.encabezado.src) caja.appendChild(insDel(() => { bk.encabezado.src = ''; refrescar(); }));
      caja.appendChild(insNota('WhatsApp la muestra apaisada (1.91:1). Máximo 5 MB.'));
      cont.appendChild(caja);
    }
  }

  // ---- cuerpo del mensaje ----
  cont.appendChild(lbl(bk.formato === 'carrusel' ? 'Mensaje de arriba del carrusel' : 'Cuerpo del mensaje'));
  cont.appendChild(campoContado(bk, 'cuerpo', 1024,
    'Ej: {{1}}, esta semana tenemos 3 y 6 cuotas sin interés…', soloCanvas, true));
  cont.appendChild(insNota('Escribí <b>{{1}}</b>, <b>{{2}}</b>… donde el sistema tiene que poner el dato real (nombre, modelo, sucursal). Se ven resaltadas en la vista previa.', 'insp-ayuda'));

  if (bk.formato !== 'carrusel') {
    cont.appendChild(lbl('Pie (opcional)'));
    cont.appendChild(campoContado(bk, 'pie', 60, 'Ej: Respondé BAJA para no recibir más', soloCanvas));
    cont.appendChild(lbl('Botones'));
    cont.appendChild(botonesPlantilla(bk, bk.botones, 3, refrescar, soloCanvas));
  } else {
    // ---- tarjetas del carrusel ----
    cont.appendChild(lbl('Tarjetas (' + (bk.tarjetas || []).length + ')'));
    (bk.tarjetas || []).forEach((c, i) => {
      const caja = insCaja();
      caja.appendChild(insHead('Tarjeta ' + (i + 1), (bk.tarjetas.length > 2) ? () => {
        bk.tarjetas.splice(i, 1); refrescar();
      } : null));
      const b = document.createElement('button'); b.type = 'button'; b.className = 'btn btn-ghost';
      b.textContent = c.src ? 'Cambiar foto' : 'Subir foto';
      const inp = document.createElement('input'); inp.type = 'file'; inp.accept = 'image/*'; inp.hidden = true;
      b.onclick = () => inp.click();
      inp.onchange = () => { if (inp.files[0]) subirImgPlantilla(c, inp.files[0]); inp.value = ''; };
      caja.append(b, inp);
      caja.appendChild(campoContado(c, 'cuerpo', 160, 'Texto de la tarjeta…', soloCanvas, true));
      caja.appendChild(botonesPlantilla(bk, c.botones, 2, refrescar, soloCanvas));
      cont.appendChild(caja);
    });
    if ((bk.tarjetas || []).length < 10) {
      cont.appendChild(insAdd('+ Agregar tarjeta', () => {
        bk.tarjetas.push({ src: '', cuerpo: '', botones: [] }); refrescar();
      }));
    }
    cont.appendChild(insNota('Entre 2 y 10 tarjetas. <b>Todas tienen que tener lo mismo</b>: si una lleva texto o botones, todas.', 'insp-ayuda'));
  }
  return cont;
}

/* campo con contador de caracteres: los límites son los de Meta y pasarse
   hace que la plantilla no se apruebe, así que se avisa antes */
function campoContado(obj, prop, max, ph, alCambiar, multi) {
  const caja = document.createElement('div');
  caja.style.cssText = 'display:flex;flex-direction:column;gap:3px';
  const el = document.createElement(multi ? 'textarea' : 'input');
  el.className = 'insp-input'; el.placeholder = ph; el.value = obj[prop] || '';
  if (multi) el.rows = max > 300 ? 4 : 3;
  const cta = document.createElement('div'); cta.className = 'fld-note';
  cta.style.cssText = 'text-align:right;margin:0';
  const pintar = () => {
    const n = (obj[prop] || '').length;
    cta.textContent = n + ' / ' + max;
    cta.style.color = n > max ? 'var(--danger)' : 'var(--ink3)';
    cta.style.fontWeight = n > max ? '700' : '400';
  };
  el.oninput = () => { obj[prop] = el.value; pintar(); if (alCambiar) alCambiar(); };
  pintar();
  caja.append(el, cta);
  return caja;
}

/* editor de botones con los límites reales: hasta 2 de enlace y 1 de teléfono */
function botonesPlantilla(bk, lista, max, refrescar, soloCanvas) {
  const cont = insCol();
  (lista || []).forEach((b, i) => {
    const caja = insCaja();
    caja.appendChild(insHead('Botón ' + (i + 1), () => { lista.splice(i, 1); refrescar(); }));
    const fila = document.createElement('div'); fila.className = 'bk-row';
    Object.entries(WA_TIPOS_BTN).forEach(([v, n]) => {
      const t = document.createElement('button'); t.type = 'button'; t.textContent = n;
      t.className = 'ctipo' + (b.tipo === v ? ' sel' : '');
      t.onclick = () => { b.tipo = v; refrescar(); };
      fila.appendChild(t);
    });
    caja.appendChild(fila);
    caja.appendChild(campoContado(b, 'texto', 25, 'Texto del botón', soloCanvas));
    if (b.tipo === 'enlace') caja.appendChild(urlInput(b, 'url', 'https://…'));
    if (b.tipo === 'telefono') {
      const tel = document.createElement('input'); tel.className = 'insp-input';
      tel.placeholder = '+54 9 11 …'; tel.value = b.url || '';
      tel.oninput = () => { b.url = tel.value; };
      caja.appendChild(tel);
    }
    cont.appendChild(caja);
  });
  if ((lista || []).length < max) {
    cont.appendChild(insAdd('+ Agregar botón', () => { lista.push({ tipo: 'rapida', texto: '', url: '' }); refrescar(); }));
  }
  // avisos de los topes de Meta
  const enlaces = (lista || []).filter(b => b.tipo === 'enlace').length;
  const tels = (lista || []).filter(b => b.tipo === 'telefono').length;
  const avisos = [];
  if (enlaces > 2) avisos.push('WhatsApp permite <b>hasta 2 botones de enlace</b>.');
  if (tels > 1) avisos.push('WhatsApp permite <b>un solo botón de teléfono</b>.');
  if (avisos.length) {
    const n = insNota('⚠️ ' + avisos.join(' '), 'insp-ayuda');
    n.style.borderColor = '#E6C9C3'; n.style.background = '#FBF0EC';
    cont.appendChild(n);
  }
  return cont;
}

async function subirImgPlantilla(obj, file) {
  const fd = new FormData();
  fd.append('key', (det.key || $('#dTitle').value || 'modulo') + '-wa-' + Date.now());
  fd.append('file', file);
  toast('Subiendo imagen…');
  try {
    const r = await api('/api/upload-contenido', { method: 'POST', body: fd });
    obj.src = r.src; renderCanvas(); renderInspector(); toast('Imagen lista', 'ok');
  } catch (e) { toast(e.message, 'err'); }
}
