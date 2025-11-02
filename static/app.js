(function(){
  const q = document.getElementById('search');
  const cards = Array.from(document.querySelectorAll('.card'));
  function filter(){
    const term = (q.value || '').trim().toLowerCase();
    cards.forEach(c => {
      const hay = (c.dataset.name + ' ' + c.dataset.desc);
      c.style.display = hay.includes(term) ? '' : 'none';
    });
  }
  q.addEventListener('input', filter);
})();
