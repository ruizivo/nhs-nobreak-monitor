FROM python:3.9.18-slim-bullseye

RUN apt update && apt upgrade && apt install curl unzip -y && apt install -y procps
RUN python3 -m pip install paho-mqtt

RUN apt-get install dos2unix
RUN apt-get -y install netcat

COPY nhsups_3.1.36_x86_64_eGLIBC_2.11.zip /tmp/nhsups.zip
RUN unzip /tmp/nhsups.zip -d /tmp/nhsups

RUN cd /tmp/nhsups/nhsups_3.1.36_x86_64_eGLIBC_2.11 && chmod +x install.sh && ./install.sh

RUN cd /usr/local/nhs && chmod +x nhsupsserver && chmod +x nhsupsserver.sh
EXPOSE 2001
# EXPOSE 2000

WORKDIR /usr/local/nhs/

COPY start.sh start.sh
RUN dos2unix start.sh
COPY nhs-nobreak-monitor.py nhs-nobreak-monitor.py

CMD bash start.sh