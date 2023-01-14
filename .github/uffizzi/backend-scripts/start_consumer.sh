while ! nc -q 1 0.0.0.0 5432 </dev/null; do sleep 5; done

python3 manage.py event_consumer