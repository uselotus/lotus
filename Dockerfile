# using official Docker Python BaseImage
#!/bin/bash
FROM --platform=linux/amd64 python:3.9-bullseye


WORKDIR /usr/src/app


COPY Pipfile Pipfile.lock ./

# install pipenv in container
RUN pip install -U --no-cache-dir --disable-pip-version-check pipenv

# install the packages/dependencies required for the project
RUN pipenv install --system --deploy --ignore-pipfile
# copy all files from the <src> directory to the <dest> directory
COPY . .

EXPOSE 8000

# Run Server

CMD ["gunicorn", "--bind", ":8000", "--workers", "3", "lotus.wsgi:application"]
