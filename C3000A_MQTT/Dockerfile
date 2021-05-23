FROM python:3.9

RUN pip3 install requests paho-mqtt
COPY DSLModem.py /usr/local/bin/DSLModem.py

CMD ["python3", "/usr/local/bin/DSLModem.py"]