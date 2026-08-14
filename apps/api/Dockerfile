FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Non-root user - Zero Trust starts in the container
RUN addgroup --system aegis && adduser --system --ingroup aegis aegis

COPY pyproject.toml .
COPY src ./src
RUN pip install --no-cache-dir .

COPY alembic.ini .
COPY alembic ./alembic

USER aegis
EXPOSE 8000
CMD ["uvicorn", "aegis_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
