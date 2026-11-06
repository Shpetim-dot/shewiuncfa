
## v7 additions
Set `CFA_SECRET_KEY` (a Fernet key: `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`) before adding providers. Optional: `CFA_APPROVAL_TTL_MINUTES`, `CFA_EMBEDDING_MODEL` (then run `POST /api/brain/reindex`). Computer use stays off; see KNOWN_LIMITATIONS.md.

## Vercel
The entrypoint is the root `main.py` (it re-exports `app.main:app`). In the Vercel project settings, **Root Directory must be the repository root** (the folder that contains `app/`, `static/` and `requirements.txt`), not `app/`. Never name a module after a Python standard-library module (`platform`, `uuid`, `json` ...): a file called `platform.py` next to the entrypoint shadows the standard one and the function fails at import. Data on Vercel lives in `/tmp` and is lost on cold starts: demo only.
Both folder layouts start: the normal one (`app/` package, `static/`, root `main.py`) and a flat one (all `.py` files, `static/` and `requirements.txt` directly in the deploy root); the flat case registers the folder as package `app` itself. If `static/` is missing the page answers 503 with an explanation instead of crashing.
