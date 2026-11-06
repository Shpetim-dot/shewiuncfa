(() => {
  try { fetch('/api/events', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: 'trust_view' }) }); } catch {}
  fetch('/api/public').then((r) => r.json()).then((i) => {
    const box = document.getElementById('contact'); const c = i.security_contact || i.contact; if (!c) return;
    box.textContent = 'To report a vulnerability, write to ';
    if (/^https?:\/\//.test(c)) { const a = document.createElement('a'); a.href = c; a.rel = 'noopener noreferrer'; a.textContent = c; box.append(a); } else box.append(document.createTextNode(c));
    box.append(document.createTextNode('. We acknowledge reports within three working days.'));
  }).catch(() => {});
})();
