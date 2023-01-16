#!/bin/bash

#all copied from https://www.reddit.com/r/django/comments/qn5r21/comment/hje2qf7/?utm_source=share&utm_medium=web2x&context=3
set -e

# Call this from the host machine.
# It will call the `tests` shortcut defined in Pipfile, which will run
# a script within the pipenv environment. Flake8 and Coverage will also be run.

# You can optionally pass in a test, or test module or class, as an argument.
# e.g.
# ./run_tests.sh tests.appname.test_models.TestClass.test_a_thing
# In this case Flake8 and Coverage will NOT be run.

#still need to add: pipenv run flake8; pipenv run coverage html run coverage
TESTS_TO_RUN=${1:-run_all_tests}

if [[ "$TESTS_TO_RUN" == "run_all_tests" ]]; then
    # Coverage config is in setup.cfg
    docker exec lotus-backend-1 /bin/sh -c "pytest --cov=metering_billing --cov-config=.coveragerc --cov-report term-missing;"
else
    docker exec lotus-backend-1 /bin/sh -c "pytest --cov=metering_billing --cov-config=.coveragerc --cov-report term-missing $TESTS_TO_RUN;"
fi
