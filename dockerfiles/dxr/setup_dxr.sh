#!/bin/bash

virtualenv /home/dxr/venv && python peep.py install -r requirements.txt && python setup.py develop && pip install pdbpp nose-progressive Sphinx==1.3.1
