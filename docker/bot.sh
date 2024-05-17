#!/bin/bash

# wait for postgres
while ! pg_isready -h botarbitrage.postgres.database.azure.com; do  # example1!
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
