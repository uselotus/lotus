python3 manage.py wait_for_db && \
python3 manage.py migrate && \
python3 manage.py initadmin && \
python3 manage.py demo_up && \
python3 manage.py setup_tasks && \
python3 manage.py runserver 0.0.0.0:8000