// v6 UI smoke test (presets, plans, settings, monitor, upsell). Start the app on port 8772 with CFA_BILLING=on CFA_DEMO_DELAY=0.1 and a fresh database, then: node tools/ui-smoke-v6.js
const { JSDOM, VirtualConsole } = require('jsdom');
const errs = []; const vc = new VirtualConsole(); vc.on('jsdomError', (e) => errs.push('jsdomError: ' + (e.detail || e.message))); vc.on('error', (e) => errs.push('console.error: ' + e));
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const B = 'http://localhost:8772';
(async () => {
  const dom = await JSDOM.fromURL(B + '/', { runScripts: 'dangerously', resources: 'usable', pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(win) { win.fetch = (u, o) => fetch(new URL(u, B).href, { ...o, signal: undefined }); win.TextDecoder = TextDecoder; win.URL.createObjectURL = () => 'blob:x'; } });
  const w = dom.window, d = w.document; const q = (s) => d.querySelector(s), qa = (s) => [...d.querySelectorAll(s)];
  const clickText = (sel, t) => { const el = qa(sel).find((e) => e.textContent.includes(t)); if (!el) throw new Error('missing ' + sel + ' ' + t); el.click(); };
  const menu = async (t) => { q('button[aria-label="Menu"]').click(); await wait(80); clickText('.drawer > .ditem', t); };
  const ok = (c, m) => console.log((c ? 'PASS ' : 'FAIL ') + m);
  await wait(1800);
  ok(!!q('.wizard') && qa('.preset').length >= 9, 'first-run wizard with presets: ' + qa('.preset').length);
  ok(qa('.wizard svg.av').length >= 20 && qa('.wizard svg.av polygon, .wizard svg.av rect, .wizard svg.av circle').length > 20, 'faceted avatars drawn: ' + qa('.wizard svg.av').length);
  const dev = qa('.preset').find((e) => e.textContent.includes('Developer')); [...dev.querySelectorAll('button')].find((b) => b.textContent === 'Use this preset').click(); await wait(2500);
  ok(!q('.wizard') && qa('.agent b').some((e) => e.textContent === 'Code Reviewer'), 'preset applied: ' + qa('.agent b').map((e) => e.textContent).join(','));
  ok(d.body.textContent.includes('Preset ready'), 'preset banner');
  ok(!!q('.meter') && q('.meter').textContent.includes('Free plan') && !!q('.appsbtn') && q('.appsbtn').textContent.includes('Connect apps') && !!q('.mbar'), 'plan meter + Connect apps CTA + mobile bar');
  ok(!!q('.bar svg.av.float'), 'header avatar floats');
  await menu('Plans'); await wait(900);
  ok(qa('.plan').length === 4 && d.body.textContent.includes('Usage this month') && d.body.textContent.includes('Current plan'), 'plans view: ' + qa('.plan').length);
  await menu('Settings'); await wait(1200);
  ok(['Readiness', 'Models', 'Access keys', 'Backups and data'].every((t) => d.body.textContent.includes(t)), 'settings sections');
  clickText('button', 'Test connection'); await wait(800);
  ok(d.body.textContent.includes('Not working') || d.body.textContent.includes('OK:'), 'model test shows a result');
  await menu('Council'); await wait(800); clickText('button', 'Code review session'); await wait(200);
  ok(qa('textarea')[0].value.startsWith('Review this change'), 'code review topic prefilled');
  clickText('button', 'Start call'); await wait(900);
  ok(qa('.ptile').length === 4, 'coding review board in the live room: ' + qa('.ptile').length);
  await wait(5500);
  await menu('Research'); await wait(900);
  const rq = q('textarea'); rq.value = 'How should code review boards handle security findings?'; rq.dispatchEvent(new w.Event('input')); clickText('button', 'Start research'); await wait(700);
  ok(!!q('.monitor') && !!q('.monitor .progress'), 'research live monitor');
  await wait(4500);
  ok(q('.monitor').textContent.includes('DONE') || q('.monitor').textContent.includes('finished'), 'monitor finished');
  await menu('Apps'); await wait(900);
  ok(qa('.modal .appcard .lbox').length === 9, 'app logo boxes: ' + qa('.modal .appcard .lbox').length + ' with images ' + qa('.modal .lbox img').length);
  q('button[aria-label="Close"]').click(); await wait(100);
  // exhaust the free message limit through the API, then hit it from the UI
  const bots = await (await fetch(B + '/api/bots')).json(); const id = bots[0].id;
  for (let i = 0; i < 50; i++) { const r = await fetch(B + `/api/bots/${id}/messages`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: 'fill ' + i }) }); if (r.status === 402) break; }
  const pickBtn = qa('.agent').find((e) => e.textContent.includes(bots[0].name)); pickBtn.click(); await wait(800);
  const ta = q('.composer textarea'); ta.value = 'one more please'; ta.dispatchEvent(new w.Event('input')); q('.send').click(); await wait(1200);
  ok(!!q('[aria-label="Plan limit reached"]') && d.body.textContent.includes('See plans'), 'upsell modal at the plan limit');
  console.log(errs.length ? 'ERRORS:\n' + errs.join('\n') : 'NO RUNTIME ERRORS'); process.exit(0);
})().catch((e) => { console.log('SCRIPT FAIL', e.message); console.log(errs.join('\n')); process.exit(1); });
