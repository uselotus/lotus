# lotus backend

## How to build

Dependencies requirements:
- python3-devel
- libpq-devel (pg_config)
- poetry

1. Generate the wheel
```
poetry build
```

2. Create a dedicated venv for lotus

```
python3 -mvenv ~/.venv/lotus
source ~/.venv/lotus/bin/activate
```

3. Install the wheel

``` 
pip install dist/lotus_backend-0.9.1-py3-none-any.whl
```

## How to call the backend

Once your lotus environment is active and the wheel installed.

``` 
lotus_backend
```

available options are:
- event_consumer
- wait_for_db
- migrate
- demo_up
- initadmin
- setup_tasks
- runserver <IP>:<PORT>
