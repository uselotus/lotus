# using official Docker Python BaseImage 
FROM python:3

WORKDIR /usr/src/app


COPY Pipfile Pipfile.lock ./

# install pipenv in container
RUN pip install -U pipenv

# install the packages/dependencies required for the project
# NOTE: i'm not entirely sure what the '--system' flag does here, might need to get rid of it?  
RUN pipenv install --system 

# copy all files from the <src> directory to the <dest> directory
COPY . .

# Run Server

CMD ["python", "manage.py", "runserver"]