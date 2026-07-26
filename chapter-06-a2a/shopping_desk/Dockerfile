FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY catalog_data.py .
COPY shopping_desk ./shopping_desk
EXPOSE 8000
CMD ["adk", "web", ".", "--host", "0.0.0.0", "--port", "8000"]
