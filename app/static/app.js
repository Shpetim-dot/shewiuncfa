(() => {
  const root = document.getElementById('app');
  const NS = 'http://www.w3.org/2000/svg';
  const G = {
    compass: '<circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2 5-5 2 2-5z"/>', lens: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
    wrench: '<path d="M4 20l9-9"/><path d="M12 6l5-3 4 4-3 5-3-3z"/>', scales: '<path d="M12 4v16M6 20h12M5 8h14"/><path d="M5 8l-3 7a3 3 0 0 0 6 0zM19 8l-3 7a3 3 0 0 0 6 0z"/>',
    coins: '<ellipse cx="12" cy="7" rx="7" ry="3"/><path d="M5 7v5c0 1.7 3 3 7 3s7-1.3 7-3V7M5 12v5c0 1.7 3 3 7 3s7-1.3 7-3v-5"/>',
    shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>', book: '<path d="M5 4h10a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z"/><path d="M5 17a3 3 0 0 1 3-3h10"/>',
    chat: '<path d="M4 5h16v11H9l-5 4z"/>', spark: '<path d="M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z"/>', menu: '<path d="M4 7h16M4 12h16M4 17h16"/>', plus: '<path d="M12 5v14M5 12h14"/>',
    graph: '<circle cx="6" cy="7" r="2.2"/><circle cx="18" cy="6" r="2.2"/><circle cx="12" cy="18" r="2.2"/><path d="M8 8l8-1M7 9l4 7M17 8l-4 8"/>',
    council: '<circle cx="8" cy="9" r="3"/><circle cx="17" cy="10" r="2.5"/><path d="M3 20c0-3 2.5-5 5-5s5 2 5 5M14 20c0-2 1.5-4 3.5-4s3.5 2 3.5 4"/>',
    grid: '<rect x="4" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.5"/>',
    flask: '<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3"/>', doc: '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M10 12h5M10 16h5"/>',
    x: '<path d="M6 6l12 12M18 6L6 18"/>', up: '<path d="M12 19V6M6 11l6-6 6 6"/>', panel: '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M15 4.5v15"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>', user: '<circle cx="12" cy="8" r="3.5"/><path d="M5 20c0-4 3-6 7-6s7 2 7 6"/>',
    teams: '<rect x="3" y="4" width="8" height="7" rx="2"/><rect x="13" y="4" width="8" height="7" rx="2"/><rect x="8" y="14" width="8" height="7" rx="2"/>', store: '<path d="M4 9l2-5h12l2 5"/><path d="M5 9v11h14V9"/><path d="M9 20v-6h6v6"/>',
    pen: '<path d="M4 20l1-4 11-11 3 3L8 19z"/><path d="M14 7l3 3"/>', rocket: '<path d="M12 3c3 2 5 5 5 9l-2 3H9l-2-3c0-4 2-7 5-9z"/><path d="M9 15l-3 4 4-1M15 15l3 4-4-1"/>', chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    terminal: '<path d="M4 5h16v14H4z"/><path d="M8 10l3 2-3 2M13 15h4"/>', bug: '<path d="M9 9a3 3 0 0 1 6 0v6a3 3 0 0 1-6 0z"/><path d="M5 10l4 1M19 10l-4 1M5 16l4-1M19 16l-4-1M12 9V4"/>', radar: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><path d="M12 12l6-5"/>',
    table: '<rect x="3.5" y="5" width="17" height="14" rx="2"/><path d="M3.5 10h17M9 10v9"/>', check: '<path d="M5 12l4 4 10-10"/>',
  };
  const KIND = { rule: 'shield', fact: 'book', decision: 'scales', lesson: 'compass', chat: 'chat', hypothesis: 'lens', note: 'doc' };
  const SPACE_COLOR = (s) => (s === 'shared' ? '#8FB1FF' : s === 'finance' ? '#4FC3D9' : (s || '').startsWith('team:') ? '#6EE7B7' : '#F4B860');
  const S = { usage: { models: [], by_kind: {}, budget: { monthly_cap: null, spent_this_month_known_cost: 0 }, note: 'Loading…', cost_is_partial: false, fallback_models: [] }, provs: [], prices: [], cu: { status: 'unconfigured', problems: [], note: '' }, invSum: null, pnew: { id: '', base_url: '', api_key: '' }, ptest: {}, pr: { provider: '', model: '', input_per_mtok: '', output_per_mtok: '', source: '' }, fb: '', cap: '', chans: {}, chan: null, cmsgs: [], cdraft: '', cbusy: '', invEdit: null, bs: { q: '', res: null }, view: 'chat', bots: [], bot: null, msgs: [], health: {}, drawer: false, menu: false, modal: null, panel: true, tab: 'overview', draft: '', busy: false,
    notes: [], note: null, versions: [], edit: false, q: '', filter: '', space: '', graph: true, graphAgent: '', newNote: false, activity: [], seen: new Set(), pulse: {}, actSince: '',
    calls: [], room: null, topic: '', picked: null, rounds: 1, planDone: {}, approvals: [], audit: [], policies: [], test: null, demo: null, verify: '', toolCalls: [], auth: false, tokenErr: '', bill: null, onb: null, presets: [], upsell: null, models: null, keys: null, newKey: null, backups: [], ready: null, leads: [], funnel: null, lead: { name: '', email: '', company: '', message: '' }, mtest: { model: '', out: '' }, ret: 90, skipOnb: false, sum: {}, cov: null, panicArm: false, menuQ: '', screen: { bot: '', events: [], ctrl: null, seen: new Set() },
    apps: [], appQ: '', appCat: 'All', appOpen: null, mcp: { name: '', url: '', token: '' }, tcall: { bot: '', tool: '', args: '{}', out: '' }, tmpl: [], caps: [],
    ag: { template: 'finance-analyst', name: '', team: '', icon: '', color: '' }, teams: [], tnew: { name: '', mission: '', members: [] }, inv: [], invQ: '', invRisk: '',
    market: [], mtab: 'curated', mname: {}, hfq: '', hf: [], hfname: {}, card: '', cardname: '', rq: '', rctx: '', rdepth: 'standard', rweb: false, rs: null, rlist: [], skip: false, err: '', info: '' };
  let token = sessionStorage.getItem('cfa_token') || '', hover = null, sim = null, actTimer = null;

  const h = (tag, a = {}, ...kids) => {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(a)) {
      if (k === 'class') el.className = v; else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else if (v === true) el.setAttribute(k, ''); else if (v !== false && v != null) el.setAttribute(k, v);
    }
    for (const kid of kids.flat(Infinity)) if (kid != null && kid !== false) el.append(kid);
    return el;
  };
  const btn = (t, f, cls = 'btn', x = {}) => h('button', { class: cls, type: 'button', onclick: f, ...x }, t);
  const icon = (n, s = 18) => { const v = document.createElementNS(NS, 'svg'); for (const [k, x] of Object.entries({ viewBox: '0 0 24 24', width: s, height: s, fill: 'none', stroke: 'currentColor', 'stroke-width': 1.8, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true' })) v.setAttribute(k, x); v.innerHTML = G[n] || G.spark; return v; };
  const col = (c) => (/^#[0-9a-f]{6}$/i.test(c || '') ? c : '#12294F');
  let gid = 0;
  const mix = (hex, a) => { const n = parseInt(col(hex).slice(1), 16), c = [n >> 16, (n >> 8) & 255, n & 255].map((v) => Math.round(a < 0 ? v * (1 + a) : v + (255 - v) * a)); return '#' + c.map((v) => v.toString(16).padStart(2, '0')).join(''); };
  // ---------- face avatars: flat, hand-built SVG. Every agent gets its own colours, ring pattern and face. ----------
  const INK = '#1B2433';
  const hsl = (hex) => { const n = parseInt(col(hex).slice(1), 16), r = (n >> 16) / 255, g = ((n >> 8) & 255) / 255, bl = (n & 255) / 255, mx = Math.max(r, g, bl), mn = Math.min(r, g, bl), l = (mx + mn) / 2; let hh = 0, sa = 0;
    if (mx !== mn) { const d = mx - mn; sa = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn); hh = mx === r ? (g - bl) / d + (g < bl ? 6 : 0) : mx === g ? (bl - r) / d + 2 : (r - g) / d + 4; hh *= 60; } return [hh, sa, l]; };
  const fromHsl = (hh, sa, l) => { const k = sa * Math.min(l, 1 - l), f = (n) => { const q = (n + hh / 30) % 12; return Math.round(255 * (l - k * Math.max(-1, Math.min(q - 3, 9 - q, 1)))); }; return '#' + [f(0), f(8), f(4)].map((v) => v.toString(16).padStart(2, '0')).join(''); };
  const EYES = {
    dot: '<circle cx="18" cy="22" r="2.5"/><circle cx="30" cy="22" r="2.5"/>',
    wide: '<circle cx="18" cy="22" r="3.3"/><circle cx="30" cy="22" r="3.3"/><circle cx="19" cy="21" r="1" fill="#FBFAF4"/><circle cx="31" cy="21" r="1" fill="#FBFAF4"/>',
    tall: '<ellipse cx="18" cy="22" rx="2.1" ry="3.4"/><ellipse cx="30" cy="22" rx="2.1" ry="3.4"/>',
    happy: '<path d="M15 23.5q3-4 6 0M27 23.5q3-4 6 0" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>',
    calm: '<path d="M15.5 22.5h5M27.5 22.5h5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>',
    wink: '<circle cx="18" cy="22" r="2.6"/><path d="M27 23.5q3-4 6 0" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>',
  };
  const BROWS = {
    none: '', raise: '<path d="M14.5 16q3.5-3 7-.5M27 17.2h6.5" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>',
    slant: '<path d="M14.5 16.5l6.5 2.2M33.5 16.5l-6.5 2.2" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>',
    soft: '<path d="M14.5 17.5q3.5-2.5 7 0M26.5 17.5q3.5-2.5 7 0" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>',
  };
  const MOUTHS = {
    smile: '<path d="M19 29.5q5 4.5 10 0" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>',
    flat: '<path d="M20 31h8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>',
    smirk: '<path d="M19.5 31q5 2.6 9.5-2.4" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>',
    open: '<ellipse cx="24" cy="31" rx="2.7" ry="2.3"/>',
    dot: '<circle cx="24" cy="30.5" r="2.1"/>',
    grin: '<path d="M18.5 29q5.5 8 11 0z"/>',
  };
  const ARCS = [['t'], ['t', 'b'], ['l', 'r'], ['t', 'l'], ['r', 'b'], ['t', 'r']];
  const ARC_ANGLES = { t: [238, 302], r: [-38, 38], b: [58, 122], l: [142, 218] };
  const CORE_FACE = {
    strategist: { ring: ['#3B6FE0', '#F2A93B'], arcs: 0, eyes: 'dot', brow: 'none', mouth: 'smile' },
    skeptic: { ring: ['#E5484D', '#2B3A67'], arcs: 2, eyes: 'dot', brow: 'raise', mouth: 'flat' },
    builder: { ring: ['#16A37F', '#F2A93B'], arcs: 3, eyes: 'wide', brow: 'slant', mouth: 'smirk' },
    chair: { ring: ['#7A4E9C', '#3B6FE0'], arcs: 0, eyes: 'dot', brow: 'none', mouth: 'dot' },
  };
  const hashOf = (str) => { let x = 7; for (const ch of String(str)) x = (x * 31 + ch.charCodeAt(0)) >>> 0; return x; };
  const pickKey = (o, n) => { const k = Object.keys(o); return k[n % k.length]; };
  function faceOf(b) {
    const key = (b && (b.id || b.name)) || 'x', core = CORE_FACE[key]; if (core) return core;
    const x = hashOf(key), [hh, sa] = hsl(b && b.color), hue = (hh + 120 + (x % 90)) % 360;
    return { ring: [fromHsl(hh, Math.max(0.55, Math.min(sa, 0.8)), 0.55), fromHsl(hue, 0.6, 0.5)], arcs: x % ARCS.length, eyes: pickKey(EYES, x >> 3), brow: pickKey(BROWS, x >> 6), mouth: pickKey(MOUTHS, x >> 9) };
  }
  const arcPath = (n, r = 18) => { const [a0, a1] = ARC_ANGLES[n], pt = (a) => `${(24 + r * Math.cos((a * Math.PI) / 180)).toFixed(2)} ${(24 + r * Math.sin((a * Math.PI) / 180)).toFixed(2)}`; return `M${pt(a0)}A${r} ${r} 0 0 1 ${pt(a1)}`; };
  // state: o.thinking = the agent is working or answering (eyes look around, mouth talks, ring turns); idle faces blink now and then.
  function tile(b, s = 40, o = {}) {
    const f = faceOf(b || {}), on = ARCS[f.arcs];
    const ring = Object.keys(ARC_ANGLES).map((n) => `<path d="${arcPath(n)}" fill="none" stroke="${on.includes(n) ? f.ring[0] : f.ring[1]}" stroke-width="3.6" stroke-linecap="round"/>`).join('');
    const v = document.createElementNS(NS, 'svg'); v.setAttribute('viewBox', '0 0 48 48'); v.setAttribute('width', s); v.setAttribute('height', s); v.setAttribute('aria-hidden', 'true');
    v.setAttribute('class', 'av' + (o.float ? ' float' : '') + (o.thinking ? ' thinking' : ''));
    v.style.setProperty('--bd', `-${(Math.random() * 5).toFixed(1)}s`);
    v.innerHTML = '<circle class="halo" cx="24" cy="24" r="22" fill="none" stroke="var(--accent)" stroke-width="2"/>'
      + '<rect x="2" y="2" width="44" height="44" rx="14" fill="#FBFAF4" stroke="rgba(15,23,42,.14)"/>'
      + `<g class="ring">${ring}</g>`
      + `<g class="face" fill="${INK}" color="${INK}"><g class="look"><g class="blink">${EYES[f.eyes] || EYES.dot}</g></g>${BROWS[f.brow] || ''}<g class="mouth m-${f.mouth}">${MOUTHS[f.mouth] || MOUTHS.smile}</g></g>`;
    return h('span', { class: 'avatar', style: `width:${s}px;height:${s}px` }, v);
  }
  const when = (t) => (t || '').slice(0, 16).replace('T', ' ');
  const botBy = (id) => S.bots.find((b) => b.id === id) || { color: '#5B6B88', icon: 'spark', name: id };
  const admin = (t) => h('p', { class: 'muted', style: 'font-size:12px' }, t);
  const dl = async (path, name) => { const r = await fetch(path, { headers: token ? { Authorization: 'Bearer ' + token } : {}, credentials: 'same-origin' }); if (!r.ok) throw new Error(`Download failed (${r.status})`); h('a', { href: URL.createObjectURL(await r.blob()), download: name }).click(); };

  // Session cookie auth needs a CSRF header; bearer tokens do not. Both are supported.
  const cookie = (n) => { const m = document.cookie.match(new RegExp('(?:^|; )' + n + '=([^;]*)')); return m ? m[1] : ''; };
  const authHeaders = (method) => {
    const hd = { 'Content-Type': 'application/json' };
    if (token) hd.Authorization = 'Bearer ' + token;
    if (method && method !== 'GET') { const c = cookie('cfa_csrf'); if (c) hd['X-CSRF-Token'] = c; }
    return hd;
  };
  const fail = async (r) => {
    if (r.status === 401) { S.auth = true; throw new Error('Sign-in required'); }
    let d = ''; try { d = (await r.json()).detail; } catch {}
    if (d && typeof d === 'object' && d.code === 'limit_reached') { S.upsell = d; throw new Error(d.message); }
    throw new Error(typeof d === 'string' && d ? d : `Request failed (${r.status})`);
  };

  async function api(path, opt = {}) {
    const method = opt.method || 'GET';
    const r = await fetch(path, { method, headers: authHeaders(method), credentials: 'same-origin', body: opt.body ? JSON.stringify(opt.body) : undefined });
    if (!r.ok) await fail(r);
    return r.json();
  }
  async function stream(path, body, onEv) {
    const r = await fetch(path, { method: 'POST', headers: authHeaders('POST'), credentials: 'same-origin', body: JSON.stringify(body) });
    if (!r.ok) await fail(r);
    const rd = r.body.getReader(), dec = new TextDecoder(); let buf = '';
    for (;;) {
      const { done, value } = await rd.read(); if (done) break; buf += dec.decode(value, { stream: true });
      let i; while ((i = buf.indexOf('\n\n')) >= 0) { const chunk = buf.slice(0, i); buf = buf.slice(i + 2); const line = chunk.split('\n').find((l) => l.startsWith('data: ')); if (line) onEv(JSON.parse(line.slice(6))); }
    }
  }
  const run = async (f) => { S.err = ''; try { await f(); } catch (e) { S.err = e.message; if (S.upsell) { S.modal = 'upsell'; S.err = ''; } } render(); };
  const loadBots = async () => { S.bots = await api('/api/bots'); if (S.bot) S.bot = S.bots.find((b) => b.id === S.bot.id) || S.bots[0]; };
  const loadNotes = async () => { S.notes = await api('/api/brain/notes'); };
  const loadApps = async () => { S.apps = await api('/api/apps'); };
  const loadTeams = async () => { S.teams = await api('/api/teams'); };

  // ---------- navigation ----------
  const stopSim = () => { if (sim && sim.raf) cancelAnimationFrame(sim.raf); sim = null; };
  const stopAct = () => { if (actTimer) clearInterval(actTimer); actTimer = null; };
  async function go(view) {
    stopAct(); S.view = view; S.drawer = false; S.menu = false; S.err = ''; S.info = ''; if (view !== 'council') S.room = null; render();
    await run(async () => {
      if (view === 'brain') { await loadNotes(); await loadBots(); S.graph = S.notes.length > 0; if (!S.note && S.notes[0]) await openNote(S.notes[0].id, true); S.actSince = (await api('/api/brain/activity?since=9999')).now; actTimer = setInterval(pollAct, 2500); }
      if (view === 'council') S.calls = await api('/api/calls');
      if (view === 'research') S.rlist = await api('/api/research');
      if (view === 'teams') { await Promise.all([loadTeams(), loadBots()]); }
      if (view === 'plans') S.bill = await api('/api/billing');
      if (view === 'settings') { for (const [k, u] of [['models', '/api/models'], ['keys', '/api/admin/keys'], ['backups', '/api/admin/backups']]) { try { S[k] = await api(u); } catch (e) { S.err = e.message; } } try { S.ready = await (await fetch('/api/health/ready')).json(); } catch {} }
      if (view === 'control') { try { S.leads = await api('/api/leads'); S.funnel = await api('/api/events/summary'); } catch {} }
      if (view === 'inventory') { S.inv = await api('/api/inventory'); S.invSum = await api('/api/inventory/summary'); }
      if (view === 'usage') { [S.usage, S.provs, S.prices, S.cu] = await Promise.all([api('/api/usage'), api('/api/providers'), api('/api/prices'), api('/api/computer-use/status')]); }
      if (view === 'market') S.market = (await api('/api/marketplace')).curated;
      if (view === 'control') [S.approvals, S.audit, S.policies, S.test, S.toolCalls, S.cov, S.sum] = await Promise.all([api('/api/security/approvals'), api('/api/security/audit?limit=15').then((d) => d.events || []), api('/api/security/policies').then((d) => d.policies), api('/api/selftest/latest'), api('/api/tool-calls'), api('/api/coverage'), api('/api/summary')]);
    });
  }
  async function pick(id) {
    stopAct(); S.bot = S.bots.find((b) => b.id === id); S.view = 'chat'; S.drawer = false; S.menu = false; S.room = null; render();
    await run(async () => { S.msgs = await api(`/api/bots/${id}/messages`); if (!S.notes.length) await loadNotes(); if (!S.apps.length) await loadApps(); });
  }
  async function openNote(id, quiet) {
    if (S.view !== 'brain') { stopAct(); S.view = 'brain'; S.actSince = (await api('/api/brain/activity?since=9999')).now; actTimer = setInterval(pollAct, 2500); }
    S.drawer = false; S.newNote = false; S.edit = false;
    const f = async () => { if (!S.notes.length) await loadNotes(); S.note = await api('/api/brain/notes/' + id); S.versions = await api(`/api/brain/notes/${id}/versions`); };
    if (quiet) await f(); else await run(f);
  }
  async function pollAct() {
    if (S.view !== 'brain') return stopAct();
    try {
      const d = await api('/api/brain/activity?since=' + encodeURIComponent(S.actSince)); S.actSince = d.now; let fresh = false;
      for (const e of d.events.reverse()) { if (S.seen.has(e.id)) continue; S.seen.add(e.id); S.activity.unshift(e); S.pulse[e.note_id] = Date.now() + 6000; fresh = true; }
      S.activity = S.activity.slice(0, 30); if (fresh) { updateTicker(); kick(); }
    } catch {}
  }
  function updateTicker() { const t = document.getElementById('ticker'); if (t) t.replaceChildren(...S.activity.slice(0, 6).map((e) => h('div', {}, `${when(e.ts)} · ${e.bot || 'someone'} ${e.kind === 'read' ? 'read' : 'wrote'} "${e.title || 'a note'}"`))); }
  async function send() {
    const text = S.draft.trim(); if (!text || S.busy) return;
    S.draft = ''; S.busy = true; S.msgs.push({ role: 'user', content: text }); render();
    await run(async () => { try { const r = await api(`/api/bots/${S.bot.id}/messages`, { method: 'POST', body: { content: text } }); S.msgs.push({ role: 'agent', content: r.reply, note: r.draft_note_id, used: r.used }); } finally { S.busy = false; } });
  }
  async function loadDemo() { await run(async () => { const r = await api('/api/demo/workspace', { method: 'POST' }); await Promise.all([loadBots(), loadNotes(), loadApps(), loadTeams()]); S.menu = false; S.info = `Demo workspace loaded: ${r.agents} agents, ${r.notes} notes, 2 teams, 3 apps. All of it is sample data.`; }); }

  // ---------- chat ----------
  function checklist() {
    const items = [['Load the demo workspace', S.bots.length > 4, loadDemo, 'Load'], ['Run a council call', S.calls.length > 0, () => go('council'), 'Open'], ['Run the authorization self-test', !!(S.test && S.test.id), () => go('control'), 'Open'],
      ['Connect an app or MCP server', S.apps.some((a) => a.connected), openApps, 'Open'], ['Create a team', S.teams.length > 0, () => go('teams'), 'Open']];
    if (items.every((i) => i[1]) || S.skip) return null;
    return h('div', { class: 'card', style: 'margin-bottom:16px' }, h('div', { class: 'row2' }, h('b', { style: 'flex:1' }, `Getting started: ${items.filter((i) => i[1]).length} of ${items.length}`), btn('Hide', () => { S.skip = true; render(); }, 'link')),
      items.map(([t, done, f, l]) => h('div', { class: 'check' + (done ? ' done' : '') }, h('span', { class: 'tick' }, done ? icon('check', 14) : null), h('span', { style: 'flex:1' }, t), done ? null : btn(l, f, 'btn'))));
  }
  function chatView() {
    const b = S.bot; if (!b) return h('div', { class: 'body' }, h('p', { class: 'empty muted' }, 'Choose an agent.'));
    const ta = h('textarea', { rows: 1, placeholder: `Message ${b.name}`, 'aria-label': `Message ${b.name}` }); ta.value = S.draft;
    const sb = h('button', { class: 'send', type: 'button', 'aria-label': 'Send', disabled: !S.draft.trim() || S.busy, onclick: send }, icon('up', 18));
    ta.addEventListener('input', () => { S.draft = ta.value; sb.disabled = !ta.value.trim() || S.busy; ta.style.height = 'auto'; ta.style.height = ta.scrollHeight + 'px'; });
    ta.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } });
    return h('div', { style: 'display:flex;flex-direction:column;min-height:0;flex:1' },
      h('div', { class: 'bar' }, tile(b, 34, { float: true, thinking: S.busy }), h('h1', {}, b.name), h('span', { class: 'muted' }, b.role), b.status === 'suspended' ? h('span', { class: 'chip warn' }, 'suspended') : null, h('span', { class: 'sp' }), S.bill && S.bill.enabled && S.bill.plan === 'free' ? btn('Upgrade', () => { track('upgrade_click'); go('plans'); }, 'btn primary') : null, h('span', { class: 'chip' }, b.model),
        h('button', { class: 'ibtn', type: 'button', 'aria-label': 'Toggle agent details', 'aria-pressed': S.panel, onclick: () => { S.panel = !S.panel; render(); } }, icon('panel'))),
      h('div', { class: 'body', id: 'scroll', 'aria-live': 'polite' }, h('div', { class: 'col' }, checklist(), h('div', { class: 'msgs' },
        S.msgs.length ? S.msgs.map((m) => h('div', { class: 'msg ' + m.role }, m.content,
          m.role === 'agent' ? h('small', { class: 'muted' }, m.used && m.used.length ? ['Based on: ', m.used.flatMap((u) => [btn(u.title, () => openNote(u.id), 'link'), ' '])] : 'Based on no verified notes') : null,
          m.note ? h('small', {}, btn('Saved to Brain as draft', () => openNote(m.note), 'link')) : null))
          : h('p', { class: 'empty muted' }, `Start a conversation with ${b.name}. Replies are scripted until a model key is set.`),
        S.busy ? h('div', { class: 'msg agent muted' }, `${b.name} is answering…`) : null))),
      h('div', { class: 'composer' }, h('div', { class: 'col', style: 'display:flex;gap:8px;align-items:flex-end;background:var(--surface);border:1px solid var(--line);border-radius:22px;padding:8px 8px 8px 18px' }, ta, sb)));
  }
  function passport() {
    const b = S.bot; if (!b) return null;
    const tabs = ['overview', 'screen', 'memory', 'apps'].map((t) => h('button', { type: 'button', role: 'tab', 'aria-selected': S.tab === t, onclick: () => { S.tab = t; render(); } }, t[0].toUpperCase() + t.slice(1)));
    let body;
    if (S.tab === 'overview') {
      const boxes = S.caps.length ? S.caps : ['memory.read', 'memory.write', 'call.join', 'approval.request', 'payments.propose'];
      const inputs = boxes.map((c) => h('label', { class: 'row', style: 'display:flex;margin:4px 0' }, h('input', { type: 'checkbox', value: c, checked: b.scopes.includes(c) }), c));
      const kv = (k, v) => h('div', { class: 'kv' }, h('span', { class: 'muted' }, k), h('span', {}, v));
      body = h('div', {}, kv('Role', b.role), kv('Team', b.team), modelEditor(b), kv('Source', b.source), kv('Trust', b.trust), kv('Status', b.status),
        h('h2', { style: 'margin-top:16px' }, 'Permissions'), inputs,
        h('div', { class: 'row2' }, btn('Save permissions', () => run(async () => { await api(`/api/bots/${b.id}/scopes`, { method: 'PUT', body: { scopes: inputs.map((l) => l.firstChild).filter((i) => i.checked).map((i) => i.value) } }); await loadBots(); S.info = 'Permissions saved and written to the audit log.'; }))),
        admin('Admin only. The server enforces every capability.'),
        h('h2', {}, 'Controls'), h('div', { class: 'row2' },
          btn(b.status === 'suspended' ? 'Resume agent' : 'Suspend agent', () => run(async () => { await api(`/api/bots/${b.id}/status`, { method: 'POST', body: { status: b.status === 'suspended' ? 'active' : 'suspended', reason: 'manual' } }); await loadBots(); })),
          b.trust === 'unverified' ? btn('Mark as reviewed', () => run(async () => { await api(`/api/bots/${b.id}/trust`, { method: 'POST', body: { trust: 'verified' } }); await loadBots(); })) : null,
          btn('Export card', () => run(async () => { await dl(`/api/bots/${b.id}/card`, `${b.id}-card.json`); }))));
    } else if (S.tab === 'screen') {
      body = h('div', {}, h('div', { class: 'screenwin' }, h('div', { class: 'screenbar' }, icon('panel', 14), h('span', { style: 'flex:1' }, `${b.name} · live`), h('span', { class: 'chip ok' }, 'LIVE')), h('div', { class: 'screenbody', id: 'screenbody' })),
        h('div', { class: 'row2', style: 'margin-top:10px' }, btn('Ask a sample question', () => { S.draft = 'Summarize what you know about payment limits.'; S.tab = 'screen'; send(); }, 'btn primary', { disabled: b.status === 'suspended' })),
        admin('This is a live stream of what the agent actually did: messages, notes read or written, tool calls and council turns. It is not a remote desktop.'));
    } else if (S.tab === 'memory') {
      const mine = S.notes.filter((n) => b.spaces.includes(n.space) && n.status === 'verified').slice(0, 10);
      body = h('div', {}, h('p', { class: 'muted' }, 'This agent reads verified notes from these spaces only:'), h('div', { class: 'row2' }, b.spaces.map((s) => h('span', { class: 'chip ok' }, s))),
        h('h2', { style: 'margin-top:16px' }, 'Notes it can use'), mine.length ? mine.map((n) => h('div', {}, btn(n.title, () => openNote(n.id), 'link'))) : h('p', { class: 'muted' }, 'No verified notes yet.'),
        h('p', {}, btn([icon('graph', 16), "Open this agent's brain"], () => { S.graph = true; S.graphAgent = b.id; go('brain').then(() => { S.graph = true; render(); }); }, 'btn')));
    } else {
      const mine = S.apps.filter((a) => a.connected && (a.grants[b.id] || []).length);
      body = h('div', {}, mine.length ? mine.map((a) => h('div', { class: 'card', style: 'margin-bottom:8px' }, h('b', {}, a.name), h('div', { class: 'row2' }, a.grants[b.id].map((t) => h('span', { class: 'chip' }, t + (a.tools.find((x) => x.name === t)?.risk === 'write' ? ' (needs approval)' : '')))))) : h('p', { class: 'muted' }, 'No app grants. Without a grant this agent cannot call any tool.'), h('p', {}, btn('Manage apps', openApps)));
    }
    return h('aside', { class: 'panel', 'aria-label': 'Agent details' }, h('div', { style: 'display:flex;gap:12px;align-items:center' }, tile(b, 52, { float: true }), h('div', {}, h('b', {}, b.name), h('div', { class: 'muted' }, b.role))), h('div', { class: 'tabs', role: 'tablist' }, tabs), body);
  }

  // ---------- council (live) ----------
  const STANCE = { support: 'Support', oppose: 'Oppose', unsure: 'Unsure' };
  function onCall(ev) {
    const r = S.room;
    if (ev.type === 'start') { r.agents = ev.agents; r.mode = ev.mode; }
    else if (ev.type === 'activity') r.activity.push(ev.text);
    else if (ev.type === 'round') { r.thinking = r.agents.map((a) => a.id); r.activity.push(ev.label); }
    else if (ev.type === 'turn') { r.events.push(ev); r.thinking = r.thinking.filter((id) => id !== ev.bot_id); r.activity.push(`${ev.name} spoke${ev.revised ? ' and changed position' : ''}`); }
    else if (ev.type === 'decision') { r.decision = ev.text; r.plan = ev.plan; r.map = ev.map; }
    else if (ev.type === 'done') { r.done = true; r.id = ev.id; r.draft = ev.draft_note_ids; }
    else if (ev.type === 'error') S.err = ev.detail;
  }
  async function startCall() {
    const ids = [...S.picked]; if (ids.length < 2) { S.err = 'Pick at least two agents.'; return render(); }
    S.room = { live: true, agents: [], events: [], activity: ['Connecting the agents…'], thinking: [], done: false }; S.planDone = {}; S.err = ''; render();
    try { await stream('/api/calls/stream', { topic: S.topic, bot_ids: ids, rounds: +S.rounds }, (ev) => { onCall(ev); render(); }); }
    catch (e) { S.err = e.message; if (!S.room.events.length) S.room = null; }
    try { S.calls = await api('/api/calls'); } catch {}
    render();
  }
  async function openCall(id) { await run(async () => { const c = await api('/api/calls/' + id); S.room = { live: false, done: true, mode: c.mode, agents: [...new Map(c.events.map((e) => [e.bot_id, { id: e.bot_id, name: e.name }])).values()], events: c.events, activity: [], thinking: [], decision: c.decision, plan: c.plan, map: c.map, draft: null }; }); }
  function councilView() {
    const cands = S.bots.filter((b) => b.id !== 'chair' && b.status !== 'suspended');
    if (!S.picked) S.picked = new Set(cands.slice(0, 3).map((b) => b.id));
    const r = S.room;
    if (!r) {
      const topic = h('textarea', { class: 'field', rows: 3, maxlength: 2000, placeholder: 'What should the agents decide? Include the goal, constraints and what a good answer looks like.' }); topic.value = S.topic;
      const startBtn = btn([icon('council', 18), 'Start call'], startCall, 'btn primary', { disabled: S.topic.trim().length < 5 });
      topic.addEventListener('input', () => { S.topic = topic.value; startBtn.disabled = topic.value.trim().length < 5; });
      const chips = cands.map((b) => h('button', { type: 'button', class: 'btn', 'aria-pressed': S.picked.has(b.id), style: S.picked.has(b.id) ? 'border-color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent)' : '', onclick: () => { S.picked.has(b.id) ? S.picked.delete(b.id) : S.picked.add(b.id); render(); } }, tile(b, 24), b.name));
      return h('div', { class: 'body' }, h('div', { class: 'col' }, h('h2', {}, 'Council call'),
        h('p', { class: 'muted' }, 'Agents join a live call, answer independently first, then respond to each other and may change their position. The Chair writes the decision and a plan. Dissent stays in the record.'),
        topic, h('div', { class: 'row2', style: 'margin:12px 0' }, chips),
        h('div', { class: 'row2' }, h('select', { class: 'field', style: 'width:auto', onchange: (e) => { S.rounds = e.target.value; } }, [1, 2, 3].map((n) => h('option', { value: n, selected: +S.rounds === n }, `${n} discussion round${n > 1 ? 's' : ''}`))),
          startBtn, btn('Use a sample topic', () => { S.topic = 'Should we let an AI agent propose supplier payments under EUR 5,000?'; render(); }),
          btn([icon('terminal', 16), 'Code review session'], () => { const dev = S.bots.filter((x) => ['Code Reviewer', 'Architect', 'Test Engineer', 'Security Reviewer'].includes(x.name)); S.picked = new Set((dev.length >= 2 ? dev : cands.slice(0, 3)).map((x) => x.id)); S.topic = 'Review this change for bugs, missing tests and security issues:\n\n<paste your diff here>'; if (dev.length < 2) S.info = 'Tip: apply the Developer preset to get a coding review board.'; render(); })),
        S.calls.length ? [h('h2', {}, 'Previous calls'), S.calls.map((x) => h('div', {}, btn(x.topic, () => openCall(x.id), 'link'), h('span', { class: 'muted mono' }, ` ${when(x.created_at)} ${x.mode}`)))] : null));
    }
    const ev = r.events, cur = ev[ev.length - 1];
    const tiles = r.agents.map((a) => { const last = [...ev].reverse().find((e) => e.bot_id === a.id), thinking = r.thinking.includes(a.id) && !r.done;
      return h('div', { class: 'ptile' + (thinking ? ' speaking' : '') }, tile(botBy(a.id), 56, { thinking }), h('b', {}, a.name), h('span', { class: 'chip' }, thinking ? 'Thinking…' : last ? STANCE[last.stance] : 'Joining')); });
    const left = h('div', {}, r.mode === 'demo' ? h('p', { class: 'chip warn' }, 'Demo mode: scripted text. No model is configured.') : null, h('div', { class: 'tiles' }, tiles),
      h('div', { class: 'cap', 'aria-live': 'polite' }, cur ? [h('div', { style: 'opacity:.7;font-size:12px' }, cur.round === 0 ? 'Independent opening' : `Discussion round ${cur.round}`), h('b', {}, cur.name + ': '), cur.text,
        cur.revised ? h('div', { style: 'opacity:.8;font-size:13px;margin-top:6px' }, 'Changed position in this round.') : null, cur.used && cur.used.length ? h('div', { style: 'opacity:.7;font-size:12px;margin-top:6px' }, 'Based on: ' + cur.used.join(', ')) : null] : 'Waiting for the first agent to speak…'),
      h('div', { class: 'row2', style: 'margin:12px 0' }, btn('New call', () => { S.room = null; render(); })),
      h('p', { class: 'muted', style: 'font-size:12px' }, r.live ? 'Live: turns appear as the agents finish them.' : 'Recorded call.'),
      r.decision ? [h('h2', {}, 'Decision'), h('div', { class: 'notebody' }, r.decision),
        h('h2', {}, 'Plan'), r.plan && r.plan.length ? h('ul', { class: 'plan', style: 'padding:0' }, r.plan.map((p, k) => h('li', {}, h('input', { type: 'checkbox', checked: !!S.planDone[k], 'aria-label': p.step, onchange: (e) => { S.planDone[k] = e.target.checked; } }), h('span', {}, p.step, ' ', h('span', { class: 'chip' }, p.owner))))) : h('p', { class: 'muted' }, 'No plan lines were returned.'),
        h('h2', {}, 'Disagreement map'), h('table', {}, h('thead', {}, h('tr', {}, h('th', {}, 'Agent'), ...(Object.values(r.map)[0] || []).map((_, k) => h('th', {}, k === 0 ? 'Opening' : `Round ${k}`)))), h('tbody', {}, Object.entries(r.map).map(([n, st]) => h('tr', {}, h('td', {}, n), ...st.map((s) => h('td', {}, STANCE[s])))))),
        r.draft ? h('p', { class: 'muted' }, 'Memory from this call is stored as drafts. ', btn('Review in Brain', () => openNote(r.draft[0]), 'link')) : null] : null);
    const right = h('div', {}, h('h2', {}, 'Agent activity'), h('div', { class: 'feed' }, [...r.activity].reverse().map((a) => h('div', {}, a))), h('h2', {}, 'Council chat'), h('div', { class: 'rchat' }, ev.map((e) => h('div', { class: 'bub' }, h('b', {}, e.name), h('div', {}, e.text)))));
    return h('div', { class: 'body' }, h('div', { class: 'wide room' }, left, right));
  }

  // ---------- brain ----------
  const svg = (W, H) => { const s = document.createElementNS(NS, 'svg'); s.setAttribute('viewBox', `0 0 ${W} ${H}`); s.setAttribute('width', '100%'); return s; };
  const sadd = (s, n, at, txt) => { const e = document.createElementNS(NS, n); for (const k in at) e.setAttribute(k, at[k]); if (txt) e.textContent = txt; s.append(e); return e; };
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const nodeColor = (n) => { const b = S.bots.find((x) => x.id === n.owner); return b ? b.color : SPACE_COLOR(n.space); };
  function kick() { if (sim && !sim.raf) sim.raf = requestAnimationFrame(tick); }
  function tick() {
    if (!sim) return; const { nodes, edges, W, H } = sim, a = sim.alpha; sim.raf = 0;
    for (const n of nodes) { for (const m of nodes) { if (n === m) continue; const dx = n.x - m.x, dy = n.y - m.y, f = (2400 * a) / (dx * dx + dy * dy + 0.5); n.vx += dx * f; n.vy += dy * f; } n.vx += (W / 2 - n.x) * 0.012 * a; n.vy += (H / 2 - n.y) * 0.012 * a; }
    for (const e of edges) { const A = sim.byId[e.from], B = sim.byId[e.to], dx = B.x - A.x, dy = B.y - A.y; A.vx += dx * 0.02 * a; A.vy += dy * 0.02 * a; B.vx -= dx * 0.02 * a; B.vy -= dy * 0.02 * a; }
    for (const n of nodes) { if (sim.drag === n) { n.vx = n.vy = 0; } else { n.x = clamp(n.x + n.vx * 0.6, 30, W - 30); n.y = clamp(n.y + n.vy * 0.6, 20, H - 20); n.vx *= 0.6; n.vy *= 0.6; } }
    edges.forEach((e, i) => { const A = sim.byId[e.from], B = sim.byId[e.to], l = sim.lines[i]; l.setAttribute('x1', A.x); l.setAttribute('y1', A.y); l.setAttribute('x2', B.x); l.setAttribute('y2', B.y); });
    const now = Date.now(); let pulsing = false;
    for (const n of nodes) {
      for (const el of [n.el, n.halo]) { el.setAttribute('cx', n.x); el.setAttribute('cy', n.y); } n.label.setAttribute('x', n.x + n.r + 3); n.label.setAttribute('y', n.y + 4);
      const until = S.pulse[n.id] || 0; if (until > now) { pulsing = true; n.halo.setAttribute('opacity', (((until - now) / 6000) * 0.9).toFixed(2)); n.halo.setAttribute('r', n.r + 6 + 3 * Math.sin(now / 200)); } else n.halo.setAttribute('opacity', 0);
    }
    sim.alpha *= 0.985; if (sim.alpha > 0.03 || sim.drag || pulsing) sim.raf = requestAnimationFrame(tick);
  }
  function buildGraph(nodes, edges) {
    const W = 860, H = 560, s = svg(W, H), deg = {}, byId = {};
    edges.forEach((e) => { deg[e.from] = (deg[e.from] || 0) + 1; deg[e.to] = (deg[e.to] || 0) + 1; });
    nodes.forEach((n, i) => { const a = (2 * Math.PI * i) / Math.max(nodes.length, 1); Object.assign(n, { x: W / 2 + Math.cos(a) * W / 3.2, y: H / 2 + Math.sin(a) * H / 3.2, vx: 0, vy: 0, r: 5 + Math.min(deg[n.id] || 0, 8) }); byId[n.id] = n; });
    const lines = edges.map(() => sadd(s, 'line', { stroke: '#8FB1FF', 'stroke-opacity': '.28' }));
    sim = { nodes, edges, lines, byId, W, H, alpha: 1, raf: 0, drag: null };
    nodes.forEach((n) => {
      const c = nodeColor(n); n.halo = sadd(s, 'circle', { r: n.r + 8, fill: 'none', stroke: '#7FA2FF', 'stroke-width': 2, opacity: 0 });
      n.el = sadd(s, 'circle', { r: n.r, fill: n.status === 'verified' ? c : '#0B1A33', stroke: c, 'stroke-width': 2, style: 'cursor:pointer' }); sadd(n.el, 'title', {}, `${n.title} (${n.kind}, ${n.status}, ${n.space})`);
      n.label = sadd(s, 'text', { 'font-size': 10, fill: '#CFE0FF', 'pointer-events': 'none' }, n.title.slice(0, 24));
      n.el.addEventListener('pointerdown', (ev) => { if (!sim) return; sim.drag = n; n.moved = 0; ev.preventDefault(); sim.alpha = 0.6; kick(); });
    });
    const at = (ev) => { const r = s.getBoundingClientRect(); return [((ev.clientX - r.left) * W) / (r.width || W), ((ev.clientY - r.top) * H) / (r.height || H)]; };
    s.addEventListener('pointermove', (ev) => { if (!sim || !sim.drag) return; const [x, y] = at(ev), n = sim.drag; n.moved += Math.abs(n.x - x) + Math.abs(n.y - y); n.x = x; n.y = y; sim.alpha = 0.5; kick(); });
    const up = () => { if (!sim || !sim.drag) return; const n = sim.drag; sim.drag = null; if (n.moved < 6) selectNode(n.id); };
    s.addEventListener('pointerup', up); s.addEventListener('pointerleave', up); kick(); return s;
  }
  function bigGraph() {
    const wrap = h('div', { class: 'gwrap dark' }, h('p', { style: 'padding:12px' }, 'Loading graph…'));
    (async () => {
      try {
        const g = await api('/api/brain/graph'), reads = new Set(), wrote = new Set(), bot = S.graphAgent ? botBy(S.graphAgent) : null;
        if (bot) (await api('/api/brain/activity?bot=' + S.graphAgent)).events.forEach((e) => (e.kind === 'read' ? reads : wrote).add(e.note_id));
        let nodes = g.nodes; if (bot) nodes = nodes.filter((n) => n.owner === bot.id || wrote.has(n.id) || reads.has(n.id) || (bot.spaces || []).filter((x) => x !== 'shared').includes(n.space));
        const ids = new Set(nodes.map((n) => n.id)); stopSim(); wrap.replaceChildren(buildGraph(nodes, g.edges.filter((e) => ids.has(e.from) && ids.has(e.to))));
        const cap = document.getElementById('gcap'); if (cap) cap.textContent = bot ? `Brain of ${bot.name}: ${nodes.length} notes (${nodes.filter((n) => n.owner === bot.id).length} written, ${reads.size} read, spaces: ${bot.spaces.join(', ')})` : `${nodes.length} notes and ${sim ? sim.edges.length : 0} connections`;
      } catch (e) { wrap.textContent = e.message; }
    })();
    return wrap;
  }
  function localGraph(n) {
    const titles = new Set([...(n.links || []), ...(n.backlinks || [])]), others = S.notes.filter((x) => titles.has(x.title) && x.id !== n.id).slice(0, 12), s = svg(260, 200);
    others.forEach((o, i) => { const a = (2 * Math.PI * i) / others.length; o.px = 130 + Math.cos(a) * 85; o.py = 100 + Math.sin(a) * 70; sadd(s, 'line', { x1: 130, y1: 100, x2: o.px, y2: o.py, stroke: 'currentColor', 'stroke-opacity': '.3' }); });
    others.forEach((o) => { const c = sadd(s, 'circle', { cx: o.px, cy: o.py, r: 7, fill: o.status === 'verified' ? SPACE_COLOR(o.space) : 'none', stroke: SPACE_COLOR(o.space), 'stroke-width': 2, style: 'cursor:pointer' }); sadd(c, 'title', {}, o.title); c.addEventListener('click', () => openNote(o.id)); sadd(s, 'text', { x: o.px, y: o.py + 18, 'font-size': 9, 'text-anchor': 'middle', fill: 'currentColor' }, o.title.slice(0, 18)); });
    sadd(s, 'circle', { cx: 130, cy: 100, r: 10, fill: 'var(--accent)' }); return s;
  }
  const hideHover = () => { if (hover) hover.remove(); hover = null; };
  function showHover(e, note) { hideHover(); hover = h('div', { class: 'hover' }, h('b', {}, note.title), h('div', { class: 'muted', style: 'margin:2px 0 6px' }, `${note.kind} · ${note.status} · ${note.space}`), (note.preview || '').slice(0, 180)); document.body.append(hover); const r = e.target.getBoundingClientRect(); hover.style.left = Math.min(r.left, innerWidth - 320) + 'px'; hover.style.top = Math.min(r.bottom + 6, innerHeight - 140) + 'px'; }
  function inline(text) {
    return text.split(/(\[\[[^\[\]]+\]\])/).map((part) => {
      const m = part.match(/^\[\[(.+)\]\]$/); if (!m) return part; const n = S.notes.find((x) => x.title === m[1]);
      if (!n) return h('span', { class: 'wl dead', title: 'No such note yet' }, m[1]);
      const a = h('button', { type: 'button', class: 'wl', onclick: () => { hideHover(); openNote(n.id); } }, m[1]);
      a.addEventListener('mouseenter', (e) => showHover(e, n)); a.addEventListener('mouseleave', hideHover); a.addEventListener('focus', (e) => showHover(e, n)); a.addEventListener('blur', hideHover); return a;
    });
  }
  function md(body, cite) {
    const out = [], fmt = (t) => (cite ? cite(t) : inline(t)); let list = null;
    for (const ln of body.split('\n')) {
      if (/^\s*[-*]\s+/.test(ln)) { if (!list) { list = h('ul'); out.push(list); } list.append(h('li', {}, fmt(ln.replace(/^\s*[-*]\s+/, '')))); continue; }
      list = null; if (/^#{1,3}\s+/.test(ln)) out.push(h('h3', {}, ln.replace(/^#+\s+/, ''))); else if (ln.trim()) out.push(h('p', {}, fmt(ln.replace(/\*\*/g, ''))));
    }
    return h('div', { class: 'md' }, out);
  }
  const activityBlock = () => h('div', {}, h('h2', {}, 'Live activity'), h('div', { class: 'ticker', id: 'ticker' }, S.activity.slice(0, 6).map((e) => h('div', {}, `${when(e.ts)} · ${e.bot || 'someone'} ${e.kind === 'read' ? 'read' : 'wrote'} "${e.title || 'a note'}"`))), h('p', { class: 'muted', style: 'font-size:12px' }, 'Neurons light up when an agent reads or writes a note.'));
  function noteSide(n) {
    if (!n) return h('div', {}, h('p', { class: 'muted' }, 'Click a neuron to preview its note.'), activityBlock());
    const kv = (k, v) => h('div', { class: 'kv' }, h('span', { class: 'muted' }, k), h('span', {}, v)), out = (n.links || []).map((t) => S.notes.find((x) => x.title === t) || { title: t, missing: true });
    return h('div', {}, h('h2', {}, n.title), h('div', { class: 'row2', style: 'margin-bottom:8px' }, h('span', { class: 'chip' }, n.kind), h('span', { class: 'chip ' + (n.status === 'verified' ? 'ok' : n.status === 'rejected' ? 'warn' : '') }, n.status), h('span', { class: 'chip' }, n.space)),
      h('div', { class: 'notebody', style: 'max-height:200px;overflow:auto' }, n.body.slice(0, 700)), h('div', { class: 'row2', style: 'margin:8px 0' }, btn('Open note', () => { S.graph = false; render(); }, 'btn primary')),
      kv('Owner', n.owner), kv('Source', n.source), h('h2', {}, `Links (${out.length})`), out.length ? out.map((o) => h('div', {}, o.missing ? h('span', { class: 'muted' }, o.title) : btn(o.title, () => selectNode(o.id), 'link'))) : h('p', { class: 'muted' }, 'No outgoing links.'),
      h('h2', {}, `Linked from (${(n.backlinks || []).length})`), (n.backlinks || []).length ? n.backlinks.map((t) => { const x = S.notes.find((y) => y.title === t); return h('div', {}, x ? btn(t, () => selectNode(x.id), 'link') : t); }) : h('p', { class: 'muted' }, 'Nothing links here yet.'),
      h('h2', {}, 'Local graph'), h('div', { class: 'gwrap' }, localGraph(n)), activityBlock());
  }
  async function selectNode(id) {
    try { S.note = await api('/api/brain/notes/' + id); S.versions = await api(`/api/brain/notes/${id}/versions`); S.edit = false; const el = document.getElementById('brain-side'); if (el) el.replaceChildren(noteSide(S.note)); }
    catch (e) { S.err = e.message; render(); }
  }
  async function uploadFile(file) {
    if (!file) return;
    if (file.size > 1500000) { S.err = 'That file is too large (max 1.5 MB).'; return render(); }
    await run(async () => {
      const buf = new Uint8Array(await file.arrayBuffer()); let bin = ''; for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
      const r = await api('/api/brain/upload', { method: 'POST', body: { filename: file.name, content_b64: btoa(bin) } });
      await loadNotes(); S.info = `Imported ${file.name} as ${r.parts} draft part(s). Drafts are not used by agents until an admin verifies them.`; await openNote(r.parent_id, true);
    });
  }
  function pickFile() { const inp = h('input', { type: 'file', accept: '.md,.txt,.csv,.json,.pdf' }); inp.addEventListener('change', () => uploadFile(inp.files[0])); inp.click(); }
  function brainView() {
    const q = h('input', { class: 'field', placeholder: 'Search notes', value: S.q, 'aria-label': 'Search notes' });
    q.addEventListener('input', () => { S.q = q.value; const pos = q.selectionStart; render(); const el = document.querySelector('input[aria-label="Search notes"]'); if (el) { el.focus(); el.setSelectionRange(pos, pos); } });
    const list = S.notes.filter((n) => (!S.q || (n.title + n.preview).toLowerCase().includes(S.q.toLowerCase())) && (!S.filter || n.status === S.filter) && (!S.space || n.space === S.space));
    const tree = h('div', { class: 'tree' }, [...new Set(list.map((n) => n.space))].sort().map((sp) => h('details', { open: true }, h('summary', {}, `${sp} (${list.filter((n) => n.space === sp).length})`),
      list.filter((n) => n.space === sp).map((n) => h('button', { type: 'button', class: 'it', 'aria-current': S.note && S.note.id === n.id ? 'true' : false, onclick: () => (S.graph ? selectNode(n.id) : openNote(n.id)) }, icon(KIND[n.kind] || 'doc', 16), h('span', { style: 'flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' }, n.title), n.status !== 'verified' ? h('span', { class: 'chip' }, n.status) : null)))));
    const drop = h('div', { class: 'drop' }, icon('doc', 18), h('span', { style: 'flex:1' }, 'Drop a file or ', btn('upload', pickFile, 'link')), h('small', { class: 'muted' }, '.md .txt .csv .json .pdf'));
    drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('over'); }); drop.addEventListener('dragleave', () => drop.classList.remove('over'));
    drop.addEventListener('drop', (e) => { e.preventDefault(); drop.classList.remove('over'); uploadFile(e.dataTransfer.files[0]); });
    const left = h('div', {}, h('div', { class: 'row2', style: 'margin-bottom:8px' }, btn([icon('plus', 16), 'Note'], () => { S.newNote = true; S.graph = false; render(); }), btn([icon('graph', 16), S.graph ? 'Notes' : 'Neurons'], () => { S.graph = !S.graph; S.newNote = false; render(); })), drop,
      h('div', { style: 'height:8px' }), q, h('div', { class: 'row2', style: 'margin:8px 0' }, ['', 'draft', 'verified'].map((f) => btn(f || 'All', () => { S.filter = f; render(); }, 'chip' + (S.filter === f ? ' ok' : ''), { 'aria-pressed': S.filter === f })), S.space ? btn(`space: ${S.space} ×`, () => { S.space = ''; render(); }, 'chip ok') : null),
      list.length ? tree : h('p', { class: 'muted' }, S.notes.length ? 'No match.' : 'No notes yet.'));
    let mid; const n = S.note;
    if (!S.notes.length && !S.newNote) {
      mid = h('div', { class: 'card empty-card' }, h('h2', {}, 'Your Brain is empty'), h('p', { class: 'muted' }, 'The Brain is a network of notes that agents read from and write to. Every note an agent writes arrives as a draft you verify. Start with sample data, a file, or your own note.'),
        h('div', { class: 'row2' }, btn('Load demo workspace', loadDemo, 'btn primary'), btn('Upload a file', pickFile), btn('New note', () => { S.newNote = true; render(); })));
    } else if (S.newNote) {
      const t = h('input', { class: 'field', placeholder: 'Title' }), b = h('textarea', { class: 'field', rows: 10, placeholder: 'Markdown. Link notes with [[Other note]].' }), k = h('select', { class: 'field', style: 'width:auto' }, ['note', 'fact', 'decision', 'rule', 'hypothesis'].map((x) => h('option', {}, x)));
      mid = h('div', {}, h('h2', {}, 'New note'), t, h('div', { style: 'height:8px' }), b, h('div', { class: 'row2', style: 'margin-top:8px' }, k, btn('Save note', () => run(async () => { const r = await api('/api/brain/notes', { method: 'POST', body: { title: t.value, body: b.value, kind: k.value } }); await loadNotes(); S.newNote = false; await openNote(r.id, true); }), 'btn primary')));
    } else if (S.graph) {
      const sel = h('select', { class: 'field', style: 'width:auto', 'aria-label': 'Whose brain', onchange: (e) => { S.graphAgent = e.target.value; render(); } }, h('option', { value: '' }, 'All agents and people'), S.bots.map((b) => h('option', { value: b.id, selected: S.graphAgent === b.id }, `Brain of ${b.name}`)));
      mid = h('div', {}, h('h2', {}, 'Live brain'), h('div', { class: 'row2', style: 'margin-bottom:8px' }, sel, h('span', { class: 'muted', id: 'gcap' }, '')),
        h('div', { class: 'legend' }, h('span', {}, 'Filled = verified, hollow = draft'), h('span', {}, 'Color = the agent that wrote it'), h('span', {}, 'Drag a neuron. A halo means an agent just read or wrote it.')), bigGraph());
    } else if (n) {
      const flagged = n.flags.includes('instruction_like') && !n.flags.includes('acknowledged'), ta = h('textarea', { class: 'field', rows: 10 }); ta.value = n.body;
      const reload = async () => { S.versions = await api(`/api/brain/notes/${n.id}/versions`); await loadNotes(); };
      mid = h('div', {}, h('h2', {}, n.title), h('div', { class: 'row2', style: 'margin-bottom:10px' }, h('span', { class: 'chip' }, n.kind), h('span', { class: 'chip ' + (n.status === 'verified' ? 'ok' : n.status === 'rejected' ? 'warn' : '') }, n.status), btn('space: ' + n.space, () => { S.space = n.space; render(); }, 'chip'), flagged ? h('span', { class: 'chip warn' }, 'instruction-like text') : null),
        S.edit ? [ta, h('div', { class: 'row2', style: 'margin-top:8px' }, btn('Save edit', () => run(async () => { S.note = await api('/api/brain/notes/' + n.id, { method: 'PUT', body: { body: ta.value } }); await reload(); S.edit = false; }), 'btn primary'), btn('Cancel', () => { S.edit = false; render(); }))] : md(n.body),
        flagged ? h('p', { class: 'muted' }, 'Instruction-like text can steer agents. This note stays out of prompts until an admin reviews and acknowledges it.') : null,
        n.status === 'draft' ? h('p', { class: 'muted' }, 'Drafts are never used in agent prompts until an admin verifies them.') : null,
        h('div', { class: 'row2', style: 'margin-top:12px' }, S.edit ? null : btn('Edit', () => { S.edit = true; render(); }),
          n.status === 'draft' || flagged ? btn(flagged ? 'Review and acknowledge' : 'Verify', () => run(async () => { S.note = await api(`/api/brain/notes/${n.id}/verify` + (flagged ? '?acknowledge=true' : ''), { method: 'POST' }); await reload(); }), 'btn primary') : null,
          n.status === 'draft' ? btn('Reject', () => run(async () => { S.note = await api(`/api/brain/notes/${n.id}/reject`, { method: 'POST' }); await reload(); })) : null),
        h('details', { style: 'margin-top:20px' }, h('summary', { class: 'muted' }, `Version history (${S.versions.length})`), S.versions.map((v) => h('div', { class: 'card', style: 'margin:8px 0' }, h('span', { class: 'mono' }, `v${v.version} · ${when(v.created_at)} · ${v.actor} · ${v.reason} · ${v.status}`), h('div', { class: 'muted' }, v.body.slice(0, 120)),
          btn('Roll back to this version', () => run(async () => { S.note = await api(`/api/brain/notes/${n.id}/rollback`, { method: 'POST', body: { version: v.version } }); await reload(); }), 'link')))));
    } else mid = h('p', { class: 'muted' }, 'Select a note.');
    return h('div', { class: 'brain' }, left, h('div', {}, mid), h('div', { id: 'brain-side' }, noteSide(S.note)));
  }

  // ---------- research ----------
  const bars = (c) => { const max = Math.max(...c.values, 1); return h('div', {}, h('div', { class: 'muted', style: 'margin-bottom:6px' }, c.title), c.labels.map((l, i) => h('div', { class: 'bar-row' }, h('span', {}, l), h('span', {}, h('i', { style: `width:${Math.max(2, (c.values[i] / max) * 100)}%` })), h('span', { class: 'mono' }, String(c.values[i]))))); };
  async function startResearch() {
    S.rs = { activity: [], sources: [], questions: [], report: null, running: true, done: [], prog: { done: 0, total: 1 }, agent: null }; render();
    try { await stream('/api/research/stream', { question: S.rq, depth: S.rdepth, web: S.rweb, context: S.rctx }, (ev) => { const r = S.rs;
      if (ev.type === 'agent') r.agent = ev.agent; else if (ev.type === 'progress') r.prog = { done: ev.done, total: ev.total }; else if (ev.type === 'plan') { r.questions = ev.questions; r.activity.push(`Planned ${ev.questions.length} sub-questions`); } else if (ev.type === 'activity') r.activity.push(ev.text); else if (ev.type === 'source') { r.sources.push(ev); r.activity.push(`Read source [${ev.n}] ${ev.title.slice(0, 60)}`); }
      else if (ev.type === 'search') { r.done.push(ev.index); r.activity.push(`Searched: ${ev.question.slice(0, 70)} (${ev.found} new source(s))`); } else if (ev.type === 'done') { r.report = ev.report; r.id = ev.id; r.mode = ev.mode; } else if (ev.type === 'error') S.err = ev.detail; render(); }); }
    catch (e) { S.err = e.message; }
    if (S.rs) S.rs.running = false; try { S.rlist = await api('/api/research'); } catch {} render();
  }
  function researchView() {
    const q = h('textarea', { class: 'field', rows: 2, maxlength: 1000, 'aria-label': 'Research question', placeholder: 'What do you want to find out?' }); q.value = S.rq;
    const cx = h('textarea', { class: 'field', rows: 2, maxlength: 2000, 'aria-label': 'Context and constraints', placeholder: 'Context for the agents (optional): who it is for, what to focus on, what to ignore.' }); cx.value = S.rctx;
    cx.addEventListener('input', () => { S.rctx = cx.value; });
    const chip = (label, on, f, dis) => h('button', { type: 'button', class: 'chip' + (on ? ' ok' : ''), 'aria-pressed': on, disabled: !!dis, onclick: f }, label);
    const depthChips = [['quick', 'Quick'], ['standard', 'Standard'], ['thorough', 'Thorough']].map(([v, l]) => chip(l, S.rdepth === v, () => { S.rdepth = v; render(); }));
    const r = S.rs, rep = r && r.report;
    const rbtn = btn([icon('lens', 16), r && r.running ? 'Researching…' : 'Start research'], startResearch, 'btn primary', { disabled: S.rq.trim().length < 8 || !!(r && r.running) });
    q.addEventListener('input', () => { S.rq = q.value; rbtn.disabled = q.value.trim().length < 8 || !!(r && r.running); });
    const cite = (t) => t.split(/(\[\d+\])/).map((p) => { const m = p.match(/^\[(\d+)\]$/); if (!m) return p; const s = (rep ? rep.sources : r.sources).find((x) => x.n === +m[1]); return !s ? p : s.kind === 'brain' ? btn(p, () => openNote(s.ref), 'wl') : /^https?:\/\//.test(s.ref) ? h('a', { class: 'wl', href: s.ref, target: '_blank', rel: 'noopener noreferrer' }, p) : p; });
    return h('div', { class: 'body' }, h('div', { class: 'wide' }, h('h2', {}, 'Deep research'),
      h('p', { class: 'muted' }, 'Plans sub-questions, searches your Brain' + (S.health.search_configured ? ' and the web' : '') + ', and writes a report with numbered citations and a chart. Without a model the report is extractive: it quotes sources and adds no generated claims.'),
      h('div', { class: 'rbox' }, q, cx), h('div', { class: 'row2', style: 'margin:10px 0;flex-wrap:wrap' }, depthChips,
        chip(S.rweb && S.health.search_configured ? 'Web: on' : 'Web: off', S.rweb && S.health.search_configured, () => { S.rweb = !S.rweb; render(); }, !S.health.search_configured),
        S.health.search_configured ? null : h('span', { class: 'muted', style: 'font-size:12px' }, 'Web search needs CFA_SEARCH_API_KEY'), h('span', { class: 'sp' }), rbtn),
      r ? h('div', { class: 'room' }, h('div', {}, r.questions.length ? [h('h2', {}, 'Plan'), h('ul', { class: 'steps', style: 'padding:0' }, r.questions.map((x, i) => h('li', {}, icon(r.done.includes(i) ? 'check' : 'search', 16), x)))] : null,
        rep ? [h('h2', {}, 'Report'), h('div', { class: 'notebody' }, md(rep.markdown, cite)), h('h2', {}, 'Chart'), bars(rep.chart),
          h('div', { class: 'row2', style: 'margin-top:12px' }, btn('Save to Brain as draft', () => run(async () => { const d = await api(`/api/research/${r.id}/save`, { method: 'POST' }); S.info = `Saved as draft: ${d.title}`; })))] : null),
        h('div', {}, researchMonitor(r, rep), h('h2', {}, `Sources (${(rep ? rep.sources : r.sources).length})`),
          (rep ? rep.sources : r.sources).map((s) => h('div', { class: 'card', style: 'margin:6px 0;font-size:13px' }, h('span', { class: 'chip' }, `[${s.n}] ${s.kind}`), ' ', s.kind === 'web' && /^https?:\/\//.test(s.ref) ? h('a', { class: 'link', href: s.ref, target: '_blank', rel: 'noopener noreferrer' }, s.title) : btn(s.title, () => openNote(s.ref), 'link'), h('div', { class: 'muted' }, s.snippet.slice(0, 120)))))) : null,
      S.rlist.length && !r ? [h('h2', {}, 'Previous research'), S.rlist.map((x) => h('div', {}, btn(x.question, () => run(async () => { const d = await api('/api/research/' + x.id); S.rs = { activity: [], sources: d.sources, questions: d.questions, report: d, running: false, done: d.questions.map((_, i) => i), id: d.id }; }), 'link'), h('span', { class: 'muted mono' }, ` ${when(x.created_at)} ${x.mode}`)))] : null));
  }

  // ---------- teams, inventory, marketplace ----------
  function memberBoxes(sel) { return S.bots.filter((b) => b.id !== 'chair' || true).map((b) => h('label', { class: 'row' }, h('input', { type: 'checkbox', value: b.id, checked: sel.includes(b.id) }), tile(b, 20), b.name)); }
  const picked = (boxes) => boxes.map((l) => l.firstChild).filter((i) => i.checked).map((i) => i.value);
  async function openChannels(t, cid) {
    const list = await api(`/api/teams/${t.id}/channels`), ch = list.find((c) => c.id === cid) || list[0];
    S.chans[t.id] = list; S.chan = { team: t, ch }; S.cmsgs = await api(`/api/channels/${ch.id}/messages`);
  }
  function channelPanel() {
    const { team, ch } = S.chan, list = S.chans[team.id] || [], inp = h('input', { class: 'field', placeholder: `Message #${ch.name}. Mention an agent with @Name`, maxlength: 2000, value: S.cdraft, 'aria-label': 'Channel message' });
    inp.addEventListener('input', () => { S.cdraft = inp.value; });
    const send = () => { const text = S.cdraft.trim(); if (!text || S.cbusy) return; S.cthink = team.members.filter((m) => text.toLowerCase().includes('@' + m.name.toLowerCase())).map((m) => m.id); S.cbusy = true; S.cdraft = ''; render();
      run(async () => { try { await api(`/api/channels/${ch.id}/messages`, { method: 'POST', body: { content: text } }); S.cmsgs = await api(`/api/channels/${ch.id}/messages`); S.chans[team.id] = await api(`/api/teams/${team.id}/channels`); } finally { S.cbusy = false; S.cthink = []; } }); };
    inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') send(); });
    const nn = h('input', { class: 'field', style: 'max-width:180px', placeholder: 'new-channel', maxlength: 30, 'aria-label': 'New channel name' });
    const bot = (id) => team.members.find((m) => m.id === id) || S.bots.find((b) => b.id === id);
    return h('div', { class: 'card chan' }, h('div', { class: 'row2' }, h('b', { style: 'flex:1' }, `${team.name} channels`), btn('Close', () => { S.chan = null; render(); }, 'link')),
      h('div', { class: 'row2', style: 'flex-wrap:wrap;margin:8px 0' }, list.map((c) => btn('# ' + c.name, () => run(() => openChannels(team, c.id)), 'chip' + (c.id === ch.id ? ' ok' : ''), { 'aria-pressed': c.id === ch.id })), nn,
        btn('Add', () => run(async () => { await api(`/api/teams/${team.id}/channels`, { method: 'POST', body: { name: nn.value.trim() } }); await openChannels(team); }), 'btn')),
      h('div', { class: 'muted', style: 'font-size:12px;margin-bottom:6px' }, ch.topic || 'Agents only answer when you @mention them, and only from notes in their own spaces.'),
      h('div', { class: 'cmsgs', role: 'log', 'aria-live': 'polite' }, S.cmsgs.length ? S.cmsgs.map((m) => h('div', { class: 'cmsg ' + m.author_kind }, m.author_kind === 'agent' ? tile(bot(m.author_id) || { id: m.author_id, name: m.author_name }, 28) : h('span', { class: 'cdot' }),
        h('div', { style: 'min-width:0' }, h('div', { class: 'row2' }, h('b', {}, m.author_name), m.author_kind === 'agent' ? h('span', { class: 'chip ' + (m.mode === 'live' ? 'ok' : 'warn') }, m.mode) : null, h('span', { class: 'muted mono', style: 'font-size:11px' }, when(m.created_at))), h('div', { class: 'ctext' }, m.content)))) : h('p', { class: 'muted' }, 'No messages yet.'),
        S.cbusy ? h('div', { class: 'cmsg agent' }, (S.cthink || []).map((id) => tile(bot(id), 28, { thinking: true })), h('span', { class: 'muted' }, (S.cthink || []).length ? 'is answering…' : 'sending…')) : null),
      h('div', { class: 'row2', style: 'margin-top:8px' }, inp, btn('Send', send, 'btn primary', { disabled: !!S.cbusy })));
  }
  function teamsView() {
    const nm = h('input', { class: 'field', placeholder: 'Team name, for example Finance desk', maxlength: 40, value: S.tnew.name, 'aria-label': 'Team name' }); nm.addEventListener('input', () => { S.tnew.name = nm.value; });
    const ms = h('input', { class: 'field', placeholder: 'Mission (optional)', maxlength: 300, value: S.tnew.mission, 'aria-label': 'Mission' }); ms.addEventListener('input', () => { S.tnew.mission = ms.value; });
    const boxes = memberBoxes(S.tnew.members);
    return h('div', { class: 'body' }, h('div', { class: 'wide' }, h('h2', {}, 'Teams'), h('p', { class: 'muted' }, 'A team is a unit with its own shared memory space. Members can read it, other agents cannot. Start a council call with a whole team.'),
      S.chan ? channelPanel() : null,
      h('div', { class: 'cards' }, S.teams.map((t) => { const eb = memberBoxes(t.members.map((m) => m.id));
        return h('div', { class: 'card appcard' }, h('div', { class: 'row2' }, icon('teams', 20), h('b', { style: 'flex:1' }, t.name), h('span', { class: 'chip' }, t.space)), h('div', { class: 'muted' }, t.mission || 'No mission set'),
          h('div', { class: 'row2' }, t.members.map((m) => h('span', { class: 'row2' }, tile(m, 24), m.name))), h('div', { class: 'muted' }, `${t.notes} team note(s)`),
          h('div', { class: 'row2' }, btn('Channels', () => run(() => openChannels(t)), 'btn'), btn([icon('council', 16), 'Start council'], () => { S.picked = new Set(t.members.map((m) => m.id).filter((id) => id !== 'chair')); S.topic = ''; go('council'); }, 'btn primary'), btn('Open team brain', () => { S.space = t.space; S.note = null; go('brain'); })),
          h('details', {}, h('summary', { class: 'muted' }, 'Edit members'), h('div', { style: 'margin-top:8px' }, eb), h('div', { class: 'row2' }, btn('Save', () => run(async () => { await api('/api/teams/' + t.id, { method: 'PUT', body: { name: t.name, mission: t.mission, members: picked(eb) } }); await Promise.all([loadTeams(), loadBots()]); }), 'btn'), btn('Delete team', () => run(async () => { await api('/api/teams/' + t.id, { method: 'DELETE' }); await Promise.all([loadTeams(), loadBots()]); }), 'link'))));
      })), S.teams.length ? null : h('p', { class: 'muted' }, 'No teams yet. Create one below or load the demo workspace.'),
      h('h2', {}, 'New team'), nm, h('div', { style: 'height:8px' }), ms, h('div', { style: 'margin:10px 0' }, boxes),
      btn([icon('plus', 16), 'Create team'], () => run(async () => { await api('/api/teams', { method: 'POST', body: { name: S.tnew.name, mission: S.tnew.mission, members: picked(boxes) } }); S.tnew = { name: '', mission: '', members: [] }; await Promise.all([loadTeams(), loadBots()]); }), 'btn primary')));
  }
  function usageView() {
    const u = S.usage, money = (v, c) => (v == null ? 'unknown' : `${v.toFixed(4)} ${c || ''}`), inp = (o, k, ph, type = 'text') => { const i = h('input', { class: 'field', type, placeholder: ph, 'aria-label': ph, value: o[k] || '', autocomplete: 'off' }); i.addEventListener('input', () => { o[k] = i.value; }); return i; };
    const reload = async () => { [S.usage, S.provs, S.prices] = await Promise.all([api('/api/usage'), api('/api/providers'), api('/api/prices')]); };
    const cap = u.budget.monthly_cap;
    return h('div', { class: 'body' }, h('div', { class: 'wide' }, h('h2', {}, 'Models & usage'),
      h('p', { class: 'muted' }, u.note + (u.cost_is_partial ? ' Some calls have no price record, so the cost total is partial.' : '')),
      h('div', { class: 'tbl-wrap' }, h('table', {}, h('thead', {}, h('tr', {}, ['Model', 'Provider', 'Calls', 'Errors', 'Tokens in / out', 'Avg latency', 'Cost', 'Fallbacks'].map((c) => h('th', {}, c)))),
        h('tbody', {}, u.models.length ? u.models.map((m) => h('tr', {}, h('td', { class: 'mono' }, m.model), h('td', {}, m.provider), h('td', {}, m.calls), h('td', {}, m.errors), h('td', { class: 'mono' }, `${m.tokens_in} / ${m.tokens_out}`), h('td', {}, m.avg_latency_ms + ' ms'), h('td', {}, money(m.cost, m.currency) + (m.calls_with_unknown_cost && m.cost != null ? ' + unpriced calls' : '')), h('td', {}, m.fallback_calls))) : h('tr', {}, h('td', { colspan: 8, class: 'muted' }, 'No model calls in this period. Demo replies make no model calls.'))))),
      h('div', { class: 'row2', style: 'margin:8px 0;flex-wrap:wrap' }, Object.entries(u.by_kind).map(([k, n]) => h('span', { class: 'chip' }, `${k}: ${n}`))),
      h('h3', {}, 'Monthly budget'), h('p', { class: 'muted' }, cap ? `Cap ${cap.amount} ${cap.currency}. Spent this month (priced calls only): ${u.budget.spent_this_month_known_cost}. Calls stop when the cap is reached.` : 'No cap set. Calls are never stopped by cost.'),
      h('div', { class: 'row2' }, inp(S, 'cap', 'Amount, for example 20', 'number'), btn('Set cap', () => run(async () => { await api('/api/usage/budget', { method: 'PUT', body: { amount: S.cap ? Number(S.cap) : null, currency: (cap && cap.currency) || 'USD' } }); await reload(); }), 'btn')),
      h('h3', {}, 'Providers'), h('p', { class: 'muted' }, 'Add any OpenAI-compatible provider. Keys are stored encrypted and never shown again. Use a model as provider-id:model-name in an agent\'s model field.'),
      S.provs.length ? h('div', { class: 'tbl-wrap' }, h('table', {}, h('thead', {}, h('tr', {}, ['Provider', 'Base URL', 'Status', 'Test with model', ''].map((c) => h('th', {}, c)))), h('tbody', {}, S.provs.map((p) => { const tm = h('input', { class: 'field', placeholder: 'model name', 'aria-label': 'Test model ' + p.id, value: S.ptest[p.id] || '' }); tm.addEventListener('input', () => { S.ptest[p.id] = tm.value; });
        return h('tr', {}, h('td', {}, h('b', {}, p.id)), h('td', { class: 'mono' }, p.base_url), h('td', {}, h('span', { class: 'chip ' + (p.status === 'ok' ? 'ok' : p.status === 'failed' ? 'warn' : '') }, p.status)), h('td', {}, tm),
          h('td', {}, h('span', { class: 'row2' }, btn('Test', () => run(async () => { const r = await api(`/api/providers/${p.id}/test`, { method: 'POST', body: { model: S.ptest[p.id] || '' } }); S.info = r.status === 'ok' ? `${p.id} answered.` : `${p.id} failed: ${r.detail}`; await reload(); }), 'link'), btn('Remove', () => run(async () => { await api('/api/providers/' + p.id, { method: 'DELETE' }); await reload(); }), 'link')))); })))) : h('p', { class: 'muted' }, 'No custom providers yet.'),
      h('div', { class: 'rbox', style: 'margin-top:8px' }, inp(S.pnew, 'id', 'Provider id, for example mistral'), inp(S.pnew, 'base_url', 'Base URL, for example https://api.mistral.ai/v1'), inp(S.pnew, 'api_key', 'API key', 'password')),
      h('div', { style: 'margin-top:8px' }, btn('Add provider', () => run(async () => { await api('/api/providers', { method: 'POST', body: S.pnew }); S.pnew = { id: '', base_url: '', api_key: '' }; await reload(); }), 'btn primary')),
      h('h3', {}, 'Fallback models'), h('p', { class: 'muted' }, 'Used only after a provider failure (credits, rate limit, outage). Every use is recorded above. Up to 3, comma separated.'),
      h('div', { class: 'row2' }, inp(S, 'fb', (u.fallback_models || []).join(', ') || 'for example provider:model'), btn('Save', () => run(async () => { await api('/api/fallbacks', { method: 'PUT', body: { models: S.fb.split(',').map((x) => x.trim()).filter(Boolean) } }); await reload(); }), 'btn')),
      h('h3', {}, 'Prices'), h('p', { class: 'muted' }, 'Costs are calculated only from price records you add, each with a source. Prices per million tokens.'),
      S.prices.length ? h('div', { class: 'tbl-wrap' }, h('table', {}, h('thead', {}, h('tr', {}, ['Provider', 'Model', 'Input', 'Output', 'Currency', 'From', 'Source'].map((c) => h('th', {}, c)))), h('tbody', {}, S.prices.map((p) => h('tr', {}, h('td', {}, p.provider), h('td', { class: 'mono' }, p.model), h('td', {}, p.input_per_mtok), h('td', {}, p.output_per_mtok), h('td', {}, p.currency), h('td', { class: 'mono' }, when(p.effective_from)), h('td', {}, p.source)))))) : h('p', { class: 'muted' }, 'No prices yet, so every cost shows as unknown.'),
      h('div', { class: 'rbox', style: 'margin-top:8px' }, inp(S.pr, 'provider', 'Provider id (default for the main key)'), inp(S.pr, 'model', 'Model name'), inp(S.pr, 'input_per_mtok', 'Input price per 1M tokens', 'number'), inp(S.pr, 'output_per_mtok', 'Output price per 1M tokens', 'number'), inp(S.pr, 'source', 'Source, for example the provider pricing page URL')),
      h('div', { style: 'margin-top:8px' }, btn('Add price', () => run(async () => { await api('/api/prices', { method: 'PUT', body: { ...S.pr, input_per_mtok: Number(S.pr.input_per_mtok), output_per_mtok: Number(S.pr.output_per_mtok) } }); S.pr = { provider: '', model: '', input_per_mtok: '', output_per_mtok: '', source: '' }; await reload(); }), 'btn')),
      h('h3', {}, 'Computer use'), h('p', { class: 'muted' }, S.cu.note), h('div', { class: 'row2', style: 'flex-wrap:wrap' }, h('span', { class: 'chip ' + (S.cu.status === 'ready' ? 'ok' : 'warn') }, S.cu.status), S.cu.problems.map((x) => h('span', { class: 'muted' }, x)))));
  }
  function accountabilityForm() {
    const e = S.invEdit, f = (k, ph, max) => { const i = h('input', { class: 'field', placeholder: ph, maxlength: max, value: e[k] || '', 'aria-label': ph }); i.addEventListener('input', () => { e[k] = i.value; }); return i; };
    return h('div', { class: 'card', style: 'margin-bottom:12px' }, h('b', {}, `Who is accountable for ${e.name}?`), h('p', { class: 'muted', style: 'margin:4px 0 8px' }, 'Owner runs it day to day, sponsor approves that it should exist, purpose says what it is for. Admin only.'),
      h('div', { class: 'rbox' }, f('owner', 'Owner (a person)', 80), f('sponsor', 'Sponsor (a person)', 80), f('purpose', 'Purpose, one sentence', 300)),
      h('div', { class: 'row2', style: 'margin-top:8px' }, btn('Save', () => run(async () => { await api(`/api/bots/${e.id}/accountability`, { method: 'PATCH', body: { owner: e.owner || '', sponsor: e.sponsor || '', purpose: e.purpose || '' } }); S.invEdit = null; S.inv = await api('/api/inventory'); S.invSum = await api('/api/inventory/summary'); }), 'btn primary'), btn('Cancel', () => { S.invEdit = null; render(); }, 'btn')));
  }
  function inventoryView() {
    const q = h('input', { class: 'field', style: 'max-width:260px', placeholder: 'Search agents', value: S.invQ, 'aria-label': 'Search agents' }); q.addEventListener('input', () => { S.invQ = q.value; const p = q.selectionStart; render(); const e = document.querySelector('input[aria-label="Search agents"]'); if (e) { e.focus(); e.setSelectionRange(p, p); } });
    const rows = S.inv.filter((a) => (!S.invQ || (a.name + a.team + a.source).toLowerCase().includes(S.invQ.toLowerCase())) && (!S.invRisk || a.risk.level === S.invRisk));
    const act = (a, path, body, method = 'POST') => run(async () => { await api(path, { method, body }); S.inv = await api('/api/inventory'); await loadBots(); });
    return h('div', { class: 'body' }, h('div', { class: 'wide' }, h('h2', {}, 'Agent inventory'), h('p', { class: 'muted' }, 'Every agent in this workspace with its source, owner, trust and risk. Suspending an agent switches off all of its capabilities at once.'),
      S.invSum ? h('div', { class: 'row2', style: 'margin-bottom:10px;flex-wrap:wrap' }, h('span', { class: 'chip ' + (S.invSum.ownerless ? 'warn' : 'ok') }, `${S.invSum.ownerless} without owner`), h('span', { class: 'chip ' + (S.invSum.no_sponsor ? 'warn' : 'ok') }, `${S.invSum.no_sponsor} without sponsor`), h('span', { class: 'chip ' + (S.invSum.no_purpose ? 'warn' : 'ok') }, `${S.invSum.no_purpose} without purpose`), h('span', { class: 'chip' }, `${S.invSum.high_risk} high risk`)) : null,
      S.invEdit ? accountabilityForm() : null,
      h('div', { class: 'row2', style: 'margin-bottom:10px' }, q, ['', 'high', 'medium', 'low', 'suspended'].map((r) => btn(r || 'All risks', () => { S.invRisk = r; render(); }, 'chip' + (S.invRisk === r ? ' ok' : ''), { 'aria-pressed': S.invRisk === r })), h('span', { class: 'muted' }, `${rows.length} of ${S.inv.length}`)),
      h('div', { class: 'tbl-wrap' }, h('table', {}, h('thead', {}, h('tr', {}, ['Agent', 'Team', 'Source', 'Trust', 'Owner / sponsor', 'Last active', 'Criticality', 'Risk', 'Status', ''].map((c) => h('th', {}, c)))),
        h('tbody', {}, rows.map((a) => h('tr', {}, h('td', {}, h('span', { class: 'row2' }, tile(a, 28), h('b', {}, a.name))), h('td', {}, a.team), h('td', {}, a.source + (a.source_ref ? ` (${a.source_ref})` : '')), h('td', {}, h('span', { class: 'chip ' + (a.trust === 'unverified' ? 'warn' : 'ok') }, a.trust)), h('td', {}, h('div', {}, a.owner === 'system' ? h('span', { class: 'muted' }, 'no owner') : a.owner), h('div', { class: 'muted', style: 'font-size:12px' }, a.sponsor ? 'Sponsor: ' + a.sponsor : 'no sponsor'), h('div', {}, btn(a.accountability.length ? 'Assign' : 'Edit', () => { S.invEdit = { id: a.id, name: a.name, owner: a.owner === 'system' ? '' : a.owner, sponsor: a.sponsor, purpose: a.purpose }; render(); }, 'link'))), h('td', { class: 'mono' }, a.last_activity ? when(a.last_activity) : 'never'),
          h('td', {}, h('select', { class: 'field', style: 'width:auto', 'aria-label': 'Criticality ' + a.name, onchange: (e) => act(a, `/api/bots/${a.id}/meta`, { criticality: e.target.value }, 'PUT') }, ['low', 'medium', 'high'].map((v) => h('option', { value: v, selected: a.criticality === v }, v)))),
          h('td', {}, h('span', { class: 'chip risk-' + a.risk.level, title: a.risk.reasons.join('; ') }, a.risk.level)), h('td', {}, a.status),
          h('td', {}, h('span', { class: 'row2' }, btn(a.status === 'suspended' ? 'Resume' : 'Suspend', () => act(a, `/api/bots/${a.id}/status`, { status: a.status === 'suspended' ? 'active' : 'suspended', reason: 'inventory' }), 'link'), a.trust === 'unverified' ? btn('Mark reviewed', () => act(a, `/api/bots/${a.id}/trust`, { trust: 'verified' }), 'link') : null)))))))));
  }
  const importAgent = (body, label) => run(async () => { const r = await api('/api/marketplace/import', { method: 'POST', body }); await loadBots(); S.info = `${label} added as "${r.name}".` + (r.note ? ' ' + r.note : ''); });
  function marketView() {
    const tabs = h('div', { class: 'row2', style: 'margin:12px 0' }, [['curated', 'Curated'], ['hf', 'Hugging Face'], ['card', 'Import a card']].map(([k, l]) => btn(l, () => { S.mtab = k; render(); }, 'chip' + (S.mtab === k ? ' ok' : ''), { 'aria-pressed': S.mtab === k })));
    let body;
    if (S.mtab === 'curated') body = h('div', { class: 'cards' }, S.market.map((c) => { const nm = h('input', { class: 'field', value: S.mname[c.id] ?? c.name, maxlength: 40, 'aria-label': 'Name for ' + c.name }); nm.addEventListener('input', () => { S.mname[c.id] = nm.value; });
      return h('div', { class: 'card appcard' }, h('div', { class: 'row2' }, tile(c, 38), h('b', { style: 'flex:1' }, c.name), h('span', { class: 'chip' }, c.category)), h('div', { class: 'muted' }, c.description), h('div', { class: 'row2' }, c.scopes.map((s) => h('span', { class: 'chip' }, s))),
        h('span', { class: 'chip risk-' + c.risk }, 'risk: ' + c.risk), nm, btn('Add to workspace', () => importAgent({ source: 'curated', ref: c.id, name: nm.value }, c.name), 'btn primary')); }));
    else if (S.mtab === 'hf') {
      const q = h('input', { class: 'field', placeholder: 'Search open models, for example llama or qwen', value: S.hfq, maxlength: 60, 'aria-label': 'Search Hugging Face' }); q.addEventListener('input', () => { S.hfq = q.value; });
      body = h('div', {}, h('p', { class: 'muted' }, 'Finds open models on Hugging Face. An imported model becomes an agent that starts unverified with read-only rights. To run it, point CFA_MODEL_BASE_URL at an OpenAI-compatible endpoint that serves it.'),
        h('div', { class: 'row2' }, q, btn([icon('search', 16), 'Search'], () => run(async () => { S.hf = await api('/api/marketplace/huggingface?q=' + encodeURIComponent(S.hfq)); }), 'btn primary')),
        h('div', { class: 'cards', style: 'margin-top:12px' }, S.hf.map((m) => { const nm = h('input', { class: 'field', value: S.hfname[m.id] ?? m.id.split('/')[1], maxlength: 40, 'aria-label': 'Name for ' + m.id }); nm.addEventListener('input', () => { S.hfname[m.id] = nm.value; });
          return h('div', { class: 'card appcard' }, h('b', {}, m.id), h('div', { class: 'row2' }, h('span', { class: 'chip' }, `${m.downloads.toLocaleString()} downloads`), h('span', { class: 'chip' }, `${m.likes} likes`), m.tags.map((t) => h('span', { class: 'chip' }, t))),
            h('a', { class: 'link', href: m.url, target: '_blank', rel: 'noopener noreferrer' }, 'Model card on Hugging Face'), nm, btn('Import as agent', () => importAgent({ source: 'huggingface', ref: m.id, name: nm.value }, m.id), 'btn primary')); })));
    } else {
      const ta = h('textarea', { class: 'field', rows: 8, placeholder: 'Paste an agent card (JSON exported from another workspace)' }); ta.value = S.card; ta.addEventListener('input', () => { S.card = ta.value; });
      const nm = h('input', { class: 'field', value: S.cardname, placeholder: 'Name for the agent', maxlength: 40, 'aria-label': 'Card agent name' }); nm.addEventListener('input', () => { S.cardname = nm.value; });
      body = h('div', {}, h('p', { class: 'muted' }, 'Cards carry a role and a system prompt, never memory or keys. Imported cards start unverified with read-only rights. Review the prompt before granting more.'), ta, h('div', { style: 'height:8px' }), nm,
        h('div', { class: 'row2', style: 'margin-top:8px' }, btn('Import card', () => { let card; try { card = JSON.parse(S.card); } catch { S.err = 'That is not valid JSON.'; return render(); } importAgent({ source: 'card', name: S.cardname, card }, 'Card'); }, 'btn primary')));
    }
    return h('div', { class: 'body' }, h('div', { class: 'wide' }, h('h2', {}, 'Marketplace'), h('p', { class: 'muted' }, 'Find agents, bring in open models and name them yourself. Everything from outside starts with the least rights.'), tabs, body));
  }

  // ---------- control ----------
  function controlView() {
    const pend = S.approvals.filter((a) => a.status === 'pending'), tcOf = (id) => S.toolCalls.find((t) => t.approval_id === id);
    const sumCards = h('div', { class: 'cards', style: 'margin-bottom:16px' }, [['Agents', S.sum.agents], ['Suspended', S.sum.suspended], ['Pending approvals', S.sum.pending_approvals], ['Memory drafts', S.sum.drafts], ['Apps connected', S.sum.apps]].map(([l, v]) => h('div', { class: 'card' }, h('div', { class: 'muted' }, l), h('b', { style: 'font-size:22px' }, String(v ?? 0)))));
    const incident = h('div', { class: 'card', style: 'margin-bottom:16px' }, h('b', {}, 'Incident switch'), h('p', { class: 'muted' }, 'Suspends every agent at once: chat, calls and tool use stop. Resume restores them. Both are written to the audit log.'),
      h('div', { class: 'row2' }, btn(S.panicArm ? 'Click again to suspend all agents' : 'Suspend all agents', () => { if (!S.panicArm) { S.panicArm = true; return render(); } S.panicArm = false; run(async () => { const r = await api('/api/security/panic', { method: 'POST', body: { action: 'suspend_all', reason: 'incident switch' } }); await loadBots(); S.sum = await api('/api/summary'); S.info = `${r.agents} agent(s) suspended.`; }); }, S.panicArm ? 'btn primary' : 'btn'),
        btn('Resume all', () => run(async () => { await api('/api/security/panic', { method: 'POST', body: { action: 'resume_all' } }); await loadBots(); S.sum = await api('/api/summary'); S.info = 'All agents resumed.'; }))));
    return h('div', { class: 'body' }, h('div', { class: 'col' }, sumCards, incident,
      h('h2', {}, 'Approval queue'), h('p', { class: 'muted' }, 'Approving records a human decision. A tool call only runs when you execute it afterwards.'),
      pend.length ? pend.map((a) => h('div', { class: 'card', style: 'margin-bottom:8px' }, h('b', {}, a.action_type), ` (${a.risk_level}): ${a.description}`, h('div', { class: 'row2', style: 'margin-top:8px' }, ['approved', 'rejected'].map((d) => btn(d === 'approved' ? 'Approve' : 'Reject', () => run(async () => { await api(`/api/security/approvals/${a.id}/decision`, { method: 'POST', body: { decision: d, decided_by: 'ui' } }); await go('control'); })))))) : h('p', { class: 'muted' }, 'Nothing pending.'),
      h('h2', {}, 'Tool calls'), S.toolCalls.length ? S.toolCalls.map((t) => h('div', { class: 'card', style: 'margin-bottom:8px' }, h('b', {}, `${t.app}.${t.tool}`), ` as ${botBy(t.bot_id).name}`, h('span', { class: 'chip ' + (['invalidated', 'expired'].includes(t.status) ? 'warn' : ''), style: 'margin-left:8px' }, `${t.status} / approval ${t.approval_status}`), h('div', { class: 'pre' }, JSON.stringify(t.args)), t.payload_hash ? h('div', { class: 'muted mono', style: 'font-size:11px' }, `Approval covers exactly this payload (${t.payload_hash})` + (t.expires_at ? `, valid until ${when(t.expires_at)}` : '')) : null,
        t.status === 'pending' && t.approval_status === 'approved' ? h('div', { class: 'row2', style: 'margin-top:8px' }, btn('Execute now', () => run(async () => { await api(`/api/tool-calls/${t.approval_id}/execute`, { method: 'POST' }); await go('control'); }), 'btn primary')) : null, t.result ? h('div', { class: 'pre' }, t.result) : null)) : h('p', { class: 'muted' }, 'No tool calls waiting.'),
      h('h2', {}, 'Authorization self-test'), h('p', { class: 'muted' }, "Synthetic probes against this app: capabilities, tool grants, suspended agents, memory spaces, unverified and instruction-like notes. It tests this app's enforcement, not model behavior."),
      h('div', { class: 'row2' }, btn([icon('flask', 16), 'Run self-test'], () => run(async () => { S.test = await api('/api/selftest', { method: 'POST' }); })), btn('Run finance demo', () => run(async () => { S.demo = await api('/api/demo/finance', { method: 'POST' }); S.test = await api('/api/selftest/latest'); await go('control'); }))),
      S.demo ? h('div', {}, S.demo.steps.map((x) => h('p', {}, (x.ok ? 'OK: ' : 'FAIL: ') + x.step))) : null,
      S.test && S.test.id ? [h('p', {}, h('b', {}, `${S.test.passed} passed, ${S.test.failed} failed `), btn('Download report', () => run(async () => { await dl(`/api/selftest/${S.test.id}/report.md`, 'selftest-report.md'); }), 'link'), ' ', S.test.share_url ? [h('a', { class: 'link', href: S.test.share_url, target: '_blank', rel: 'noopener noreferrer' }, 'Open public link'), ' ', btn('Copy', () => { navigator.clipboard && navigator.clipboard.writeText(location.origin + S.test.share_url); S.info = 'Link copied. Anyone with it can read this report.'; render(); }, 'link'), ' ', btn('Revoke', () => run(async () => { await api(`/api/selftest/${S.test.id}/share`, { method: 'DELETE' }); S.test = await api('/api/selftest/latest'); }), 'link')] : btn('Create public link', () => run(async () => { await api(`/api/selftest/${S.test.id}/share`, { method: 'POST' }); S.test = await api('/api/selftest/latest'); }), 'link')),
        h('table', {}, h('tbody', {}, S.test.probes.filter((x) => !x.ok).concat(S.test.probes.filter((x) => x.ok).slice(0, 6)).map((x) => h('tr', {}, h('td', {}, x.name), h('td', {}, x.expected), h('td', {}, x.actual), h('td', {}, x.ok ? 'pass' : 'FAIL')))))] : null,
      S.cov ? [h('h2', {}, 'Coverage of the OWASP agentic risks'), h('p', { class: 'muted' }, `${S.cov.framework}. ${S.cov.disclaimer}`),
        S.cov.items.map((c) => h('div', { class: 'card', style: 'margin-bottom:8px' }, h('div', { class: 'row2' }, h('b', { style: 'flex:1' }, (c.id.startsWith('ASI') ? c.id + ' · ' : '') + c.name), h('span', { class: 'chip ' + (c.status === 'covered' ? 'ok' : '') }, c.status),
          h('span', { class: 'chip' }, c.evidence.total ? `${c.evidence.passed} of ${c.evidence.total} probes passed` : 'no probes yet')),
          h('ul', { style: 'margin:8px 0;padding-left:18px' }, c.controls.map((x) => h('li', {}, x))), h('div', { class: 'muted', style: 'font-size:13px' }, 'Known gaps: ' + c.gaps.join('; '))))] : null,
      h('h2', {}, 'Policies'), h('table', {}, h('tbody', {}, (S.policies || []).map((p) => h('tr', {}, h('td', { class: 'mono' }, p.action_type), h('td', {}, p.decision))))),
      S.funnel ? [h('h2', {}, 'Pipeline'), h('div', { class: 'cards' }, [['Page views', S.funnel.last_30_days.welcome_view], ['Pilot clicks', S.funnel.last_30_days.cta_pilot], ['Leads', S.funnel.leads_total], ['Presets applied', S.funnel.last_30_days.preset_applied], ['Upgrade clicks', S.funnel.last_30_days.upgrade_click]].map(([l, v]) => h('div', { class: 'card' }, h('div', { class: 'muted' }, l + ' (30 days)'), h('b', { style: 'font-size:22px' }, String(v || 0))))),
        S.leads.length ? h('table', {}, h('tbody', {}, S.leads.slice(0, 8).map((x) => h('tr', {}, h('td', { class: 'mono' }, when(x.created_at)), h('td', {}, x.name), h('td', {}, x.email), h('td', {}, x.company), h('td', { class: 'muted' }, x.message.slice(0, 60)))))) : h('p', { class: 'muted' }, 'No leads yet. The public page /welcome has the pilot form.')] : null,
      h('h2', {}, 'Audit log'), h('div', { class: 'row2' }, btn('Verify integrity', () => run(async () => { const v = await api('/api/security/audit/verify'); S.verify = v.valid ? `Chain intact (${v.checked} events). It detects edits; it is not an external signature.` : 'Chain broken: ' + JSON.stringify(v); })), btn('Export for SIEM (NDJSON)', () => run(async () => { await dl('/api/security/audit/export', 'audit-export.ndjson'); }))),
      S.verify ? h('p', { class: 'muted' }, S.verify) : null, h('table', {}, h('tbody', {}, (S.audit || []).map((e) => h('tr', {}, h('td', { class: 'mono' }, when(e.created_at)), h('td', {}, e.event_type), h('td', {}, e.actor)))))));
  }

  // ---------- modals ----------
  async function openApps() { S.modal = 'apps'; S.appOpen = null; S.menu = false; S.drawer = false; render(); await run(async () => { await Promise.all([loadApps(), loadBots()]); }); }
  async function openAgent() { S.modal = 'agent'; S.menu = false; render(); await run(async () => { const t = await api('/api/templates'); S.tmpl = t.filter((x) => x.id); S.caps = (t.find((x) => x.capabilities) || {}).capabilities || []; }); }
  const close = () => { S.modal = null; render(); };
  function appsModal() {
    const cats = ['All', ...new Set(S.apps.map((a) => a.category))], list = S.apps.filter((a) => (S.appCat === 'All' || a.category === S.appCat) && a.name.toLowerCase().includes(S.appQ.toLowerCase()));
    const q = h('input', { class: 'field', placeholder: 'Search apps', value: S.appQ, 'aria-label': 'Search apps' });
    q.addEventListener('input', () => { S.appQ = q.value; const p = q.selectionStart; render(); const e = document.querySelector('input[aria-label="Search apps"]'); if (e) { e.focus(); e.setSelectionRange(p, p); } });
    let body;
    if (S.appOpen) {
      const a = S.apps.find((x) => x.id === S.appOpen), t = S.tcall, granted = (S.bots.filter((b) => (a.grants[b.id] || []).length));
      const agentSel = h('select', { class: 'field', style: 'width:auto', 'aria-label': 'Agent for test call', onchange: (e) => { t.bot = e.target.value; } }, S.bots.map((b) => h('option', { value: b.id, selected: t.bot === b.id }, b.name)));
      const toolSel = h('select', { class: 'field', style: 'width:auto', 'aria-label': 'Tool for test call', onchange: (e) => { t.tool = e.target.value; } }, a.tools.filter((x) => x.risk !== 'secret').map((x) => h('option', { value: x.name, selected: t.tool === x.name }, `${x.name} (${x.risk})`)));
      const args = h('textarea', { class: 'field', rows: 2, 'aria-label': 'Arguments as JSON' }); args.value = t.args; args.addEventListener('input', () => { t.args = args.value; });
      if (!t.bot) t.bot = S.bots[0] && S.bots[0].id; if (!t.tool && a.tools[0]) t.tool = a.tools[0].name;
      body = h('div', {}, btn('Back', () => { S.appOpen = null; render(); }, 'link'), h('h2', { style: 'margin-top:10px' }, appLogo(a, 28), ' ', a.name, ' ', h('span', { class: 'chip ' + (a.live ? 'ok' : '') }, a.live ? 'Live MCP server' : 'Demo')), h('p', { class: 'muted' }, 'Choose which tools each agent may call. Write tools only create an approval request. Secret-looking tools can never be granted.'),
        h('div', { class: 'tbl-wrap' }, h('table', {}, h('thead', {}, h('tr', {}, h('th', {}, 'Agent'), a.tools.map((x) => h('th', {}, x.name, h('div', { class: 'muted', style: 'font-weight:400;font-size:12px' }, x.risk === 'read' ? 'read' : x.risk === 'write' ? 'needs approval' : 'blocked by policy'))), h('th', {}))),
          h('tbody', {}, S.bots.map((b) => { const boxes = a.tools.map((x) => h('input', { type: 'checkbox', value: x.name, disabled: x.risk === 'secret', checked: (a.grants[b.id] || []).includes(x.name), 'aria-label': `${b.name} ${x.name}` }));
            return h('tr', {}, h('td', {}, h('span', { class: 'row2' }, tile(b, 24), b.name)), boxes.map((x) => h('td', {}, x)), h('td', {}, btn('Save', () => run(async () => { await api(`/api/bots/${b.id}/apps/${a.id}`, { method: 'PUT', body: { tools: boxes.filter((x) => x.checked).map((x) => x.value) } }); await loadApps(); S.info = 'Grants saved and written to the audit log.'; }), 'link'))); })))),
        h('h2', {}, 'Try a call'), h('p', { class: 'muted' }, a.live ? 'Runs against the live server. Read tools return immediately, write tools wait for approval in Control.' : 'Demo: no external service is contacted.'),
        h('div', { class: 'row2' }, agentSel, toolSel), h('div', { style: 'height:8px' }), args, h('div', { class: 'row2', style: 'margin-top:8px' }, btn('Run as this agent', () => run(async () => { let ar = {}; try { ar = JSON.parse(t.args || '{}'); } catch { throw new Error('Arguments must be valid JSON.'); } const r = await api(`/api/bots/${t.bot}/tools`, { method: 'POST', body: { app: a.id, tool: t.tool, args: ar } }); t.out = r.status === 'pending_approval' ? `Waiting for approval (${r.approval.id}). Approve it in Control, then execute.` : r.result; }), 'btn primary')),
        t.out ? h('div', { class: 'pre' }, t.out) : null,
        h('p', {}, a.live ? [btn('Refresh tools', () => run(async () => { await api(`/api/mcp/servers/${a.id}/refresh`, { method: 'POST' }); await loadApps(); })), ' ', btn('Remove server', () => run(async () => { await api(`/api/mcp/servers/${a.id}`, { method: 'DELETE' }); S.appOpen = null; await loadApps(); }))] : btn('Disconnect ' + a.name, () => run(async () => { await api(`/api/apps/${a.id}/disconnect`, { method: 'POST' }); S.appOpen = null; await loadApps(); }))));
    } else {
      const m = S.mcp, nm = h('input', { class: 'field', placeholder: 'Name', maxlength: 40, value: m.name, 'aria-label': 'MCP server name' }), url = h('input', { class: 'field', placeholder: 'https://your-server.example/mcp', maxlength: 300, value: m.url, 'aria-label': 'MCP server URL' }), tk = h('input', { class: 'field', type: 'password', placeholder: 'Bearer token (optional)', maxlength: 500, value: m.token, autocomplete: 'off', 'aria-label': 'MCP bearer token' });
      nm.addEventListener('input', () => { m.name = nm.value; }); url.addEventListener('input', () => { m.url = url.value; }); tk.addEventListener('input', () => { m.token = tk.value; });
      body = h('div', {}, h('details', { class: 'card', style: 'margin-bottom:14px' }, h('summary', {}, h('b', {}, 'Add a live MCP server')), h('p', { class: 'muted' }, 'Connects to a server that speaks MCP over Streamable HTTP. The app discovers its tools, treats every tool as a write unless the server marks it read-only, and blocks secret-looking tools. Tokens are encrypted at rest and never shown again. OAuth and legacy SSE-only servers are not supported.'),
        h('div', { class: 'row2' }, nm, url), h('div', { style: 'height:8px' }), tk, h('div', { class: 'row2', style: 'margin-top:8px' }, btn('Connect and discover tools', () => run(async () => { const r = await api('/api/mcp/servers', { method: 'POST', body: { name: m.name, url: m.url, token: m.token || undefined } }); S.mcp = { name: '', url: '', token: '' }; await loadApps(); S.appOpen = r.id; }), 'btn primary'))),
        h('div', { class: 'row2', style: 'margin-bottom:12px' }, cats.map((c) => btn(c, () => { S.appCat = c; render(); }, 'chip' + (S.appCat === c ? ' ok' : ''), { 'aria-pressed': S.appCat === c }))),
        h('div', { class: 'cards' }, list.map((a) => h('div', { class: 'card appcard' }, h('div', { class: 'row2' }, appLogo(a, 38), h('b', {}, a.name), h('span', { class: 'chip' + (a.live ? ' ok' : '') }, a.live ? 'Live' : 'Demo')),
          h('div', { class: 'muted' }, a.description), h('div', { class: 'row2' }, h('span', { class: 'chip' }, `${a.tools.filter((t) => t.risk === 'read').length} read`), h('span', { class: 'chip' }, `${a.tools.filter((t) => t.risk === 'write').length} need approval`), a.tools.some((t) => t.risk === 'secret') ? h('span', { class: 'chip warn' }, 'secrets blocked') : null),
          a.connected ? btn('Manage grants', () => { S.appOpen = a.id; render(); }, 'btn primary') : btn('Connect (demo)', () => run(async () => { await api(`/api/apps/${a.id}/connect`, { method: 'POST' }); await loadApps(); S.appOpen = a.id; }))))));
    }
    return h('div', { class: 'scrim', onclick: (e) => { if (e.target.classList.contains('scrim')) close(); } }, h('div', { class: 'modal', role: 'dialog', 'aria-label': 'Apps' },
      h('div', { class: 'modal-h' }, h('h2', { style: 'margin:0;flex:1' }, 'Apps (MCP)'), h('button', { class: 'ibtn', type: 'button', 'aria-label': 'Close', onclick: close }, icon('x'))),
      h('div', { class: 'banner', style: 'border:1px solid var(--line);border-radius:12px;margin-bottom:12px' }, 'The catalog apps are a demo and contact no external service. Live MCP servers you add are real.'),
      S.err ? h('div', { class: 'banner', role: 'alert', style: 'color:var(--bad)' }, S.err) : null, S.appOpen ? null : q, h('div', { style: 'height:12px' }), body));
  }
  function agentModal() {
    const d = S.ag, t = S.tmpl.find((x) => x.id === d.template) || { scopes: [] };
    const name = h('input', { class: 'field', placeholder: 'Agent name, for example Ledger', maxlength: 40, value: d.name, 'aria-label': 'Agent name' }); name.addEventListener('input', () => { d.name = name.value; });
    const team = h('input', { class: 'field', placeholder: 'Team, for example Finance desk', maxlength: 30, value: d.team, 'aria-label': 'Team' }); team.addEventListener('input', () => { d.team = team.value; });
    const tpl = h('select', { class: 'field', 'aria-label': 'Template', onchange: (e) => { d.template = e.target.value; render(); } }, S.tmpl.map((x) => h('option', { value: x.id, selected: x.id === d.template }, x.name)));
    const caps = (S.caps || []).map((c) => h('label', { class: 'row' }, h('input', { type: 'checkbox', value: c, checked: t.scopes.includes(c), disabled: d.template !== 'custom' }), c));
    const riskOf = (sc) => { let n = 0, why = []; if (sc.includes('payments.propose')) { n += 3; why.push('can propose payments'); } if (sc.includes('memory.write')) { n += 1; why.push('writes memory drafts'); } if (sc.includes('approval.request')) { n += 1; why.push('can request approvals'); } return { lvl: n >= 4 ? 'high' : n >= 2 ? 'medium' : 'low', why }; };
    const prev = h('span', { class: 'chip' }, ''), upd = () => { const r = riskOf(d.template === 'custom' ? picked(caps) : t.scopes); prev.className = 'chip risk-' + r.lvl; prev.textContent = `Risk preview: ${r.lvl}${r.why.length ? ' (' + r.why.join(', ') + ')' : ''}`; };
    caps.forEach((l) => l.firstChild.addEventListener('change', upd)); upd();
    const icons = ['compass', 'lens', 'wrench', 'scales', 'coins', 'shield', 'book', 'chat', 'spark'].map((i) => h('button', { type: 'button', 'aria-pressed': d.icon === i, 'aria-label': i, onclick: () => { d.icon = i; render(); } }, tile({ color: d.color || '#12294F', icon: i }, 34)));
    const swatches = ['#2F5BD3', '#B7791F', '#1B7F79', '#1F6F8B', '#7A4E9C', '#3D7A4F', '#B5543C', '#5B6B88'].map((c) => h('button', { type: 'button', class: 'swatch', style: `background:${c}`, 'aria-label': 'Color ' + c, 'aria-pressed': d.color === c, onclick: () => { d.color = c; render(); } }));
    return h('div', { class: 'scrim', onclick: (e) => { if (e.target.classList.contains('scrim')) close(); } }, h('div', { class: 'modal', role: 'dialog', 'aria-label': 'New agent', style: 'max-width:560px' },
      h('div', { class: 'modal-h' }, h('h2', { style: 'margin:0;flex:1' }, 'New agent'), h('button', { class: 'ibtn', type: 'button', 'aria-label': 'Close', onclick: close }, icon('x'))),
      h('p', { class: 'muted' }, 'Demo mode: no model provider is connected, so replies are scripted. Permissions and memory spaces are real and enforced.'), S.err ? h('div', { class: 'banner', role: 'alert', style: 'color:var(--bad)' }, S.err) : null,
      h('label', {}, 'Name', name), h('div', { style: 'height:10px' }), h('label', {}, 'Team', team), h('div', { style: 'height:10px' }), h('label', {}, 'Template', tpl),
      h('p', { class: 'muted' }, d.template.startsWith('finance') || d.template.startsWith('compliance') ? 'Finance templates get a finance memory space and store their operating rules in the Brain.' : 'This agent gets a private memory space.'),
      h('div', {}, 'Capabilities'), h('div', {}, caps), h('div', { style: 'margin:6px 0' }, prev), h('div', { class: 'muted', style: 'margin-top:10px;font-size:12px' }, 'The face is drawn from the agent name; the colour sets the ring.'), h('div', { style: 'margin-top:10px' }, 'Color'), h('div', { class: 'picker' }, swatches),
      h('div', { class: 'row2', style: 'margin-top:18px' }, btn('Create agent', () => run(async () => { const body = { template: d.template, name: d.name, scopes: d.template === 'custom' ? picked(caps) : undefined, team: d.team || undefined, icon: d.icon || undefined, color: d.color || undefined };
        const r = await api('/api/bots', { method: 'POST', body }); await loadBots(); S.modal = null; S.ag = { template: 'finance-analyst', name: '', team: '', icon: '', color: '' }; await pick(r.id); }), 'btn primary'), btn('Cancel', close))));
  }

  // ---------- shell ----------
  const track = (name) => { try { fetch('/api/events', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) }); } catch {} };
  function appLogo(a, size = 36) {
    const box = h('span', { class: 'lbox', style: `width:${size}px;height:${size}px` }), mono = () => box.replaceChildren(h('b', {}, a.name[0]));
    if (a.live || !a.logo) { mono(); return box; }
    const img = h('img', { alt: a.name, width: size - 14, height: size - 14, loading: 'lazy' }), cdn = S.health.logo_cdn ? `${S.health.logo_cdn}/${a.logo}` : '';
    img.src = `/static/logos/${a.id}.svg`; // drop official SVGs here to override
    img.addEventListener('error', () => { if (cdn && !img.dataset.t) { img.dataset.t = '1'; img.src = cdn; } else mono(); });
    box.append(img); return box;
  }
  function meterBlock() {
    const b = S.bill; if (!b || !b.enabled) return null;
    const lim = b.limits.messages, pct = lim > 100000 ? 6 : Math.min(100, Math.round((b.usage.messages / lim) * 100));
    return h('div', { class: 'meter' }, h('div', { class: 'row2' }, h('b', {}, b.plan_name + ' plan'), h('span', { class: 'muted', style: 'flex:1;text-align:right;font-size:12px' }, `${b.usage.messages} / ${lim > 100000 ? 'unlimited' : lim} messages`)),
      h('div', { class: 'progress' + (pct >= 90 ? ' hot' : '') }, h('i', { style: `width:${pct}%` })), b.plan === 'free' ? btn('Upgrade', () => { track('upgrade_click'); go('plans'); }, 'btn primary', { style: 'width:100%;margin-top:8px;justify-content:center' }) : null);
  }
  function mobileBar() {
    return h('div', { class: 'mbar' }, h('button', { class: 'ibtn', type: 'button', 'aria-label': 'Menu', onclick: () => { S.drawer = !S.drawer; render(); if (S.drawer) refreshSum(); } }, icon('menu')), h('div', { class: 'logo' }, 'Shewiun'), h('span', { class: 'sp' }),
      h('button', { class: 'ibtn', type: 'button', 'aria-label': 'Connect apps', onclick: openApps }, icon('grid')), h('button', { class: 'ibtn', type: 'button', 'aria-label': 'New agent', onclick: openAgent }, icon('plus')));
  }
  function modelEditor(b) {
    const inp = h('input', { class: 'field', placeholder: 'default, or hf:MiniMaxAI/MiniMax-M2', value: b.model.endsWith('(no key)') ? b.model.replace(' (no key)', '') : (b.model === 'demo mode' ? '' : b.model), 'aria-label': 'Model for this agent', list: 'models-list' });
    const dlist = h('datalist', { id: 'models-list' }, ((S.models && S.models.suggested) || []).map((x) => h('option', { value: x.id }, x.name)));
    return h('div', { style: 'margin:6px 0' }, h('div', { class: 'kv' }, h('span', { class: 'muted' }, 'Model'), h('span', {}, b.model)), inp, dlist,
      h('div', { class: 'row2', style: 'margin-top:6px' }, btn('Save model', () => run(async () => { await api(`/api/bots/${b.id}/model`, { method: 'PUT', body: { model: inp.value.trim() } }); await loadBots(); S.info = 'Model saved. Open models run through Hugging Face when HF_TOKEN is set.'; }), 'btn'), btn('Settings', () => go('settings'), 'link')));
  }
  // Reader view: shows the source the agent is reading right now. It is a text extract, not a live browser; a real browser needs an isolated provider.
  function readerView(r) {
    const src = r.sources[r.sources.length - 1], web = src && src.kind === 'web', url = !src ? (r.running ? 'searching…' : '') : web ? src.ref : 'Brain · ' + src.title;
    return h('div', { class: 'reader', 'aria-label': 'Reader view of the current source' }, h('div', { class: 'rbar' }, h('span', { class: 'rdots' }, h('i'), h('i'), h('i')), h('span', { class: 'rurl mono' }, url || 'no page opened yet'), h('span', { class: 'chip' }, 'Reader view')),
      h('div', { class: 'rbody' + (r.running ? ' reading' : '') }, src ? [h('b', {}, src.title), h('p', { class: 'muted', style: 'margin:6px 0 0' }, src.snippet)] : h('span', { class: 'muted' }, r.running ? 'Planning the search…' : 'Nothing was read.'),
        h('div', { class: 'muted', style: 'font-size:11px;margin-top:8px' }, 'Text extract of the source, not a live browser.')));
  }
  function researchMonitor(r, rep) {
    const pr = r.prog || { done: 1, total: 1 }, pct = Math.round((pr.done / Math.max(pr.total, 1)) * 100);
    return h('div', { class: 'monitor' }, h('div', { class: 'monhead' }, r.agent ? tile(r.agent, 38, { thinking: r.running, float: !r.running }) : icon('lens', 24), h('div', { style: 'flex:1' }, h('b', {}, r.agent ? r.agent.name : 'Research agent'), h('div', { style: 'font-size:12px;opacity:.7' }, r.running ? `working: step ${pr.done} of ${pr.total}` : rep ? 'finished' : 'idle')), h('span', { class: 'chip ' + (r.running ? 'ok' : '') }, r.running ? 'LIVE' : 'DONE')),
      h('div', { class: 'progress dark' }, h('i', { style: `width:${pct}%` })), readerView(r), h('div', { class: 'monbody' }, r.activity.length ? [...r.activity].reverse().map((a) => h('div', {}, a)) : h('div', { style: 'opacity:.7' }, 'Waiting to start…')));
  }
  async function upgrade(plan) { track('upgrade_click'); await run(async () => { const r = await api('/api/billing/checkout', { method: 'POST', body: { plan } }); location.href = r.url; }); }
  async function applyPreset(id) {
    track('preset_applied');
    await run(async () => { const r = await api(`/api/presets/${id}/apply`, { method: 'POST' }); await Promise.all([loadBots(), loadNotes(), loadTeams(), api('/api/billing').then((x) => { S.bill = x; })]); S.modal = null; S.onb = { done: true, suggest: false }; S.topic = r.topic; S.info = `Preset ready: ${r.created} agents, team "${r.team}" and ${r.notes} starter notes. Try the sample question in a council call.`; if (r.first_agent) await pick(r.first_agent); });
  }
  function onboardModal() {
    return h('div', { class: 'scrim' }, h('div', { class: 'modal wizard', role: 'dialog', 'aria-label': 'Choose a preset' }, h('div', { class: 'logo' }, 'Shewiun'), h('h2', { style: 'margin-top:16px;border:0;padding:0;font-size:22px' }, 'What are you building?'),
      h('p', { class: 'muted' }, 'Pick a starter team. It creates agents with roles and the right permissions, a shared memory with first notes, and a sample question. You can change everything later.'),
      S.err ? h('div', { class: 'banner', role: 'alert', style: 'color:var(--bad)' }, S.err) : null,
      h('div', { class: 'cards' }, S.presets.map((p) => h('div', { class: 'card appcard preset' }, h('div', { class: 'stack' }, p.agents.slice(0, 4).map((a) => tile(a, 40))), h('div', { class: 'row2' }, h('b', { style: 'flex:1' }, p.name), h('span', { class: 'chip' }, p.level)), h('div', { class: 'muted' }, p.tagline), h('div', { class: 'muted', style: 'font-size:12px' }, 'For: ' + p.audience),
        h('div', { class: 'pflow' }, p.flow),
        h('ul', { class: 'pfacts' }, h('li', {}, `${p.agents.length} agents: ${p.agents.map((a) => a.name).join(', ')}`), h('li', {}, `${p.notes} starter notes in a shared team memory`), h('li', {}, p.read_only ? `${p.read_only} read-only agent(s) that cannot write memory` : 'All agents can write drafts to memory'), h('li', {}, p.can_request_approval ? (p.proposes_payments ? 'Can propose payments, a human always approves' : 'Can ask a human for approval') : 'No approval flow')),
        btn('Use this preset', () => applyPreset(p.id), 'btn primary')))),
      h('div', { class: 'row2', style: 'margin-top:16px' }, btn('Load the demo workspace instead', () => { S.modal = null; loadDemo(); }), btn('Skip for now', () => { S.skipOnb = true; S.modal = null; api('/api/onboarding/complete', { method: 'POST' }).catch(() => {}); render(); }, 'link'))));
  }
  function upsellModal() {
    const u = S.upsell || {}, close2 = () => { S.modal = null; S.upsell = null; render(); };
    return h('div', { class: 'scrim', onclick: (e) => { if (e.target.classList.contains('scrim')) close2(); } }, h('div', { class: 'modal', role: 'dialog', 'aria-label': 'Plan limit reached', style: 'max-width:480px' }, h('h2', {}, 'Plan limit reached'), h('p', {}, u.message || 'You reached a limit of your plan.'),
      h('div', { class: 'progress hot' }, h('i', { style: 'width:100%' })), h('p', { class: 'muted' }, `${u.used} of ${u.limit} ${u.label} used this month on the ${(u.plan || '').toUpperCase()} plan.`),
      h('div', { class: 'row2' }, btn('See plans', () => { track('upgrade_click'); S.modal = null; S.upsell = null; go('plans'); }, 'btn primary'), btn('Not now', close2))));
  }
  function leadModal() {
    const l = S.lead, f = (k, ph, type = 'text') => { const i = h('input', { class: 'field', type, placeholder: ph, maxlength: 120, value: l[k], 'aria-label': ph }); i.addEventListener('input', () => { l[k] = i.value; }); return i; };
    const msg = h('textarea', { class: 'field', rows: 3, maxlength: 1000, placeholder: 'What do you want to prove or protect?', 'aria-label': 'Message' }); msg.value = l.message; msg.addEventListener('input', () => { l.message = msg.value; });
    return h('div', { class: 'scrim', onclick: (e) => { if (e.target.classList.contains('scrim')) close(); } }, h('div', { class: 'modal', role: 'dialog', 'aria-label': 'Request a pilot', style: 'max-width:480px' }, h('h2', {}, 'Request a pilot'), h('p', { class: 'muted' }, 'We set up a workspace with you, run the authorization test on your agents and send you the evidence report.'),
      S.err ? h('div', { class: 'banner', role: 'alert', style: 'color:var(--bad)' }, S.err) : null, f('name', 'Your name'), h('div', { style: 'height:8px' }), f('email', 'Work email', 'email'), h('div', { style: 'height:8px' }), f('company', 'Company'), h('div', { style: 'height:8px' }), msg,
      h('div', { class: 'row2', style: 'margin-top:12px' }, btn('Send request', () => run(async () => { await api('/api/leads', { method: 'POST', body: { ...l, source: 'app' } }); S.lead = { name: '', email: '', company: '', message: '' }; S.modal = null; S.info = 'Thank you. We will reply by email.'; }), 'btn primary'), btn('Cancel', close))));
  }
  function plansView() {
    const b = S.bill; if (!b) return h('div', { class: 'body' }, h('p', { class: 'muted' }, 'Loading…'));
    const fmt = (n) => (n >= 100000 ? 'unlimited' : n.toLocaleString());
    const cta = (p) => (p.id === b.plan ? h('span', { class: 'chip ok' }, 'Current plan') : p.id === 'free' ? null : p.id === 'pilot' ? btn('Request a pilot', () => { track('cta_pilot'); S.modal = 'lead'; render(); }, 'btn primary')
      : b.checkout ? btn('Upgrade to ' + p.name, () => upgrade(p.id), 'btn primary') : btn('Ask for ' + p.name, () => { S.modal = 'lead'; render(); }, 'btn'));
    return h('div', { class: 'body' }, h('div', { class: 'wide' }, h('h2', {}, 'Plans and usage'),
      !b.enabled ? h('div', { class: 'banner', style: 'border:1px solid var(--line);border-radius:12px;margin-bottom:14px' }, 'Billing is off on this deployment: self-hosted installs have no limits. Set CFA_BILLING=on to enforce plans.') : null,
      b.status === 'past_due' ? h('div', { class: 'banner', role: 'alert', style: 'color:var(--bad);margin-bottom:14px' }, 'Your last payment failed. Update your payment method to keep your plan.') : null,
      h('div', { class: 'cards' }, b.plans.map((p) => h('div', { class: 'card plan' + (p.id === b.plan ? ' current' : '') }, h('b', { style: 'font-size:16px' }, p.name), h('div', { class: 'price' }, p.price_eur === null ? 'Custom' : p.price_eur === 0 ? '€0' : `€${p.price_eur}`, p.price_eur ? h('small', {}, ' / month') : null), h('div', { class: 'muted' }, p.tagline),
        h('ul', {}, ['messages', 'calls', 'research', 'uploads', 'agents', 'mcp_servers'].map((k) => h('li', {}, `${fmt(p.limits[k])} ${b.labels[k]}${['agents', 'mcp_servers'].includes(k) ? '' : ' / month'}`))), cta(p)))),
      b.portal ? h('p', {}, btn('Manage billing and invoices', () => run(async () => { const r = await api('/api/billing/portal', { method: 'POST' }); location.href = r.url; }))) : null,
      h('h2', {}, 'Usage this month'), h('div', { class: 'card' }, Object.keys(b.labels).map((k) => { const lim = b.limits[k], pct = lim >= 100000 ? 4 : Math.min(100, Math.round((b.usage[k] / Math.max(lim, 1)) * 100));
        return h('div', { style: 'margin:10px 0' }, h('div', { class: 'row2' }, h('span', { style: 'flex:1' }, b.labels[k]), h('span', { class: 'muted mono' }, `${b.usage[k]} / ${fmt(lim)}`)), h('div', { class: 'progress' + (pct >= 90 ? ' hot' : '') }, h('i', { style: `width:${pct}%` }))); })),
      h('p', { class: 'muted', style: 'font-size:12px' }, 'Limits reset on the first of each month. Prices are launch prices and may change. Plans apply to this workspace.')));
  }
  function settingsView() {
    const m = S.models, k = S.keys, mt = S.mtest;
    const kname = h('input', { class: 'field', placeholder: 'Key name, for example Alice laptop', maxlength: 40, 'aria-label': 'Key name' }), krole = h('select', { class: 'field', style: 'width:auto', 'aria-label': 'Key role' }, ['member', 'admin', 'viewer'].map((r) => h('option', {}, r)));
    const mi = h('input', { class: 'field', placeholder: 'Model id, for example hf:MiniMaxAI/MiniMax-M2', value: mt.model, 'aria-label': 'Model to test' }); mi.addEventListener('input', () => { mt.model = mi.value; });
    const days = h('input', { class: 'field', type: 'number', min: 7, max: 3650, value: S.ret, style: 'width:110px', 'aria-label': 'Retention days' }); days.addEventListener('input', () => { S.ret = +days.value; });
    return h('div', { class: 'body' }, h('div', { class: 'wide' }, h('h2', {}, 'Settings'),
      h('div', { class: 'card', style: 'margin-bottom:14px' }, h('b', {}, 'Readiness'), S.ready ? h('p', {}, h('span', { class: 'chip ' + (S.ready.ready ? 'ok' : 'warn') }, S.ready.ready ? 'ready' : 'not ready'), ' ', S.ready.errors.join('; ')) : null, (S.health.warnings || []).map((w) => h('div', { class: 'muted' }, w))),
      h('div', { class: 'card', style: 'margin-bottom:14px' }, h('b', {}, 'Models'), h('p', { class: 'muted' }, 'Agents use any OpenAI-compatible endpoint, and open models through Hugging Face Inference Providers (prefix hf:). Keys are environment variables and are never shown here.'),
        m ? m.providers.map((p) => h('div', { class: 'kv' }, h('span', {}, p.name), h('span', { class: 'chip ' + (p.configured ? 'ok' : 'warn') }, p.configured ? 'key set' : 'no key'))) : null, m ? h('p', { class: 'muted' }, m.free_tier_note) : null,
        h('div', { class: 'muted', style: 'margin-top:8px' }, 'Open models to try (click to fill):'), m ? h('div', { class: 'row2' }, m.suggested.map((x) => btn(x.name, () => { mt.model = x.id; render(); }, 'chip', { title: x.note }))) : null,
        h('div', { class: 'row2', style: 'margin-top:10px' }, mi, btn('Test connection', () => run(async () => { const r = await api('/api/models/test', { method: 'POST', body: { model: mt.model || null } }); mt.out = r.ok ? `OK: ${r.provider} / ${r.model} answered in ${r.ms} ms` : `Not working: ${r.message}`; }), 'btn primary')), mt.out ? h('div', { class: 'pre' }, mt.out) : null,
        h('p', { class: 'muted', style: 'font-size:12px' }, 'Set the model per agent in the agent panel. Default: CFA_MODEL_BASE_URL, CFA_MODEL_API_KEY, CFA_MODEL_NAME. Hugging Face: HF_TOKEN.')),
      h('div', { class: 'card', style: 'margin-bottom:14px' }, h('b', {}, 'Access keys'), h('p', { class: 'muted' }, 'Keys are stored as a hash. A new token is shown once.'),
        S.newKey ? h('div', { class: 'pre' }, `New token for ${S.newKey.name} (${S.newKey.role}): ${S.newKey.token}\nCopy it now. It cannot be shown again.`) : null,
        k ? h('table', {}, h('tbody', {}, k.keys.map((x) => h('tr', {}, h('td', {}, x.name), h('td', {}, x.role), h('td', { class: 'mono' }, 'used ' + (when(x.last_used) || 'never')), h('td', {}, x.revoked ? h('span', { class: 'chip warn' }, 'revoked') : btn('Revoke', () => run(async () => { await api('/api/admin/keys/' + x.id, { method: 'DELETE' }); S.keys = await api('/api/admin/keys'); }), 'link')))))) : null, k && k.env_keys ? h('p', { class: 'muted' }, `${k.env_keys} key(s) come from the environment.`) : null,
        h('div', { class: 'row2', style: 'margin-top:8px' }, kname, krole, btn('Create key', () => run(async () => { S.newKey = await api('/api/admin/keys', { method: 'POST', body: { name: kname.value, role: krole.value } }); S.keys = await api('/api/admin/keys'); }), 'btn primary'))),
      h('div', { class: 'card' }, h('b', {}, 'Backups and data'), h('p', { class: 'muted' }, 'Backups copy the whole database. Keep CFA_SECRET_KEY somewhere else. The audit log is never purged.'),
        h('div', { class: 'row2' }, btn('Back up now', () => run(async () => { await api('/api/admin/backup', { method: 'POST' }); S.backups = await api('/api/admin/backups'); S.info = 'Backup created.'; }), 'btn primary'), btn('Export all data (JSON)', () => run(async () => { await dl('/api/admin/export', 'cfa-export.json'); }))),
        h('div', { style: 'margin-top:8px' }, (S.backups || []).slice(0, 6).map((x) => h('div', { class: 'row2' }, h('span', { class: 'mono', style: 'flex:1' }, x.name), h('span', { class: 'muted' }, Math.round(x.bytes / 1024) + ' KB'), btn('Download', () => run(async () => { await dl('/api/admin/backups/' + x.name, x.name); }), 'link')))),
        h('div', { class: 'row2', style: 'margin-top:10px' }, h('span', {}, 'Delete chats, activity, calls and research older than'), days, h('span', {}, 'days'), btn('Run retention', () => run(async () => { const r = await api('/api/admin/retention', { method: 'POST', body: { days: S.ret } }); S.info = 'Deleted: ' + Object.entries(r.deleted).map(([a, n]) => `${a} ${n}`).join(', '); }), 'btn')))));
  }
  // live agent screen
  async function streamGet(path, signal, onEv) {
    const r = await fetch(path, { headers: token ? { Authorization: 'Bearer ' + token } : {}, credentials: 'same-origin', signal });
    if (r.status === 401) { S.auth = true; return; } if (!r.ok) throw new Error('stream failed');
    const rd = r.body.getReader(), dec = new TextDecoder(); let buf = '';
    for (;;) { const { done, value } = await rd.read(); if (done) break; buf += dec.decode(value, { stream: true }); let i; while ((i = buf.indexOf('\n\n')) >= 0) { const chunk = buf.slice(0, i); buf = buf.slice(i + 2); const line = chunk.split('\n').find((l) => l.startsWith('data: ')); if (line) onEv(JSON.parse(line.slice(6))); } }
  }
  const SCREEN_LABEL = { research: 'research', chat: 'asked', reply: 'replied', read: 'read note', write: 'wrote draft', turn: 'council', tool: 'tool', denied: 'blocked' };
  function paintScreen() {
    const el = document.getElementById('screenbody'); if (!el) return;
    el.replaceChildren(...(S.screen.events.length ? S.screen.events.map((e) => h('div', { class: 'sline k-' + e.kind }, h('span', { class: 'mono muted' }, (e.ts || '').slice(11, 19)), h('b', {}, SCREEN_LABEL[e.kind] || e.kind), h('span', {}, e.kind === 'read' || e.kind === 'write' ? `"${e.text}"` : e.text))) : [h('div', { class: 'muted' }, 'Waiting for the agent to do something. Ask a question or start a council call.')]));
    el.scrollTop = el.scrollHeight;
  }
  function stopScreen() { if (S.screen.ctrl) S.screen.ctrl.abort(); S.screen = { bot: '', events: [], ctrl: null, seen: new Set() }; }
  function ensureScreen() {
    const want = S.view === 'chat' && S.panel && S.tab === 'screen' && S.bot && !S.auth;
    if (!want) { if (S.screen.bot) stopScreen(); return; }
    if (S.screen.bot !== S.bot.id) {
      stopScreen(); const ctrl = new AbortController(), id = S.bot.id; S.screen = { bot: id, events: [], ctrl, seen: new Set() };
      (async () => { while (!ctrl.signal.aborted) { try { await streamGet(`/api/bots/${id}/screen/stream`, ctrl.signal, (e) => { const sc = S.screen; if (sc.bot !== id || sc.seen.has(e.id)) return; sc.seen.add(e.id); sc.events = [...sc.events, e].slice(-120); paintScreen(); }); } catch {} if (ctrl.signal.aborted) break; await new Promise((r) => setTimeout(r, 2000)); } })();
    }
    paintScreen();
  }
  // sign-in / first-run setup
  async function submitAuth(kind) {
    const email = (document.getElementById('auth-email') || {}).value || '';
    const password = (document.getElementById('auth-password') || {}).value || '';
    const name = (document.getElementById('auth-name') || {}).value || '';
    const org = (document.getElementById('auth-org') || {}).value || '';
    S.tokenErr = '';
    const body = kind === 'register' ? { email, password, name, org_name: org } : { email, password };
    try {
      const r = await fetch(kind === 'register' ? '/api/auth/register' : '/api/auth/login',
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin', body: JSON.stringify(body) });
      if (!r.ok) { const d = await r.json().catch(() => ({})); S.tokenErr = typeof d.detail === 'string' ? d.detail : 'Sign-in failed'; render(); return; }
      S.auth = false; S.setup = false; token = ''; sessionStorage.removeItem('cfa_token');
      await init();
    } catch (e) { S.tokenErr = e.message; render(); }
  }
  function loginView() {
    if (S.setup) {
      const email = h('input', { class: 'field', id: 'auth-email', type: 'email', placeholder: 'you@company.com', autocomplete: 'email', 'aria-label': 'Email' });
      const name = h('input', { class: 'field', id: 'auth-name', type: 'text', placeholder: 'Your name', autocomplete: 'name', 'aria-label': 'Your name' });
      const org = h('input', { class: 'field', id: 'auth-org', type: 'text', placeholder: 'Organisation (e.g. Acme)', 'aria-label': 'Organisation' });
      const pw = h('input', { class: 'field', id: 'auth-password', type: 'password', placeholder: 'At least 10 characters', autocomplete: 'new-password', 'aria-label': 'Password' });
      [email, name, org, pw].forEach((i) => i.addEventListener('keydown', (e) => { if (e.key === 'Enter') submitAuth('register'); }));
      return h('div', { class: 'login' }, h('div', { class: 'card login-card' }, h('div', { class: 'logo' }, 'Shewiun'),
        h('h2', { style: 'margin-top:18px' }, 'Create your workspace'),
        h('p', { class: 'muted' }, 'This is the first start of this installation. The account you create now owns the organisation.'),
        email, name, org, pw, S.tokenErr ? h('p', { class: 'warn-text', role: 'alert' }, S.tokenErr) : null,
        h('div', { class: 'row2', style: 'margin-top:12px' }, btn('Create workspace', () => submitAuth('register'), 'btn primary')),
        h('p', { class: 'muted', style: 'font-size:12px;margin-top:16px' }, 'Passwords are hashed with Argon2id. Invite teammates later from Settings.')));
    }
    const email = h('input', { class: 'field', id: 'auth-email', type: 'email', placeholder: 'you@company.com', autocomplete: 'username', 'aria-label': 'Email' });
    const pw = h('input', { class: 'field', id: 'auth-password', type: 'password', placeholder: 'Password', autocomplete: 'current-password', 'aria-label': 'Password' });
    [email, pw].forEach((i) => i.addEventListener('keydown', (e) => { if (e.key === 'Enter') submitAuth('login'); }));
    return h('div', { class: 'login' }, h('div', { class: 'card login-card' }, h('div', { class: 'logo' }, 'Shewiun'), h('h2', { style: 'margin-top:18px' }, 'Sign in'), h('p', { class: 'muted' }, 'Use the email address and password of your Shewiun account.'),
      email, pw, S.tokenErr ? h('p', { class: 'warn-text', role: 'alert' }, S.tokenErr) : null, h('div', { class: 'row2', style: 'margin-top:12px' }, btn('Sign in', () => submitAuth('login'), 'btn primary')),
      h('p', { class: 'muted', style: 'font-size:12px;margin-top:16px' }, 'Forgot your password? Ask an admin to send a reset link, or use the API: POST /api/auth/password/forgot.')));
  }
  const logout = async () => { try { await fetch('/api/auth/logout', { method: 'POST', headers: authHeaders('POST'), credentials: 'same-origin' }); } catch {} sessionStorage.removeItem('cfa_token'); token = ''; S.auth = true; location.reload(); };
  const refreshSum = async () => { try { S.sum = await api('/api/summary'); if (S.drawer) render(); } catch {} };
  // menu
  function drawer() {
    const f = S.menuQ.trim().toLowerCase(), badge = (n) => (n ? h('span', { class: 'badge' }, String(n)) : null);
    const it = (label, sub, ic, view, fn, count) => ((f && !(label + ' ' + sub).toLowerCase().includes(f)) ? null : h('button', { class: 'ditem', type: 'button', 'aria-current': S.view === view && !S.modal, onclick: fn || (() => go(view)) }, h('span', { class: 'dicon' }, icon(ic, 18)), h('span', { style: 'flex:1' }, label, h('small', {}, sub)), badge(count)));
    const group = (title, items) => { const real = items.filter(Boolean); return real.length ? [h('h3', {}, title), real] : null; };
    const quick = h('div', { class: 'quick' }, [['New agent', 'plus', openAgent], ['New note', 'doc', () => { S.newNote = true; S.graph = false; go('brain').then(() => { S.newNote = true; S.graph = false; render(); }); }], ['New call', 'council', () => { S.room = null; go('council'); }], ['Upload file', 'up', () => { pickFile(); go('brain'); }]].map(([l, ic, fn]) => h('button', { type: 'button', class: 'qbtn', onclick: fn }, icon(ic, 18), h('span', {}, l))));
    const q = h('input', { class: 'field', placeholder: 'Search the menu', value: S.menuQ, 'aria-label': 'Search the menu' });
    q.addEventListener('input', () => { S.menuQ = q.value; const p = q.selectionStart; render(); const e = document.querySelector('input[aria-label="Search the menu"]'); if (e) { e.focus(); e.setSelectionRange(p, p); } });
    return [h('div', { class: 'dscrim', onclick: () => { S.drawer = false; render(); } }), h('nav', { class: 'drawer', 'aria-label': 'Main menu' },
      h('div', { style: 'display:flex;align-items:center;gap:10px;margin:2px 4px 10px' }, h('div', { class: 'logo', style: 'flex:1' }, 'Shewiun'), h('button', { class: 'ibtn', type: 'button', 'aria-label': 'Close menu', onclick: () => { S.drawer = false; render(); } }, icon('x'))), q, quick,
      h('div', { class: 'm-only' }, h('h3', {}, 'Agents'), S.bots.map((b) => h('button', { class: 'ditem', type: 'button', onclick: () => pick(b.id) }, tile(b, 34), h('span', {}, b.name, h('small', {}, b.role))))),
      group('Workspace', [it('Agents', 'Chat with your team', 'chat', 'chat', () => (S.bot ? pick(S.bot.id) : go('chat')), S.sum.agents), it('Agent screen', 'Watch what an agent does, live', 'panel', 'screen', () => { S.tab = 'screen'; S.panel = true; if (S.bot) pick(S.bot.id); else go('chat'); }), it('Teams', 'Units with shared memory', 'teams', 'teams', null, S.sum.teams), it('Council', 'Live call, decision and plan', 'council', 'council'), it('Brain', 'Neurons, notes and files', 'graph', 'brain', null, S.sum.drafts), it('Research', 'Deep search with citations and charts', 'lens', 'research')]),
      group('Govern', [it('Control', 'Approvals, tool calls, audit, incident switch', 'shield', 'control', null, S.sum.pending_approvals), it('Inventory', 'Every agent, its owner, sponsor and risk', 'table', 'inventory', null, S.sum.agents), it('Models & usage', 'Providers, tokens, costs, budget', 'chart', 'usage'), it('Self-test', 'Prove the boundaries, share the evidence', 'flask', 'control'), it('OWASP coverage', 'What is covered, what is not', 'check', 'control')]),
      group('Connect', [it('Apps', 'Live MCP servers and a demo catalog', 'grid', 'apps', openApps, S.sum.apps), it('Marketplace', 'Curated agents and Hugging Face', 'store', 'market')]),
      group('Playbooks', [(f && !'agent launch review go or no-go'.includes(f)) ? null : h('a', { class: 'ditem', href: '/review/agent-launch' }, h('span', { class: 'dicon' }, icon('doc', 18)), h('span', {}, 'Agent launch review', h('small', {}, 'Go or no-go for an AI agent')))]),
      group('Account', [it('Plans & usage', 'Limits, upgrade, billing', 'chart', 'plans', null, S.bill && S.bill.enabled ? S.bill.plan_name : null), it('Settings', 'Models, access keys, backups', 'wrench', 'settings'), it('Load demo workspace', 'Sample agents, notes, teams and apps', 'spark', 'x', loadDemo)]),
      h('p', { class: 'muted', style: 'font-size:12px;margin:18px 10px' }, `Shewiun v${S.health.version || '?'}${S.health.build ? ' · build ' + S.health.build : ''}`))];
  }
  function render() {
    stopSim(); hideHover();
    if (S.auth) { stopScreen(); root.replaceChildren(loginView()); return; } const hd = S.health, groups = [...new Set(S.bots.map((b) => b.team))];
    const side = h('aside', { class: 'side' },
      h('div', { class: 'side-top' }, h('button', { class: 'ibtn', type: 'button', 'aria-label': 'Menu', 'aria-expanded': S.drawer, onclick: () => { S.drawer = !S.drawer; render(); if (S.drawer) refreshSum(); } }, icon('menu')), h('div', { class: 'logo' }, 'Shewiun'), h('span', { class: 'sp' }),
        h('button', { class: 'ibtn', type: 'button', 'aria-label': 'Search notes', onclick: () => go('brain') }, icon('search')), h('button', { class: 'ibtn', type: 'button', 'aria-label': 'New agent', onclick: openAgent }, icon('plus'))),
      h('div', { class: 'agents' }, groups.map((g) => [h('div', { class: 'group' }, g), S.bots.filter((b) => b.team === g).map((b) => h('button', { class: 'agent', type: 'button', 'aria-current': S.view === 'chat' && S.bot && S.bot.id === b.id ? 'true' : false, onclick: () => pick(b.id) }, tile(b, 38), h('span', {}, h('b', {}, b.name), h('small', {}, b.status === 'suspended' ? 'suspended' : b.preview || b.role))))])),
      meterBlock(),
      h('button', { class: 'appsbtn', type: 'button', onclick: openApps }, icon('grid', 20), h('span', { style: 'flex:1' }, 'Connect apps', h('small', {}, `${S.sum.apps || 0} connected · MCP`)), h('span', { class: 'chip ok' }, 'MCP')),
      h('div', { style: 'position:relative' }, S.menu ? h('div', { class: 'pop', role: 'menu' }, btn([icon('chart', 16), 'Plans & usage'], () => go('plans'), 'menuitem'), btn([icon('wrench', 16), 'Settings'], () => go('settings'), 'menuitem'), btn([icon('flask', 16), 'Authorization self-test'], () => go('control'), 'menuitem'), btn([icon('table', 16), 'Agent inventory'], () => go('inventory'), 'menuitem'), btn([icon('grid', 16), 'Apps'], openApps, 'menuitem'),
        btn([icon('spark', 16), 'Load demo workspace'], loadDemo, 'menuitem'), btn([icon('x', 16), 'Sign out'], logout, 'menuitem')) : null,
        h('button', { class: 'acct', type: 'button', 'aria-expanded': S.menu, onclick: () => { S.menu = !S.menu; render(); } }, h('span', { class: 'tile', style: 'width:34px;height:34px;background:var(--accent);color:var(--on-accent)' }, icon('user', 18)),
          h('span', {}, (S.me && S.me.org ? S.me.org.name : 'Workspace owner'), h('small', {}, S.me && S.me.user ? S.me.user.email + ' · ' + S.me.role : (hd.auth === 'enabled' ? 'Signed in' : 'Open dev mode, no login')), h('small', {}, hd.model_configured ? 'Model connected' : 'No model, demo replies'), h('small', {}, `v${hd.version || '?'}${hd.build ? ' · ' + hd.build : ''}`)))));
    const view = { chat: chatView, council: councilView, brain: brainView, research: researchView, teams: teamsView, inventory: inventoryView, usage: usageView, market: marketView, control: controlView, plans: plansView, settings: settingsView }[S.view]();
    const hasPanel = S.view === 'chat' && S.panel && S.bot, warn = (hd.warnings || []).length && S.view === 'chat' && !S.err && !S.info;
    root.replaceChildren(h('div', { class: 'shell' + (hasPanel ? ' has-panel' : '') }, side,
      h('main', { class: 'main' }, mobileBar(), S.err && !S.modal ? h('div', { class: 'banner', role: 'alert', style: 'color:var(--bad)' }, S.err) : null, S.info && !S.err ? h('div', { class: 'banner', role: 'status' }, S.info) : null,
        warn ? h('div', { class: 'banner', title: hd.warnings.join('\n') }, `${hd.warnings.length} setup warning(s): ${hd.warnings[0]}`) : null, view), hasPanel ? passport() : null),
      ...(S.drawer ? drawer() : []), S.modal === 'apps' ? appsModal() : null, S.modal === 'agent' ? agentModal() : null, S.modal === 'onboard' ? onboardModal() : null, S.modal === 'upsell' ? upsellModal() : null, S.modal === 'lead' ? leadModal() : null);
    const sc = document.getElementById('scroll'); if (sc) sc.scrollTop = sc.scrollHeight;
    ensureScreen();
  }
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { if (S.modal) close(); else if (S.drawer) { S.drawer = false; render(); } } });
  async function init() {
    S.err = '';
    try {
      const st = await api('/api/auth/status');
      S.setup = !!st.setup_required;
      if (st.auth_required) { S.me = await api('/api/auth/me').catch(() => null); }
    } catch (e) { S.err = e.message; }
    try { S.health = await api('/api/health'); } catch (e) { S.err = e.message; }
    if (S.auth) { render(); return; }
    try {
      S.bots = await api('/api/bots'); S.bot = S.bots[0]; const t = await api('/api/templates'); S.caps = (t.find((x) => x.capabilities) || {}).capabilities || [];
      S.msgs = await api(`/api/bots/${S.bot.id}/messages`); await Promise.all([loadNotes(), loadApps(), loadTeams(), api('/api/calls').then((c) => { S.calls = c; }), api('/api/selftest/latest').then((x) => { S.test = x; }), api('/api/summary').then((x) => { S.sum = x; }), api('/api/billing').then((x) => { S.bill = x; }), api('/api/onboarding').then((x) => { S.onb = x; }), api('/api/presets').then((x) => { S.presets = x; })]);
    } catch (e) { if (S.auth) { S.err = ''; S.tokenErr = S.setup ? '' : 'Please sign in again.'; } else S.err = e.message; }
    if (S.onb && S.onb.suggest && !S.skipOnb && S.bots.length <= 4 && !S.auth) S.modal = 'onboard';
    if (/billing=success/.test(location.search)) { S.info = 'Thank you! Your plan updates in a few seconds.'; setTimeout(() => api('/api/billing').then((x) => { S.bill = x; render(); }).catch(() => {}), 3500); }
    render();
  }
  init();
})();
