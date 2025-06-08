FROM python:3.12-alpine

RUN apk add --no-cache openssh-client

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gatekeeper.py gatekeeper.py

CMD ["streamlit", "run", "gatekeeper.py", "--server.port=8501", "--server.enableCORS=false"]