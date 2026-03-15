"""
Limpia resultados/tareas terminadas de Celery en Redis.
Uso:
    python -m app.scripts.purge_celery_results
Opciones:
    --pattern PAT   Patrón a borrar (default: celery-task-meta-*)
    --dry-run       Solo lista cuántas claves coinciden, no borra.
"""
import argparse

import redis

from app.core.config import get_settings


def purge(pattern: str, dry_run: bool = False) -> tuple[int, list[str]]:
    settings = get_settings()
    r = redis.from_url(settings.REDIS_URL)
    keys = list(r.scan_iter(match=pattern))
    if dry_run:
        return len(keys), []
    deleted = 0
    deleted_keys = []
    if keys:
        deleted = r.delete(*keys)
        deleted_keys = [k.decode() if isinstance(k, bytes) else k for k in keys]
    return deleted, deleted_keys


def main():
    parser = argparse.ArgumentParser(description="Purge Celery result keys from Redis")
    parser.add_argument("--pattern", default="celery-task-meta-*", help="Pattern to match (default: celery-task-meta-*)")
    parser.add_argument("--dry-run", action="store_true", help="Only count keys, do not delete")
    args = parser.parse_args()

    count, keys = purge(args.pattern, args.dry_run)
    if args.dry_run:
        print(f"Dry-run: {count} keys would be deleted (pattern={args.pattern})")
    else:
        print(f"Deleted {count} keys (pattern={args.pattern})")
        if count > 0:
            print("Sample:")
            for k in keys[:5]:
                print(f" - {k}")


if __name__ == "__main__":
    main()
