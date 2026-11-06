(async () => {
  const app = document.getElementById('app');
  const SECRET = /(sk-[a-z0-9_-]{16,}|AKIA[0-9A-Z]{12,}|eyJ[a-zA-Z0-9_-]{20,}\.|-----BEGIN [A-Z ]*PRIVATE KEY|api[_-]?key\s*[:=]\s*\S{8,})/i;
  const TRI = [['yes', 'Yes'], ['no', 'No'], ['unknown', "I don't know"]];
  const VERDICT = { 'go': 'Go', 'conditional-go': 'Conditional go', 'no-go': 'No-go' };
  const BOT = '<svg width="32" height="32" viewBox="0 0 32 32" aria-hidden="true"><rect x="3" y="5" width="26" height="22" rx="8" fill="var(--accent)"/><circle cx="12" cy="15" r="2.6" fill="#fff"/><circle cx="20" cy="15" r="2.6" fill="#fff"/></svg>';

  // All dynamic text goes through textContent; no user or server text is parsed as HTML.
  const h = (tag, attrs = {}, ...kids) => {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === 'class') el.className = v; else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else if (v === true) el.setAttribute(k, ''); else if (v !== false && v != null) el.setAttribute(k, v);
    }
    for (const kid of kids.flat()) if (kid != null) el.append(kid);
    return el;
  };
  const head = () => { const d = h('div', { class: 'al-head' }, h('h1', {}, 'Agent launch review')); d.insertAdjacentHTML('afterbegin', BOT); return d; };
  const fail = (msg) => app.replaceChildren(head(), h('p', { class: 'al-warn', role: 'alert' }, msg));

  let playbook;
  try {
    const r = await fetch('/api/playbooks/agent-launch');
    if (!r.ok) throw new Error();
    playbook = await r.json();
  } catch { return fail('The questionnaire could not be loaded. Reload the page to try again.'); }

  const steps = playbook.steps; const a = {}; let i = 0;
  const filled = (q) => q.optional || (Array.isArray(a[q.id]) ? a[q.id].length > 0 : Boolean(a[q.id]));
  const secret = () => typeof a.purpose === 'string' && SECRET.test(a.purpose);

  function question(q) {
    if (q.type === 'text') {
      const warn = h('p', { class: 'al-warn', role: 'alert', hidden: true }, 'This looks like a key or token. Remove it before continuing.');
      const ta = h('textarea', { id: q.id, maxlength: 500 }); ta.value = a[q.id] || '';
      ta.addEventListener('input', () => { a[q.id] = ta.value; warn.hidden = !secret(); nav(); });
      warn.hidden = !secret();
      return h('fieldset', { class: 'al-q' }, h('label', { for: q.id }, q.label + (q.optional ? ' (optional)' : '')),
        q.hint ? h('p', { class: 'al-hint' }, q.hint) : null, ta, warn);
    }
    const multi = q.type === 'multi';
    const opts = (q.type === 'tri' ? TRI : q.options).map(([v, l]) => {
      const input = h('input', { type: multi ? 'checkbox' : 'radio', name: q.id, value: v });
      input.checked = multi ? (a[q.id] || []).includes(v) : a[q.id] === v;
      input.addEventListener('change', () => {
        if (!multi) a[q.id] = v; else {
          const cur = a[q.id] || [];
          a[q.id] = v === 'none' ? (cur.includes('none') ? [] : ['none'])
            : cur.includes(v) ? cur.filter((x) => x !== v) : [...cur.filter((x) => x !== 'none'), v];
          render(); // keeps "none" exclusive and re-syncs checkboxes
          return;
        }
        nav();
      });
      return h('label', { class: 'al-opt' }, input, h('span', {}, l));
    });
    return h('fieldset', { class: 'al-q' }, h('legend', {}, q.label), h('div', { class: 'al-opts' }, opts));
  }

  let navEl;
  function nav() {
    const last = i === steps.length - 1;
    const ok = steps[i].questions.every(filled) && !secret();
    const next = h('button', { class: 'al-btn primary', type: 'button', disabled: !ok, onclick: last ? submit : () => { i++; render(); } }, last ? 'Show review' : 'Next');
    navEl.replaceChildren(h('button', { class: 'al-btn', type: 'button', disabled: i === 0, onclick: () => { i--; render(); } }, 'Back'), next);
  }

  function render() {
    navEl = h('div', { class: 'al-nav' });
    const tabs = h('nav', { class: 'al-steps', 'aria-label': 'Steps' }, steps.map((s, n) =>
      h('button', { type: 'button', 'aria-current': n === i ? 'step' : false, onclick: () => { if (n <= i) { i = n; render(); } } }, s.title)));
    app.replaceChildren(head(),
      h('p', { class: 'al-sub' }, 'Answer a few questions about the agent you plan to launch. You get a go or no-go with the controls to fix first.'),
      tabs, ...steps[i].questions.map(question), navEl);
    nav();
  }

  async function submit() {
    const body = { ...a }; if (!body.purpose) delete body.purpose;
    let r;
    try { r = await fetch('/api/reviews/agent-launch', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); }
    catch { return fail('The review could not be created. Check your connection and try again.'); }
    if (!r.ok) return fail(r.status === 422 ? 'Some answers were not accepted. Go back and check the free-text field for keys or tokens.' : 'The review could not be created. Try again in a moment.');
    show(await r.json());
  }

  function show(res) {
    const sev = (s) => s[0].toUpperCase() + s.slice(1);
    app.replaceChildren(head(),
      h('p', { class: 'al-verdict' }, VERDICT[res.verdict]),
      h('p', { class: 'al-sub' }, `${res.findings.length} finding${res.findings.length === 1 ? '' : 's'} from your answers.`),
      h('p', { class: 'al-disc' }, res.disclaimer),
      res.findings.map((f) => h('section', { class: 'al-f' },
        h('h3', {}, h('span', { class: 'al-sev ' + f.severity }, sev(f.severity)), f.title,
          f.basis === 'unknown' ? h('span', { class: 'al-assumed' }, 'Assumed: unanswered or "I don\'t know"') : null),
        h('p', {}, f.why), h('p', {}, h('strong', {}, 'Fix: '), f.fix))),
      h('div', { class: 'al-nav' }, h('button', { class: 'al-btn', type: 'button', onclick: () => { i = 0; render(); } }, 'Edit answers')));
  }
  render();
})();
