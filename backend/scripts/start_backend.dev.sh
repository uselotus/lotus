while ! nc -q 1 db 5432 </dev/null; do sleep 5; done
while ! nc -q 1 svix-server 8071 </dev/null; do sleep 5; done

lotus_backend wait_for_db && \
lotus_backend migrate && \
lotus_backend demo_up && \
lotus_backend initadmin && \
lotus_backend setup_tasks && \
lotus_backend runserver 0.0.0.0:8000
