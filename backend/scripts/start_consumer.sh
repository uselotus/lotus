while ! nc -q 1 db 5432 </dev/null; do sleep 5; done

lotus_backend event_consumer
