# Railway / Heroku Procfile
# Cada línea es un tipo de proceso separado.
# En Railway: crear 3 servicios apuntando al mismo repo, cada uno con su Start Command.

web:    uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
worker: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2
beat:   celery -A app.tasks.celery_app beat --loglevel=info
