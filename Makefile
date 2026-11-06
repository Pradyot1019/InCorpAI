.PHONY: up ingest api web test
up:      ; docker compose up --build -d db api web && docker compose run --rm ingest
ingest:  ; cd backend && python ingest.py ../corpus
api:     ; cd backend && uvicorn main:app --reload --port 8000
web:     ; cd frontend && npm run dev
test:    ; cd backend && pytest -q && cd ../frontend && npm run typecheck
