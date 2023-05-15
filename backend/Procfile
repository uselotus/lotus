release: chmod u+x ./scripts/release.sh && ./scripts/release.sh
web: gunicorn lotus.wsgi:application -w 4 --threads 4 --preload
web2: gunicorn lotus.wsgi:application -b 0.0.0.0 -w 4 --threads 4 --preload
worker: celery -A lotus worker -l info --without-gossip --without-mingle --without-heartbeat --concurrency=4
beat: celery -A lotus beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
events: python3 manage.py event_consumer
