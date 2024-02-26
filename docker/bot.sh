#!/bin/bash

# wait for postgres
while ! pg_isready -h db; do
  echo 'Retry in 5 seconds...'
  sleep 5
done

alembic upgrade head

if [[ "${1}" == "tgbot" ]]; then
  python bot.py
else
  python main.py
fi
