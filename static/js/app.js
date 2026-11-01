/* Utilidades comunes: avisos, formsets en línea, confirmaciones */
function mostrarAviso(texto, error) {
  const el = document.getElementById('aviso');
  el.textContent = texto;
  el.className = 'aviso' + (error ? ' error' : '');
  el.hidden = false;
  clearTimeout(mostrarAviso._t);
  mostrarAviso._t = setTimeout(() => { el.hidden = true; }, error ? 6000 : 2500);
}

function tokenCSRF() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : '';
}

/* Formsets de Django: agregar y quitar líneas */
document.querySelectorAll('[data-formset]').forEach((cont) => {
  const prefijo = cont.dataset.formset;
  const total = document.getElementById(`id_${prefijo}-TOTAL_FORMS`);
  const plantilla = cont.querySelector('template');
  cont.querySelector('.agregar-linea').addEventListener('click', () => {
    const n = parseInt(total.value, 10);
    cont.querySelector('.lineas').insertAdjacentHTML('beforeend', plantilla.innerHTML.replace(/__prefix__/g, n));
    total.value = n + 1;
  });
  cont.addEventListener('change', (e) => {
    if (e.target.type === 'checkbox' && e.target.name.endsWith('-DELETE')) {
      e.target.closest('.linea').classList.toggle('quitada', e.target.checked);
    }
  });
});

/* Confirmaciones y motivos en formularios */
document.querySelectorAll('form[data-confirmar]').forEach((f) => {
  f.addEventListener('submit', (e) => { if (!confirm(f.dataset.confirmar)) e.preventDefault(); });
});
document.querySelectorAll('form[data-pedir-motivo]').forEach((f) => {
  f.addEventListener('submit', (e) => {
    const motivo = prompt(f.dataset.pedirMotivo);
    if (!motivo || !motivo.trim()) { e.preventDefault(); return; }
    f.querySelector('input[name=motivo]').value = motivo.trim();
  });
});
