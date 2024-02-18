#!/bin/bash

# wait for postgres
while ! pg_isready -h 10.10.49.3; do
  echo 'Retry in 5 seconds...'
  sleep 5
done

alembic upgrade head

python main.py
