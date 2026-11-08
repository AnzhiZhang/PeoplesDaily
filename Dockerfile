FROM python:3.14

COPY . /peoplesdaily

WORKDIR /peoplesdaily
VOLUME ["/peoplesdaily/config", "/peoplesdaily/data"]
RUN apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*
RUN pip install -r /peoplesdaily/requirements.txt --no-cache-dir

ENV LANG=C.UTF-8
ENV PYTHONUNBUFFERED=1

CMD ["python", "/peoplesdaily/main.py"]
