#!/bin/bash -ex

source venv/bin/activate

pip install -r requirements-dev.txt

pycodestyle *.py */*.py

PYTHONPATH=`pwd` pylint services/ letsgo.py instance.py mission.py

pytest -m "not integration"
