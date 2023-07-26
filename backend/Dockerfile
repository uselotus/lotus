# ---------------------------------------
# Build
# ---------------------------------------
FROM python:3.9 AS build
ENV PYTHONUNBUFFERED 1
WORKDIR /lotus
# pip install optimization
RUN apt-get update && apt-get install -y netcat-openbsd
COPY pyproject.toml poetry.lock ./
RUN pip install --no-cache-dir --disable-pip-version-check poetry
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi
COPY ./lotus/ ./lotus/
COPY ./metering_billing/ ./metering_billing/
COPY ./api/ ./api/
COPY ./manage.py ./
# ---------------------------------------
# Development
# ---------------------------------------
FROM build AS development
COPY ./pytest.ini ./.coveragerc ./
COPY ./scripts/start_backend.dev.sh ./scripts/start_backend.dev.sh
RUN chmod +x ./scripts/start_backend.dev.sh
# ---------------------------------------
# Production
# ---------------------------------------
FROM build AS production
COPY ./scripts/start_backend.prod.sh ./scripts/start_backend.prod.sh
RUN chmod +x ./scripts/start_backend.prod.sh
