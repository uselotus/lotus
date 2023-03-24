while ! nc -q 1 db 5432 </dev/null; do sleep 5; done

MAX_TRIES=30
COUNT=0
while ! nc -q 1 svix-server 8071 </dev/null; do
  if [ $COUNT -eq $MAX_TRIES ]; then
    echo "Timeout waiting for svix-server."
    exit 1
  fi
  sleep 5
  COUNT=$((COUNT+1))
done



python3 manage.py wait_for_db && \
python3 manage.py migrate && \
python3 manage.py initadmin && \
python3 manage.py demo_up && \
python3 manage.py setup_tasks && \
python3 manage.py runserver 0.0.0.0:8000
