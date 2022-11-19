python3 manage.py wait_for_db && \
python3 manage.py migrate && \
python3 manage.py djstripe_sync_models && \
python3 manage.py setup_tasks && \
python3 manage.py event_consumer