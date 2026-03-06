# Pepper Root AI Agency — Proje Dokümantasyonu

> **Son Güncelleme:** 6 Mart 2026
> **Repo:** [github.com/aemregul/PepperRootAiAgency](https://github.com/aemregul/PepperRootAiAgency)

Bu dosya projenin tüm özelliklerini, mimarisini ve nasıl çalıştığını açıklar. Yeni bir AI oturumu veya ekip üyesi bu dosyayı okuyarak projeyi tamamen anlayabilir.

---

## 🚨 KRİTİK ÇALIŞMA KURALLARI (EN ÖNCELİKLİ!)

Bu kurallar her şeyden önce gelir. Bu kurallara uyulmadığı takdirde proje bozulabilir.

### 1. Branch Tabanlı Geliştirme
- **`main` branch'a direkt push YASAK.** Her değişiklik için yeni branch oluştur.
- Branch'ı Vercel'de ayrı deploy olarak canlıya al ve test et.
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
- Sonra branch'ta Vercel'e deploy edilip **canlıda da test edilecek.**
- Test edilmemiş kod kesinlikle `main`'e merge edilmez.

### 4. Bilgilendirme Zorunluluğu
- Ne yapacağını, hangi dosyaları değiştireceğini, potansiyel riskleri **önceden söyle.**
- Sessizce dosya değiştirme, "bonus" özellik ekleme, veya planlanmamış değişiklik yapma.
- Her değişiklik öncesi kısa bilgi ver: "X dosyasında Y değişikliği yapacağım, Z etkisi olabilir."

### 5. Sadece İstenen Şeye Odaklan
- Kullanıcının istediği değişikliği yap, ekstra "iyileştirme" ekleme.
- Çalışan sisteme müdahale etme — "daha iyi olur" diye değişiklik yapma.
- Bir sorun çözülmüyorsa zorlamadan kullanıcıyla konuş, birlikte karar verin.

---

## 🧠 Proje Nedir?

Pepper Root AI Agency, **agent-first** (ajantik) bir AI yaratıcı stüdyodur. Kullanıcı doğal dilde istek yapar; AI asistan planlar, üretir, düzenler ve adapte olur.

**Temel Yetkinlikler:**
- 🖼️ Görsel üretim ve düzenleme (33 AI modeli, admin toggle ile yönetim)
- 🎬 Video üretim ve post-production (FFmpeg + AI)
- 🎵 Müzik/ses üretimi ve senkronizasyon
- 🚀 Tek cümleden tam kampanya oluşturma (otonom)
- 👤 Karakter/marka/mekan hafızası (@tag sistemi)
- 🔍 Web araştırma ve analiz

---

## 🏗️ Mimari

### Tech Stack
| Katman | Teknoloji |
|---|---|
| **Backend** | Python 3.14, FastAPI, SQLAlchemy, Alembic |
| **Frontend** | Next.js 16.1.6, TypeScript, React |
| **Veritabanı** | PostgreSQL (Lokal: Docker `pepperroot-db` / Canlı: Railway Postgres) |
| **Cache** | Redis (opsiyonel — yoksa DB fallback) |
| **Primary LLM** | OpenAI GPT-4o |
| **Görsel AI** | fal.ai (Nano Banana, Flux.2, GPT Image 1 vb.) |
| **Video AI** | fal.ai (Kling 3.0 Pro — varsayılan), Google Veo 3.1 |
| **Ses AI** | OpenAI Whisper/TTS, ElevenLabs, Mirelo SFX |
| **Arama** | Pinecone (vektör), SerpAPI (web) |
| **Auth** | Google OAuth 2.0, JWT |

### Klasör Yapısı
```
PepperRootAiAgency/
├── backend/
│   ├── app/
│   │   ├── api/routes/          # REST API endpoints
│   │   ├── core/                # config, database, cache
│   │   ├── models/              # SQLAlchemy modelleri
│   │   ├── services/
│   │   │   ├── agent/           # orchestrator.py, tools.py (36 araç)
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
│       ├── app/                 # Next.js pages (/, /app, /login)
│       ├── components/          # ChatPanel, AssetsPanel, Sidebar vb.
│       ├── contexts/            # AuthContext
│       └── lib/                 # api.ts
└── CLAUDE.md                    # Bu dosya
```

---

## 🤖 Agent Sistemi (36 Araç)

Agent, GPT-4o tabanlıdır. Kullanıcının mesajını alır, hangi araçları kullanacağına karar verir ve çalıştırır. Araç tanımları `tools.py`, handler'lar `orchestrator.py` dosyasındadır.

### Tool Call Guard'ları
| Guard | Engellenen | Tetikleyici |
|---|---|---|
| **Entity Guard** | `create_character/location/brand` | `generate_image` aynı batch'te |
| **Plugin Guard** | `generate_image`, `edit_image` vb. | `manage_plugin` aynı batch'te |
| **Video Duplicate Guard** | İkinci video çağrısı | Aynı batch'te 2x video |

### Görsel Araçları
| Araç | Ne Yapar |
|---|---|
| `generate_image` | Yeni görsel üretir (9 model destekler) |
| `edit_image` | Mevcut görseli düzenler (maskesiz inpainting) |
| `outpaint_image` | Görsel boyutunu/formatını değiştirir |
| `upscale_image` | Kaliteyi artırır (Topaz 2x-4x) |
| `remove_background` | Arka planı kaldırır (transparent PNG) |
| `generate_grid` | 3x3 grid oluşturur (9 varyasyon) |

### Video Araçları
| Araç | Ne Yapar |
|---|---|
| `generate_video` | Kısa video üretir (≤10s) — 5 model |
| `generate_long_video` | Uzun video üretir (15-180s) — sahne planı + FFmpeg birleştirme |
| `edit_video` | Videoyu görsel olarak düzenler |
| `advanced_edit_video` | FFmpeg post-production (10 operasyon) |

### Ses & Müzik
| Araç | Ne Yapar |
|---|---|
| `generate_music` | AI müzik üretir (MiniMax) |
| `add_audio_to_video` | Videoya ses/müzik ekler (FFmpeg) |
| `audio_visual_sync` | Ses-görüntü senkronizasyonu (6 operasyon) |

### Diğer Araçlar
| Araç | Ne Yapar |
|---|---|
| `plan_and_execute` | Tek cümleden tam kampanya |
| `create_character/location/brand` | Entity oluştur (@tag sistemi) |
| `search_web/search_images/browse_url` | Web araştırma |
| `research_brand` | Marka araştırması |
| `manage_plugin` | Plugin CRUD |
| `manage_core_memory` | Kullanıcı tercihleri hafıza |

---

## 🎬 33 AI Modeli (5 Kategori)

| Kategori | Sayı | Modeller |
|---|---|---|
| Görsel Üretim | 9 | Nano Banana Pro, Nano Banana 2, Flux.2, Flux 2 Max, GPT Image 1, Reve, Seedream 4.5, Recraft V3, Grok Imagine 1.0 |
| Görsel Düzenleme | 7 | Flux Kontext, Flux Kontext Pro, OmniGen V1, Flux Inpainting, Object Removal, Outpainting, Nano Banana 2 Edit |
| Video | 9 | Kling 3.0 Pro, Sora 2 Pro, Veo 3.1 Fast, Veo 3.1 Quality, Veo 3.1 (Google SDK), Seedance 1.5, Hailuo 02, Grok Imagine Video |
| Ses & Müzik | 4 | ElevenLabs TTS/SFX, Whisper STT, Stable Audio |
| Araç & Utility | 4 | Face Swap, Topaz Upscale, Background Removal, Style Transfer |

---

## 🛡️ Admin Panel

| Sekme | Ne Yapar |
|---|---|
| **Genel Bakış** | Toplam oturum, asset, mesaj, aktif model istatistikleri |
| **AI Modeller** | 33 modelin açma/kapama toggle'ları (5 kategori) |
| **Analitik** | Model kullanım dağılımı, günlük üretim trendleri |

---

## 🏪 Plugin Marketplace

- 41 resmi plugin (8 kategori)
- Topluluk pluginleri (chat'ten oluşturulan otomatik yayınlanır)
- Sıralama: Popüler, En İyi, Yeni
- Proje seçici popup ile yükleme, duplicate kontrolü

---

## 🖥️ Frontend Özellikleri

- **Chat Paneli**: SSE streaming, çoklu görsel yükleme (10'a kadar), ChatGPT tarzı medya düzeni
- **Assets Panel**: 6 kategori filtresi, çoklu seçim & indirme, video hover preview, çöp kutusu
- **Sidebar**: Proje yönetimi, entity listesi, plugin listesi, daraltılabilir
- **Auth**: Google OAuth 2.0, "Hesabımı hatırla" toggle

---

## 🔧 Çalıştırma Komutları

```bash
# Backend (production)
cd /Users/emre/PepperRootAiAgency/backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Backend (development — auto-reload)
cd /Users/emre/PepperRootAiAgency/backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd /Users/emre/PepperRootAiAgency/frontend
npm run dev
```

### URL'ler
| Ortam | Frontend | Backend |
|---|---|---|
| Lokal | http://localhost:3000 | http://localhost:8000 |
| Canlı | https://pepper-root-ai-agency.vercel.app | https://pepperrootaiagency-production.up.railway.app |

### Railway Environment Variables
| Değişken | Açıklama |
|---|---|
| `DATABASE_URL` | `${Postgres.DATABASE_URL}` — Railway referans |
| `OPENAI_API_KEY` | OpenAI API anahtarı |
| `FAL_KEY` | fal.ai API anahtarı |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret |
| `GOOGLE_REDIRECT_URI` | Google OAuth callback URL |
| `FRONTEND_URL` | Vercel frontend URL |
| `BACKEND_URL` | Railway backend URL |
| `ALLOWED_ORIGINS` | CORS izin verilen origins |

---

## 🧠 Agent Context Sistemi

`orchestrator.py` → `_build_enriched_context()` metodu:

| # | Bileşen | Ne Enjekte Eder |
|---|---|---|
| 1 | Entity @tag çözümleme | Mesajdaki @tag'lerin detayları |
| 2 | Proje bağlamı | Aktif proje adı, kategori |
| 3 | Working Memory | Son 5 asset'in URL ve prompt'u |
| 4 | Kullanıcı tercihleri | Aspect ratio, model, stil |
| 5 | Episodic memory | Önemli olaylar |
| 6 | Core memory | Projeler arası uzun vadeli hafıza |
| 7 | Entity listesi | Kullanıcının TÜM entity'leri |
| 8 | Plugin listesi | Projede yüklü eklentilerin stil bilgisi |

---

## 📋 Faz Geçmişi

| Faz | Tarih | Açıklama |
|---|---|---|
| 1-4 | Ocak 2026 | Altyapı, Agent çekirdek, Entity sistemi, Video üretimi |
| 5-8 | Şubat 2026 | Plugin, Auth, Frontend, GPT-4o migration |
| 9-13 | Şubat 2026 | Redis, Pinecone, Gemini edit, Core Memory |
| 14-21 | Şubat 2026 | UI redesign, Multi-model video, 47 model |
| 22-24 | 27 Şubat | Kampanya planlama, Video editing, Audio sync |
| 25-27 | 1 Mart | Admin Panel, Plugin Marketplace, Guards & UX |
| 28-30 | 3 Mart | Agent Intelligence, Security & Deploy, Feedback sistemi |
| 31 | 4 Mart | Long Video Production Fix & Stability |
| 32 | 4 Mart | Grok Imagine Entegrasyonu (33 model) |
| 33 | 5 Mart | Autonomous Agency Features |
| 34 | 5 Mart | Production Deploy (Railway + Vercel) |

---

## 📊 Proje İstatistikleri

| Metrik | Değer |
|---|---|
| Agent Araç | 36 |
| AI Model | 33 |
| Toplam Faz | 34 |
| Canlı Backend | Railway |
| Canlı Frontend | Vercel |

---

## 📌 Bilinen Sorunlar & Yapılacaklar

- [ ] Rate limiting ve monitoring middleware sorunlu — devre dışı bırakıldı, stabil hale getirilecek
- [ ] Video subprocess hatası — "boş yanıt Exit: 1" debug edilecek
- [ ] System prompt dengelenmesi — çok kısa veya çok uzun olmamalı
- [ ] Chat SSE streaming güvenilirliği — mesaj kesilme sorunu
