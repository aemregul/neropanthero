---
description: Projeyi lokalde çalıştırma (backend + frontend + Docker)
---

# Lokal Geliştirme Ortamı

## Ön Koşullar
- Python 3.12+ ve Node.js 20+ yüklü olmalı
- Docker Desktop çalışıyor olmalı (veritabanı için)
- `backend/.env` dosyası düzgün yapılandırılmış olmalı

## A) Docker ile Veritabanı ve Redis Başlatma

// turbo
1. Docker Compose ile sadece veritabanı ve Redis'i başlat:
```bash
cd /Users/emre/PepperRootAiAgency && docker compose up -d postgres redis
```

## B) Backend Başlatma

// turbo
2. Backend sanal ortamını aktive et ve bağımlılıkları yükle:
```bash
cd /Users/emre/PepperRootAiAgency/backend && source venv/bin/activate && pip install -r requirements.txt
```

// turbo
3. Veritabanı migration'larını çalıştır:
```bash
cd /Users/emre/PepperRootAiAgency/backend && source venv/bin/activate && alembic upgrade head
```

// turbo
4. Backend'i development modunda başlat:
```bash
cd /Users/emre/PepperRootAiAgency/backend && source venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend erişim: http://localhost:8000
API docs: http://localhost:8000/docs

## C) Frontend Başlatma

// turbo
5. Frontend bağımlılıklarını yükle:
```bash
cd /Users/emre/PepperRootAiAgency/frontend && npm install
```

// turbo
6. Frontend'i başlat:
```bash
cd /Users/emre/PepperRootAiAgency/frontend && npm run dev
```

Frontend erişim: http://localhost:3000

## D) Tam Docker Compose (Her Şey Birlikte)

Tüm servisleri Docker Compose ile ayağa kaldırmak için:
```bash
cd /Users/emre/PepperRootAiAgency && docker compose up -d
```

## Servis URL'leri

| Servis    | URL                      |
| --------- | ------------------------ |
| Frontend  | http://localhost:3000     |
| Backend   | http://localhost:8000     |
| API Docs  | http://localhost:8000/docs|
| Flower    | http://localhost:5555     |
| PostgreSQL| localhost:5432            |
| Redis     | localhost:6379            |
