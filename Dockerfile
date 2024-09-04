FROM python:3.12

COPY . /peoplesdaily

WORKDIR /peoplesdaily
VOLUME /peoplesdaily/data
RUN pip install -r /peoplesdaily/requirements.txt --no-cache-dir

ENV LANG=C.UTF-8
ENV PYTHONUNBUFFERED=1

CMD ["python", "/peoplesdaily/main.py", "--cron-enabled"]
