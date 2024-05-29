FROM python:alpine AS builder

WORKDIR /app

COPY ./requirements.txt .
RUN pip install --no-cache-dir -U -r requirements.txt

FROM python:alpine

WORKDIR /app

COPY --from=builder /usr/local /usr/local

COPY . /app
EXPOSE 3000

ENTRYPOINT ["python", "./main.py"]