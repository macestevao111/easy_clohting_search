#!/bin/bash
# Ativa o ambiente virtual
source venv/bin/activate
# Instala Flask no ambiente virtual
pip install Flask
export FLASK_APP=app.py
export FLASK_ENV=development
flask run --host=0.0.0.0 --port=3000
