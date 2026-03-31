FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed by spacy/presidio
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spacy model (needed by presidio)
RUN python -m spacy download en_core_web_lg

# Copy app code
COPY . .

# Create data directories
RUN mkdir -p data/financial_reports data/compliance_rules data/chroma_db

# Hugging Face Spaces uses port 7860
EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]