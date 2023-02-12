while ! nc -q 1 db 5432 </dev/null; do sleep 5; done
while ! nc -q 1 svix-server 8071 </dev/null; do sleep 5; done

python3 lotus_backend wait_for_db && \
python3 lotus_backend migrate && \
python3 lotus_backend demo_up && \
python3 lotus_backend initadmin && \
python3 lotus_backend setup_tasks && \
python3 lotus_backend runserver 0.0.0.0:8000
