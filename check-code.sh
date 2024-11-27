#!/bin/bash -ex

source venv/bin/activate

pycodestyle --ignore=E501 */*.py

PYTHONPATH=`pwd` pylint --max-line-length=240 services/ letsgo.py instance.py mission.py
