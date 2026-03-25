FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pdf_to_excel/ /app/pdf_to_excel/

RUN pip install --no-cache-dir -r /app/pdf_to_excel/requirements.txt

EXPOSE 8501

WORKDIR /app/pdf_to_excel

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]

