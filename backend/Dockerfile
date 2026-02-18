# ========== STAGE 1: Builder ==========
FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# ========== STAGE 2: Runtime ==========
FROM python:3.12-slim

WORKDIR /app

# -----------------------------------------------------------------------
# Create non-root user BEFORE copying app files.
# UID 1000 matches the runAsUser in backend-deployment.yaml.
#
# INTERVIEW NOTE (PCI DSS/Security):
#   Running containers as root is a critical security anti-pattern.
#   If an attacker escapes the container, they have root on the node.
#   Non-root user + readOnlyRootFilesystem = defense in depth.
# -----------------------------------------------------------------------
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

COPY . .

# Ensure appuser owns the app directory
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENV WEB_CONCURRENCY=1

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY}"]
