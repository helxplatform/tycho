FROM python:3.9.3-slim

WORKDIR /

RUN apt-get update
RUN apt-get install -y build-essential libffi-dev libssl-dev
RUN apt-get install libffi-dev
RUN pip install --upgrade pip
#RUN pip install --no-cache-dir -r ./requirements.txt
#COPY requirements.txt ./

RUN apt-get install -y git
RUN git clone https://github.com/helxplatform/tycho.git --branch develop
RUN pip install --no-cache-dir -r tycho/requirements.txt
#COPY . /tycho

ENV PYTHONPATH /tycho
ENV WORKERS=2
ENV APP_MODULE=tycho.api:app
ENV APP_NAME=tycho
ENV PORT=8099

ENV TYCHO=https://tycho.renci.org

ENTRYPOINT /usr/local/bin/gunicorn --workers=$WORKERS --bind=0.0.0.0:$PORT --name=$APP_NAME --timeout=600 $APP_MODULE
