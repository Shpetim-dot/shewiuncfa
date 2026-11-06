# Deploying on Vercel (Python)

## The 500 `ModuleNotFoundError: No module named 'app'`

That error means the function ran with `main.py` in `/var/task` but the `app/` package was not in
the deployment. The repository is fine; the upload was incomplete (or the old root-level function
config was used).

## Correct setup in this repository

```
api/index.py        # Vercel entrypoint, exports `app`
app/                # the application package (must be deployed!)
vercel.json         # function config + rewrite of every path to the function
```

`vercel.json`:

* `functions["api/index.py"].includeFiles = "**/*"` forces the whole tree into the bundle,
  including `app/`, `app/static/` and `app/playbooks/`.
* `rewrites` sends every request (HTML, API, `/review/agent-launch`) to the function, so the
  FastAPI app keeps serving its own static files.

## Deploy checklist

1. `git ls-files app | wc -l` must be > 0 (about 30 files). If it is 0, the folder was never
   committed — `git add app` and push.
2. `git ls-files api/index.py vercel.json` must list both files.
3. In Vercel: *Settings → General → Root Directory* = repository root (not a subfolder),
   Framework Preset = **Other**, no build command, output directory empty.
4. Redeploy without build cache ("Redeploy" → uncheck *use existing build cache*).
5. Check `https://<deployment>/api/health` → `{"status":"ok",...}`.

## Environment variables (minimum)

```
CFA_ENV=production
CFA_ALLOW_SIGNUP=1          # first start only, then 0
CFA_SECRET_KEY=<fernet key>
CFA_API_KEYS=               # optional legacy keys
CFA_MODEL_API_KEY=...       # or ANTHROPIC_API_KEY / GEMINI_API_KEY
STRIPE_*=...                # only if you sell through Stripe
```

## Known Vercel limits

* The filesystem is read-only except `/tmp`; `app/main.py` already redirects the SQLite file to
  `/tmp/cfa.db`. **Data is lost on cold starts** — Vercel is a demo/showcase host, not production.
* One function, one SQLite file: no background worker survives a request. Runtime runs will only
  complete while an instance is warm.
* For real data use the Docker image with a volume (Fly, Render, any VM).

## Local smoke test of the entrypoint

```
python -c "import importlib.util as u, os; s=u.spec_from_file_location('e','api/index.py'); m=u.module_from_spec(s); s.loader.exec_module(m); print(len(m.app.routes))"
```
