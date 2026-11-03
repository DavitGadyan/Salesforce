.PHONY: setup api web test seed

setup:            ## install backend + frontend dependencies
	cd api && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd web && npm install
	test -f api/.env || cp api/.env.example api/.env

api:              ## FastAPI on :8000
	cd api && .venv/bin/uvicorn app.main:app --reload --port 8000

web:              ## Next.js on :3210 (proxies /api to :8000)
	cd web && npx next dev -p 3210

test:
	cd api && .venv/bin/python -m pytest -q

seed:             ## regenerate demo_data/*.json (deterministic)
	cd api && .venv/bin/python scripts/gen_demo_data.py
