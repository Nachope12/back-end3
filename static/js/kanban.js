/* Tablero Kanban: consume la API REST (POST /api/pedidos/<id>/cambiar_estado/) */
(function () {
  const tablero = document.querySelector('.tablero');
  if (!tablero || tablero.dataset.mover !== '1') return;
  const api = tablero.dataset.api;

  async function mover(id, estado, boton) {
    if (boton) boton.disabled = true;
    try {
      const r = await fetch(`${api}${id}/cambiar_estado/`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': tokenCSRF() },
        body: JSON.stringify({ estado }),
      });
      const datos = await r.json().catch(() => ({}));
      if (!r.ok) {
        mostrarAviso(datos.detail || 'No se pudo mover el pedido.', true);
        if (boton) boton.disabled = false;
        return;
      }
      mostrarAviso('Pedido actualizado');
      setTimeout(() => location.reload(), 350);
    } catch (e) {
      mostrarAviso('Sin conexión con el servidor.', true);
      if (boton) boton.disabled = false;
    }
  }

  tablero.addEventListener('click', (e) => {
    const b = e.target.closest('button[data-a]');
    if (!b) return;
    mover(b.closest('.tarjeta-pedido').dataset.id, b.dataset.a, b);
  });

  let arrastrado = null;
  tablero.addEventListener('dragstart', (e) => {
    const t = e.target.closest('.tarjeta-pedido');
    if (!t) return;
    arrastrado = t;
    t.classList.add('arrastrando');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', t.dataset.id);
  });
  tablero.addEventListener('dragend', () => {
    if (arrastrado) arrastrado.classList.remove('arrastrando');
    document.querySelectorAll('.columna.sobre').forEach((c) => c.classList.remove('sobre'));
    arrastrado = null;
  });
  tablero.querySelectorAll('.columna').forEach((col) => {
    col.addEventListener('dragover', (e) => { e.preventDefault(); col.classList.add('sobre'); });
    col.addEventListener('dragleave', () => col.classList.remove('sobre'));
    col.addEventListener('drop', (e) => {
      e.preventDefault();
      col.classList.remove('sobre');
      if (!arrastrado || arrastrado.dataset.estado === col.dataset.estado) return;
      mover(arrastrado.dataset.id, col.dataset.estado, null);
    });
  });
})();
