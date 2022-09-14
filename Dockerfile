# ---------------------------------------
# Build
# ---------------------------------------
FROM --platform=linux/amd64 python:3.9-bullseye AS build
ENV PYTHONUNBUFFERED 1
#make lotus user
WORKDIR /lotus
# pip install optimization
COPY Pipfile Pipfile.lock ./
RUN pip install -U --no-cache-dir --disable-pip-version-check pipenv
RUN pipenv install --system --deploy --ignore-pipfile
# copy python files,
COPY ./lotus/ ./lotus/
COPY ./metering_billing/ ./metering_billing/
COPY ./manage.py ./
# ---------------------------------------
# Development
# ---------------------------------------
FROM build AS development
# ---------------------------------------
# Production
# ---------------------------------------
FROM development AS production
