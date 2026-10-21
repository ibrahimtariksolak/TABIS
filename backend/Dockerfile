FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml requirements.txt ./
COPY battery_platform/ battery_platform/

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "battery_platform.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
