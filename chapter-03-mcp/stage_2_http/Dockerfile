FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY catalog_data.py .
COPY stage_2_http ./stage_2_http
EXPOSE 8000
CMD ["python", "-m", "stage_2_http.catalog_server"]
