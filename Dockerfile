# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Node 20 — yalnızca "node" ikili dosyası kopyalanır.
# npm/npx bilinçli olarak alınmaz: imajda paket yöneticisi yoksa üretilen kod
# bağımlılık indiremez. "Sıfır bağımlılıkla node --test" kuralı böylece imaj
# düzeyinde de zorlanmış olur (PROJECT.md §2.1, §6/T2b).
# ---------------------------------------------------------------------------
FROM node:20-bookworm-slim AS node

FROM python:3.11-slim-bookworm

COPY --from=node /usr/local/bin/node /usr/local/bin/node

# libstdc++6: node ikili dosyasının çalışma anı bağımlılığı.
# "node --version" burada bir derleme zamanı duman testidir; eksik kütüphane
# çalışma anında değil, derlemede patlasın.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libstdc++6 \
 && rm -rf /var/lib/apt/lists/* \
 && node --version

# Sandbox'ın ayrıcalık düşürme katmanı bu kullanıcıya dayanır (PROJECT.md §3.3).
RUN useradd --system --no-create-home --shell /usr/sbin/nologin runner

WORKDIR /app

# Bağımlılıklar koddan önce: kod değişince pip katmanı yeniden kurulmaz.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY prompts/ ./prompts/
COPY src/ ./src/

# Üretilen oyunların kök dizini. Görev başına alt dizin açılır ve runner'a
# devredilir; app sürecinin kendisi bu dizine root olarak yazar.
RUN mkdir -p /workspaces /app/data && chown runner:runner /workspaces

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    WORKSPACES_ROOT=/workspaces

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
