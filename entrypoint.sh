#!/bin/sh
set -e

python manage.py makemigrations core
python manage.py makemigrations clients
python manage.py makemigrations interns
python manage.py makemigrations notifications
python manage.py migrate core
python manage.py migrate clients
python manage.py migrate interns
python manage.py migrate
python manage.py collectstatic

exec "$@"
