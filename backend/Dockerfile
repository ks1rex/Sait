FROM python:3.11-slim

WORKDIR /app

# LibreOffice is required for docx → pdf conversion (stage 7 of the roadmap).
# Uncomment when ready to enable /generate PDF output.
# Adds ~300 MB to the image, so kept opt-in for now.
#
# RUN apt-get update && apt-get install -y --no-install-recommends \
#         libreoffice \
#     && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
