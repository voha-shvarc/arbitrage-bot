#!/bin/bash

if [[ "${1}" == "celery" ]]; then
  celery -A celery_app.conf:app worker -l INFO
elif [[ "${1}" == "flower" ]]; then
  celery -A celery_app.conf:app flower
elif [[ "${1}" == "beat" ]]; then
  celery -A celery_app.conf:app beat -l DEBUG
fi
