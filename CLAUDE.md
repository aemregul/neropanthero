# Nero Panthero AI Studio — Proje Dokümantasyonu

> **Repo:** [github.com/aemregul/neropanthero](https://github.com/aemregul/neropanthero)

Bu dosya projenin tüm özelliklerini, mimarisini ve nasıl çalıştığını açıklar. Yeni bir AI oturumu veya ekip üyesi bu dosyayı okuyarak projeyi tamamen anlayabilir.

---

## 🚨 KRİTİK ÇALIŞMA KURALLARI (EN ÖNCELİKLİ!)

Bu kurallar her şeyden önce gelir. Bu kurallara uyulmadığı takdirde proje bozulabilir.

### 1. Branch Tabanlı Geliştirme

- **`main` branch'a direkt push YASAK.** Her değişiklik için yeni branch oluştur.
- Branch'ı deploy ortamında ayrı deploy olarak canlıya al ve test et.
- Test başarılıysa `main`'e merge et. Başarısızsa düzelt, tekrar test et.
- Branch isimlendirme: `fix/bug-adi`, `feat/ozellik-adi`, `hotfix/acil-duzeltme`

### 2. Bir Şeyi Düzeltirken Başka Şeyleri Bozma

- **Bir bug fix'e odaklanırken mevcut çalışan özellikleri ASLA bozma.**
- Değişiklik yapmadan önce etki analizi yap: "Bu değişiklik hangi dosyaları, hangi özellikleri etkiler?"
- Eğer bir fix başka bir özelliği bozabilecekse, **ÖNCE kullanıcıyı bilgilendir:**
  - "Bu bug'ı şöyle çözeceğim, ama X özelliği etkilenebilir. Onay veriyor musun?"
- Kullanıcıdan onay almadan riskli değişiklik YAPMA.

### 3. Test Etmeden Push Yok

- Her değişiklik **önce local'de test edilecek** (import kontrolü, syntax kontrolü, çalıştırma testi).
- Sonra branch'ta deploy edilip **canlıda da test edilecek.**
- Test edilmemiş kod kesinlikle `main`'e merge edilmez.

### 4. Bilgilendirme Zorunluluğu

- Ne yapacağını, hangi dosyaları değiştireceğini, potansiyel riskleri **önceden söyle.**
- Sessizce dosya değiştirme, "bonus" özellik ekleme, veya planlanmamış değişiklik yapma.
- Her değişiklik öncesi kısa bilgi ver: "X dosyasında Y değişikliği yapacağım, Z etkisi olabilir."

### 5. Sadece İstenen Şeye Odaklan

- Kullanıcının istediği değişikliği yap, ekstra "iyileştirme" ekleme.
- Çalışan sisteme müdahale etme — "daha iyi olur" diye değişiklik yapma.
- Bir sorun çözülmüyorsa zorlamadan kullanıcıyla konuş, birlikte karar verin.

### 6. Öncelik: Stabilite

- Yeni özellik eklemeden önce mevcut sistemin kararlı çalıştığından emin ol.
- Kullanıcı tarafında "yanıt vermedi" veya "asılı kaldı" hissi oluşturan sessiz hatalar kritik bug olarak ele alınmalı.

---

## 🧠 Proje Nedir?

Nero Panthero AI Studio, **agent-first** (ajantik) bir AI yaratıcı stüdyodur. Kullanıcı doğal dilde istek yapar; AI asistan planlar, üretir, düzenler ve adapte olur.

**Temel Yetkinlikler:**

- 🖼️ Görsel üretim ve düzenleme (AI modelleri, admin toggle ile yönetim)
- 🎬 Video üretim ve post-production (FFmpeg + AI)
- 🎵 Müzik/ses üretimi ve senkronizasyon
- 🚀 Tek cümleden tam kampanya oluşturma (otonom)
- 👤 Karakter/marka/mekan hafızası (@tag sistemi)
- 🔍 Web araştırma ve analiz

---

## 🏗️ Mimari

### Tech Stack

| Katman          | Teknoloji                                     |
| --------------- | --------------------------------------------- |
| **Backend**     | Python, FastAPI, SQLAlchemy, Alembic          |
| **Frontend**    | Next.js, TypeScript, React, TailwindCSS       |
| **Veritabanı**  | PostgreSQL (asyncpg)                          |
| **Cache**       | Redis (opsiyonel — yoksa DB fallback)         |
| **Primary LLM** | OpenAI GPT-4o                                |
| **Görsel AI**   | fal.ai (Nano Banana, Flux.2, GPT Image 1 vb.) |
| **Video AI**    | fal.ai (Kling 3.0 Pro), Google Veo 3.1       |
| **Ses AI**      | OpenAI Whisper/TTS, ElevenLabs                |
| **Arama**       | Pinecone (vektör), SerpAPI (web)              |
| **Auth**        | Google OAuth 2.0, JWT                         |

### Klasör Yapısı

```
neropanthero/
├── backend/
│   ├── app/
│   │   ├── api/routes/          # REST API endpoints
│   │   ├── core/                # config, database, cache
│   │   ├── models/              # SQLAlchemy modelleri
│   │   ├── services/
│   │   │   ├── agent/           # orchestrator.py, tools.py
│   │   │   ├── plugins/         # fal_plugin_v2.py, fal_models.py
│   │   │   ├── long_video_service.py
│   │   │   ├── google_video_service.py
│   │   │   ├── entity_service.py
│   │   │   ├── asset_service.py
│   │   │   └── ...
│   │   └── main.py
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── app/                 # Next.js pages
│       ├── components/          # ChatPanel, AssetsPanel, Sidebar vb.
│       ├── contexts/            # AuthContext
│       └── lib/                 # api.ts
└── CLAUDE.md                    # Bu dosya
```

---

## 🤖 Agent Sistemi

Agent, GPT-4o tabanlıdır. Kullanıcının mesajını alır, hangi araçları kullanacağına karar verir ve çalıştırır. Araç tanımları `tools.py`, handler'lar `orchestrator.py` dosyasındadır.

### Tool Call Guard'ları

| Guard                     | Engellenen                         | Tetikleyici                    |
| ------------------------- | ---------------------------------- | ------------------------------ |
| **Entity Guard**          | `create_character/location/brand`  | `generate_image` aynı batch'te |
| **Plugin Guard**          | `generate_image`, `edit_image` vb. | `manage_plugin` aynı batch'te  |
| **Video Duplicate Guard** | İkinci video çağrısı               | Aynı batch'te 2x video         |

### Görsel Araçları

| Araç                | Ne Yapar                                      |
| ------------------- | --------------------------------------------- |
| `generate_image`    | Yeni görsel üretir                            |
| `edit_image`        | Mevcut görseli düzenler (maskesiz inpainting) |
| `outpaint_image`    | Görsel boyutunu/formatını değiştirir          |
| `upscale_image`     | Kaliteyi artırır                              |
| `remove_background` | Arka planı kaldırır (transparent PNG)         |
| `generate_grid`     | Grid oluşturur (varyasyon)                    |

### Video Araçları

| Araç                  | Ne Yapar                                                       |
| --------------------- | -------------------------------------------------------------- |
| `generate_video`      | Kısa video üretir (≤10s)                                      |
| `generate_long_video` | Uzun video üretir (15-180s) — sahne planı + FFmpeg birleştirme |
| `edit_video`          | Videoyu görsel olarak düzenler                                 |
| `advanced_edit_video` | FFmpeg post-production                                         |

### Ses & Müzik

| Araç                 | Ne Yapar                                  |
| -------------------- | ----------------------------------------- |
| `generate_music`     | AI müzik üretir                           |
| `add_audio_to_video` | Videoya ses/müzik ekler (FFmpeg)          |
| `audio_visual_sync`  | Ses-görüntü senkronizasyonu               |

### Diğer Araçlar

| Araç                                  | Ne Yapar                      |
| ------------------------------------- | ----------------------------- |
| `plan_and_execute`                    | Tek cümleden tam kampanya     |
| `create_character/location/brand`     | Entity oluştur (@tag sistemi) |
| `search_web/search_images/browse_url` | Web araştırma                 |
| `research_brand`                      | Marka araştırması             |
| `manage_plugin`                       | Plugin CRUD                   |
| `manage_core_memory`                  | Kullanıcı tercihleri hafıza   |

---

## 🛡️ Admin Panel

| Sekme           | Ne Yapar                                                |
| --------------- | ------------------------------------------------------- |
| **Genel Bakış** | Toplam oturum, asset, mesaj, aktif model istatistikleri |
| **AI Modeller** | Model açma/kapama toggle'ları                           |
| **Analitik**    | Model kullanım dağılımı, günlük üretim trendleri        |

---

## 🖥️ Frontend Özellikleri

- **Chat Paneli**: SSE streaming, çoklu görsel yükleme, medya düzeni, `react-markdown` ile zengin mesaj formatı
- **Assets Panel**: Kategori filtresi, çoklu seçim & indirme, video hover preview, çöp kutusu
- **Sidebar**: Proje yönetimi, entity listesi, plugin listesi, daraltılabilir
- **Auth**: Google OAuth 2.0, "Hesabımı hatırla" toggle

---

## 🔧 Çalıştırma Komutları

```bash
# Backend (development — auto-reload)
cd backend
# Windows:
$env:PYTHONIOENCODING="utf-8"; venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm run dev
```

### URL'ler

| Ortam | Frontend             | Backend              |
| ----- | -------------------- | -------------------- |
| Lokal | http://localhost:3000 | http://localhost:8000 |

### Environment Variables

| Değişken               | Açıklama                  |
| ---------------------- | ------------------------- |
| `DATABASE_URL`         | PostgreSQL bağlantı URL'i |
| `OPENAI_API_KEY`       | OpenAI API anahtarı       |
| `FAL_KEY`              | fal.ai API anahtarı       |
| `ANTHROPIC_API_KEY`    | Anthropic API anahtarı    |
| `GOOGLE_CLIENT_ID`     | Google OAuth Client ID    |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret|
| `GOOGLE_REDIRECT_URI`  | Google OAuth callback URL |
| `FRONTEND_URL`         | Frontend URL              |
| `BACKEND_URL`          | Backend URL               |
| `ALLOWED_ORIGINS`      | CORS izin verilen origins |

---

## 🧠 Agent Context Sistemi

`orchestrator.py` → `_build_enriched_context()` metodu:

| #   | Bileşen               | Ne Enjekte Eder                         |
| --- | --------------------- | --------------------------------------- |
| 1   | Entity @tag çözümleme | Mesajdaki @tag'lerin detayları          |
| 2   | Proje bağlamı         | Aktif proje adı, kategori               |
| 3   | Working Memory        | Son 5 asset'in URL ve prompt'u          |
| 4   | Kullanıcı tercihleri  | Aspect ratio, model, stil               |
| 5   | Episodic memory       | Önemli olaylar                          |
| 6   | Core memory           | Projeler arası uzun vadeli hafıza       |
| 7   | Entity listesi        | Kullanıcının TÜM entity'leri            |
| 8   | Plugin listesi        | Projede yüklü eklentilerin stil bilgisi |

---

## Değişiklik Öncesi Kontrol Listesi

Her değişiklik öncesi şunları yap:
1. ✅ Hangi dosyalar değişecek?
2. ✅ Bu değişiklik başka özellikleri etkiler mi?
3. ✅ Riskli bir durum var mı? → Kullanıcıyı bilgilendir
4. ✅ Branch oluşturuldu mu? (main'e direkt değişiklik yok)
5. ✅ Lokal test yapılacak mı? → Evet, her zaman
