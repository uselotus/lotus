# ---------------------------------------
# Build
# ---------------------------------------
FROM python:3.9 AS build
ENV PYTHONUNBUFFERED 1
#make lotus user
WORKDIR /lotus
# pip install optimization
RUN apt-get update && apt-get install -y netcat
COPY Pipfile Pipfile.lock ./
RUN pip install -U --no-cache-dir --disable-pip-version-check pipenv
RUN pipenv install --system --deploy --ignore-pipfile --dev
# copy python files,
COPY ./lotus/ ./lotus/
COPY ./metering_billing/ ./metering_billing/
COPY ./manage.py ./
# ---------------------------------------
# Development
# ---------------------------------------
FROM build AS development
COPY ./pytest.ini ./.coveragerc ./
COPY ./scripts/start_backend.dev.sh ./scripts/start_backend.dev.sh
COPY ./scripts/start_consumer.sh ./scripts/start_consumer.sh
RUN chmod +x ./scripts/start_backend.dev.sh
RUN chmod +x ./scripts/start_consumer.sh

# ---------------------------------------
# Production
# ---------------------------------------
FROM build AS production 
COPY ./scripts/start_backend.prod.sh ./scripts/start_backend.prod.sh
COPY ./scripts/start_consumer.sh ./scripts/start_consumer.sh
RUN chmod +x ./scripts/start_backend.prod.sh
RUN chmod +x ./scripts/start_consumer.sh