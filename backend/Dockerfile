# ---------------------------------------
# Build
# ---------------------------------------
FROM python:3.9 AS build
ENV PYTHONUNBUFFERED 1
#make lotus user
WORKDIR /lotus
# pip install optimization
COPY pyproject.toml poetry.lock ./
# copy python files,
COPY ./src ./src
RUN apt-get update && apt-get install -y netcat
RUN pip install -U --no-cache-dir --disable-pip-version-check poetry wheel
RUN poetry build
# ---------------------------------------
# Development
# ---------------------------------------
FROM build AS development
COPY ./pytest.ini ./.coveragerc ./
COPY ./scripts/start_backend.dev.sh ./scripts/start_backend.dev.sh
COPY ./scripts/start_consumer.sh ./scripts/start_consumer.sh
RUN pip install dist/lotus_backend-0.9.1-py3-none-any.whl
RUN chmod +x ./scripts/start_backend.dev.sh
RUN chmod +x ./scripts/start_consumer.sh

# ---------------------------------------
# Production
# ---------------------------------------
FROM python:3.9 AS production
ENV PYTHONUNBUFFERED 1
#make lotus user
WORKDIR /lotus
COPY ./scripts/start_backend.prod.sh ./scripts/start_backend.prod.sh
COPY ./scripts/start_consumer.sh ./scripts/start_consumer.sh
COPY --from=build /lotus/dist/lotus_backend-0.9.1-py3-none-any.whl /tmp/lotus_backend-0.9.1-py3-none-any.whl
RUN apt-get update && apt-get install -y netcat \
    && rm -rf /var/lib/apt/lists/* \
    && pip install -U --no-cache-dir --disable-pip-version-check wheel \
    && pip install /tmp/lotus_backend-0.9.1-py3-none-any.whl \
    && rm /tmp/lotus_backend-0.9.1-py3-none-any.whl \
    && chmod +x ./scripts/start_backend.prod.sh \
    && chmod +x ./scripts/start_consumer.sh

