while ! nc -q 1 db 5432 </dev/null; do sleep 5; done
while ! nc -q 1 svix-server 8071 </dev/null; do sleep 5; done

python3 manage.py wait_for_db && \
python3 manage.py migrate && \
python3 manage.py demo_up && \
python3 manage.py djstripe_sync_models && \
python3 manage.py initadmin && \
python3 manage.py setup_tasks && \
python3 manage.py runserver 0.0.0.0:8000