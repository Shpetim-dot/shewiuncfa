(() => {
  const track = (name) => { try { fetch('/api/events', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) }); } catch {} };
  track('welcome_view');
  document.querySelectorAll('[data-track]').forEach((a) => a.addEventListener('click', () => track(a.dataset.track)));
  const LABEL = { messages: 'agent messages / month', calls: 'council calls / month', research: 'deep research runs / month', uploads: 'file uploads / month', agents: 'agents of your own', mcp_servers: 'live MCP servers' };
  fetch('/api/public').then((r) => r.json()).then((info) => {
    document.getElementById('ver').textContent = 'v' + info.version;
    const box = document.getElementById('plans');
    info.plans.forEach((p) => {
      const card = document.createElement('div'); card.className = 'card';
      const b = document.createElement('b'); b.textContent = p.name; card.append(b);
      const pr = document.createElement('div'); pr.className = 'price'; pr.textContent = p.price_eur === null ? 'Custom' : p.price_eur === 0 ? '€0' : '€' + p.price_eur;
      if (p.price_eur) { const sm = document.createElement('small'); sm.textContent = ' / month'; pr.append(sm); } card.append(pr);
      const t = document.createElement('div'); t.className = 'muted'; t.textContent = p.tagline; card.append(t);
      const ul = document.createElement('ul');
      Object.keys(LABEL).forEach((k) => { const li = document.createElement('li'); const n = p.limits[k]; li.textContent = (n >= 100000 ? 'Unlimited ' : n.toLocaleString() + ' ') + LABEL[k]; ul.append(li); });
      card.append(ul); box.append(card);
    });
  }).catch(() => {});
  const form = document.getElementById('lead'), out = document.getElementById('lead-out');
  form.addEventListener('submit', async (e) => {
    e.preventDefault(); out.textContent = 'Sending…';
    const body = Object.fromEntries(new FormData(form).entries()); body.source = 'welcome';
    try {
      const r = await fetch('/api/leads', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      if (r.ok) { form.reset(); out.textContent = 'Thank you. We will reply by email.'; } else { const d = await r.json().catch(() => ({})); out.textContent = typeof d.detail === 'string' ? d.detail : 'Please check your details.'; }
    } catch { out.textContent = 'Could not send. Please try again.'; }
  });
})();
