FROM python:alpine

COPY ./requirements.txt /app/

WORKDIR /app

RUN pip install --no-cache-dir -U -r requirements.txt

COPY python /app

EXPOSE 5678

ENTRYPOINT ["python", "./main.py"]
