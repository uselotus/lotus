release: chmod u+x release.sh && ./release.sh
web: gunicorn lotus.lotus.wsgi
worker: celery -A lotus.lotus worker -l info
beat: celery -A lotus.lotus beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
