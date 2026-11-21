# Munshi Guard

Voice-first supplier accountability for kirana shops.

## Run it on your computer
1. python -m venv .venv
2. Windows: .venv\Scripts\activate    |    Mac: source .venv/bin/activate
3. pip install -r requirements.txt
4. Windows: copy .env.example .env    |    Mac: cp .env.example .env   (then fill in your keys)
5. uvicorn app.main:app --reload
6. Open http://127.0.0.1:8000/health  -> {"status":"ok"}

## Rules
- Never commit .env or any real key.
- Only edit your own folders. Run "git pull" before "git push".
