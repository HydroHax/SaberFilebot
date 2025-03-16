FROM python:3.9.6-slim-buster
RUN apt update && apt upgrade -y


RUN pip3 install -U pip
RUN mkdir /app/
COPY . /app/
WORKDIR /app/
RUN pip3 install -U -r requirements.txt
CMD python3 -m bot
