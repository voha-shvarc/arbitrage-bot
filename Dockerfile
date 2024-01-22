FROM python:alpine3.17

RUN apk add build-base git bash postgresql-client
WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

RUN chmod a+x docker/*.sh

RUN python /app/docker/fix_huobi.py
