#!/bin/bash

# wait for postgres
while ! pg_isready -h 10.63.144.3; do
  echo 'Retry in 5 seconds...'
  sleep 5
done

alembic upgrade head

if [[ "${1}" == "tgbot" ]]; then
  python bot.py
elif [[ "${1}" == "tgbot-filtered" ]]; then
  python bot.py -f
else
  python main.py
fi
