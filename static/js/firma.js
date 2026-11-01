/* Firma digital en canvas: guarda un PNG (data URL) en el campo oculto al enviar */
(function () {
  const lienzo = document.getElementById('lienzo-firma');
  if (!lienzo) return;
  const ctx = lienzo.getContext('2d');
  const campo = document.querySelector('input[name=firma]');
  let dibujando = false;
  let hayTrazo = false;

  ctx.lineWidth = 2.5;
  ctx.lineCap = 'round';
  ctx.strokeStyle = '#2a2230';

  function punto(e) {
    const r = lienzo.getBoundingClientRect();
    return { x: (e.clientX - r.left) * (lienzo.width / r.width), y: (e.clientY - r.top) * (lienzo.height / r.height) };
  }
  lienzo.addEventListener('pointerdown', (e) => {
    dibujando = true;
    lienzo.setPointerCapture(e.pointerId);
    const p = punto(e);
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
  });
  lienzo.addEventListener('pointermove', (e) => {
    if (!dibujando) return;
    const p = punto(e);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    hayTrazo = true;
  });
  ['pointerup', 'pointercancel'].forEach((ev) => lienzo.addEventListener(ev, () => { dibujando = false; }));

  document.getElementById('limpiar-firma').addEventListener('click', () => {
    ctx.clearRect(0, 0, lienzo.width, lienzo.height);
    hayTrazo = false;
    campo.value = '';
  });
  document.getElementById('form-entrega').addEventListener('submit', () => {
    campo.value = hayTrazo ? lienzo.toDataURL('image/png') : '';
  });
})();
