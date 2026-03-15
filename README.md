# RecordApp Backend

API REST para el sistema de recordatorios inteligentes por WhatsApp.

## Stack

- **FastAPI** + Uvicorn
- **PostgreSQL** (async via asyncpg)
- **SQLAlchemy 2.0** (async ORM)
- **Alembic** (migraciones)
- **Celery + Redis** (task queue — Ciclo 3)
- **WhatsApp Cloud API** (envío de mensajes)

## Setup local

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt

# Copiar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales

# Correr migraciones
alembic upgrade head

# Iniciar servidor
uvicorn app.main:app --reload --port 8000
```

## Endpoints

Documentación interactiva en: `http://localhost:8000/docs`

## Deploy (Railway)

1. Conectar repo en Railway
2. Agregar PostgreSQL addon
3. Configurar variables de entorno desde `.env.example`
4. Deploy automático desde `main`

## Mantenimiento (admin)

- Limpiar resultados/tareas terminadas de Celery en Redis (script en `app/scripts/purge_celery_results.py`):

	```bash
	# Ver cuántas claves coinciden (sin borrar)
	python -m app.scripts.purge_celery_results --dry-run

	# Borrar claves celery-task-meta-* (usa REDIS_URL de settings)
	python -m app.scripts.purge_celery_results

	# Otro patrón
	python -m app.scripts.purge_celery_results --pattern "celery-taskset-meta-*"
	```
