#!/bin/bash -ex

source venv/bin/activate

pycodestyle *.py */*.py

PYTHONPATH=`pwd` pylint services/ letsgo.py instance.py mission.py
