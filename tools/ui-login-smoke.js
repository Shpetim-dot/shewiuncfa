// Sign-in smoke test. Start the app on port 8771 with CFA_API_KEYS=adm-token:admin:Alice, then: node tools/ui-login-smoke.js

const { JSDOM, VirtualConsole } = require('jsdom');
const errs = []; const vc = new VirtualConsole(); vc.on('jsdomError', (e) => errs.push(e.detail || e.message));
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const dom = await JSDOM.fromURL('http://localhost:8771/', { runScripts: 'dangerously', resources: 'usable', pretendToBeVisual: true, virtualConsole: vc, beforeParse(win) { win.fetch = (u, o) => fetch(new URL(u, 'http://localhost:8771').href, { ...o, signal: undefined }); win.TextDecoder = TextDecoder; } });
  const w = dom.window, d = w.document; await wait(1500);
  const ok = (c, m) => console.log((c ? 'PASS ' : 'FAIL ') + m);
  ok(!!d.querySelector('.login') && d.body.textContent.includes('Sign in'), 'sign-in screen instead of a dead page');
  const inp = d.querySelector('input[type=password]'); inp.value = 'wrong'; [...d.querySelectorAll('button')].find((b) => b.textContent === 'Sign in').click(); await wait(1200);
  ok(d.body.textContent.includes('That token was not accepted.'), 'wrong token message');
  const inp2 = d.querySelector('input[type=password]'); inp2.value = 'adm-token'; [...d.querySelectorAll('button')].find((b) => b.textContent === 'Sign in').click(); await wait(1800);
  ok(d.querySelectorAll('.agent').length >= 4 && !d.querySelector('.login'), 'agents visible after sign-in: ' + d.querySelectorAll('.agent').length);
  console.log(errs.length ? 'ERRORS ' + errs.join('|') : 'NO RUNTIME ERRORS'); process.exit(0);
})().catch((e) => { console.log('SCRIPT FAIL', e.message); process.exit(1); });
