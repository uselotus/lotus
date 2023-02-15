while ! nc -q 1 db 5432 </dev/null; do sleep 5; done
while ! nc -q 1 svix-server 8071 </dev/null; do sleep 5; done

lotus_backend wait_for_db && \
lotus_backend migrate && \
lotus_backend initadmin && \
lotus_backend setup_tasks && \
lotus_backend collectstatic --no-input && \
gunicorn lotus.wsgi:application -w 4 --threads 4 -b :8000 --reload
