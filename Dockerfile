FROM python:3.12-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY sun_intensity_agent ./sun_intensity_agent
COPY tests ./tests

# Default to running the FastAPI server via uvicorn
# Can be overridden with `docker run <image> python -m sun_intensity_agent.cli [options]`
CMD ["uvicorn", "sun_intensity_agent.server:app", "--host", "0.0.0.0", "--port", "8080"]
