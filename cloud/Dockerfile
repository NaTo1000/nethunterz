FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt aiohttp

# Copy cloud and shared modules
COPY cloud/ cloud/
COPY nrf_module/ nrf_module/

# Create non-root user
RUN adduser --disabled-password --gecos "" nethunterz
USER nethunterz

EXPOSE 8080

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "cloud.api_server"]
