# ---------------------------------------
# Build
# ---------------------------------------
FROM --platform=linux/amd64 python:3.9-bullseye AS build
ENV PYTHONUNBUFFERED 1
ENV POSTGRES_USER lotus
ENV POSTGRES_NAME lotus
ENV POSTGRES_PASSWORD lotus
#make lotus user
WORKDIR /code
# pip install optimization
COPY Pipfile Pipfile.lock ./
RUN pip install -U --no-cache-dir --disable-pip-version-check pipenv
RUN pipenv install --system --deploy --ignore-pipfile
# copy python files,
COPY . .
# ---------------------------------------
# Development
# ---------------------------------------
FROM build AS development
# ---------------------------------------
# Production
# ---------------------------------------
FROM development AS production
