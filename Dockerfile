FROM python:3.12

COPY . /peoplesdaily

WORKDIR /peoplesdaily
VOLUME /peoplesdaily/data
RUN pip install -r /peoplesdaily/requirements.txt --no-cache-dir

ENV LANG=C.UTF-8
ENV PYTHONUNBUFFERED=0

CMD ["python", "/peoplesdaily/src/schedule_task.py"]
