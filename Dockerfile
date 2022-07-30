# using official Docker Python BaseImage
FROM python:3.9

# updating docker host or host machine
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app


COPY Pipfile Pipfile.lock ./

# install pipenv in container
RUN pip install -U pipenv

# install the packages/dependencies required for the project
# NOTE: i'm not entirely sure what the '--system' flag does here, might need to get rid of it?
RUN pipenv install --system

# copy all files from the <src> directory to the <dest> directory
COPY . .

EXPOSE 8000

# Run Server

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
