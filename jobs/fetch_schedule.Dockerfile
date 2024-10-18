FROM python:3.10.4

ARG FOOTBALL_API_KEY
ARG ORACLE_DB_PWD

COPY . packing_report/

RUN mv packing_report/srv/tnsnames.ora /etc/
RUN mkdir -p /root/soccerdata/config/
RUN cp packing_report/configs/*.json /root/soccerdata/config/


ENV FOOTBALL_API_KEY=$FOOTBALL_API_KEY
ENV ORACLE_DB_PWD=$ORACLE_DB_PWD
ENV PYTHONPATH="/packing_report"

WORKDIR "/packing_report"

# RUN pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ["python", "pipeline/fetch_schedule.py"]