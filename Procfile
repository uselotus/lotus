release: chmod u+x build.sh && ./build.sh
web: gunicorn lotus.wsgi
worker: celery -A lotus worker -l info
beat: celery -A lotus beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
