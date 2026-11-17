#!/usr/bin/env bash

# Thin wrapper around run_tests.py; run from apps/api so pytest.ini and test paths resolve.
# The Python that has the API dependencies installed (the image's, or an activated
# virtualenv) is used; set PYTHON to pick another interpreter.
cd "$(dirname "$0")" || exit 1
exec "${PYTHON:-python3}" run_tests.py "$@"
