"""
Agent tarafından kullanılabilen araçların tanımları.
OpenAI Functions format (function calling).
"""

def convert_to_openai_tools(anthropic_tools: list) -> list:
    """Anthropic tool formatını OpenAI functions formatına çevir."""
    openai_tools = []
    for tool in anthropic_tools:
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool.get("input_schema", {"type": "object", "properties": {}})
            }
        }
        openai_tools.append(openai_tool)
    return openai_tools


# Agent'a sunulacak araçların listesi (Anthropic JSON Schema formatında - geriye uyumluluk)
AGENT_TOOLS_ANTHROPIC = [
    {
        "name": "generate_image",
        "description": "Kullanıcının isteğine göre AI görseli üretir. Model parametresiyle en uygun modeli SEÇ. Model belirtmezsen Smart Router otomatik seçer ama SEN seçersen daha iyi sonuç çıkar. Eğer @tag ile referans verilen bir entity varsa, onun özelliklerini prompt'a ekle.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Görselin detaylı açıklaması (İngilizce olması daha iyi sonuç verir)."
                },
                "aspect_ratio": {
                    "type": "string",
                    "enum": ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "21:9", "4:5", "5:4"],
                    "description": "Görselin en-boy oranı."
                },
                "model": {
                    "type": "string",
                    "enum": ["auto", "nano_banana", "nano_banana_2", "flux2", "flux2_max", "gpt_image", "reve", "seedream", "recraft", "grok_imagine"],
                    "description": "Görsel modeli seç. auto=Smart Router. nano_banana=Fotorealist/portre(varsayılan). nano_banana_2=Hızlı fotorealist(ucuz). flux2=Hızlı+metin/tipografi. flux2_max=Maksimum kalite/detay. gpt_image=Anime/Ghibli/cartoon/illüstrasyon. reve=Yaratıcı/sanatsal. seedream=Hızlı+ucuz. recraft=Logo/vektör/marka. grok_imagine=xAI Grok/yüksek estetik/hassas metin render."
                },
                "resolution": {
                    "type": "string",
                    "enum": ["1K", "2K", "4K"],
                    "description": "Görselin çözünürlüğü."
                },
                "additional_reference_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Kullanıcının gönderdiği referans görsele EK OLARAK eklenecek, internetten (search_images aracıyla) bulduğun referans resimlerin URL listesi (Multi-Image mantığı için)."
                }
            },
            "required": ["prompt"]
        }
    {
        "name": "generate_video",
        "description": "SADECE 5-10 saniyelik KISA video üretir (ARKA PLAN GÖREVİ). ⚠️ KRİTİK KURAL: Kullanıcı 15 saniye, 20 saniye, 30 saniye, 1 dakika, 2 dakika veya daha UZUN video isterse BU ARACI KULLANMA! Bunun yerine generate_long_video kullan. Bu araç MAKSİMUM 10 saniye üretir. BU ARACI TEK SEFERDE SADECE 1 KERE ÇAĞIR! ⚠️ ÇOKLU GÖRSEL: Kullanıcı 2+ referans görsel ile video isterse StoryReel özelliğini öner → kabul ederse generate_long_video kullan, her görseli ayrı sahnenin reference_image_url'sine ekle.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Video açıklaması"},
                "image_url": {"type": "string", "description": "Başlangıç görseli URL (opsiyonel)"},
                "duration": {"type": "string", "enum": ["5", "8", "10"], "description": "Video süresi (saniye). Kullanıcı süre belirtmediyse '5'. 3-6s isterse '5', 7-8s isterse '8', 9-10s isterse '10' kullan."},
                "aspect_ratio": {"type": "string", "enum": ["16:9", "9:16", "1:1"], "description": "Video oranı"},
                "model": {
                    "type": "string", 
                    "enum": ["auto", "kling", "sora2", "veo", "seedance", "hailuo", "grok_imagine_video"], 
                    "description": "Video modeli seç. auto=Smart Router(varsayılan). kling=En güvenilir, çoklu sahne(varsayılan). sora2=En uzun süre(~20s), çoklu sahne+ses, hikaye anlatımı. veo=En iyi fizik simülasyonu, sinematik, belgesel. seedance=Hızlı+ucuz, iyi kalite. hailuo=En hızlı(~5s), kısa clip/sosyal medya. grok_imagine_video=xAI sinematik video+senkronize ses."
                }
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "edit_video",
        "description": "Mevcut bir videoyu GÖRSEL olarak düzenler. Nesne kaldırma/değiştirme (inpainting), stil değiştirme (v2v) veya talimatlı düzenleme yapar. ÖNEMLİ: Bu araç SES/MÜZİK EKLEME YAPMAZ! Ses/müzik birleştirme için add_audio_to_video aracını kullan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "video_url": {"type": "string", "description": "Düzenlenecek videonun URL'si"},
                "prompt": {"type": "string", "description": "Düzenleme talimatı (örn: 'kadını sil', 'anime yap')"},
                "image_url": {"type": "string", "description": "Videonun referans görseli/thumbnail'i (Varsa mutlaka gönderilmeli, daha iyi sonuç verir)"}
            },
            "required": ["video_url", "prompt"]
        }
    },
    {
        "name": "generate_long_video",
        "description": "15 saniyeden UZUN video üretir (15s - 3 dakika, ARKA PLAN GÖREVİ). ⚠️ KRİTİK: Kullanıcı 15 saniye, 20s, 30s, 1dk, 2dk, 3dk gibi SÜRELİ video isterse MUTLAKA BU ARACI kullan — generate_video KULLANMA! Çok aşamalı işlemdir. ÖNEMLİ: Bu aracı çağırmadan ÖNCE kullanıcıya sahne planını göster ve ONAY al! Plan onayı OLMADAN çağırırsan HATA mesajı döner.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Video senaryosu / ana açıklama"},
                "total_duration": {"type": "integer", "description": "Hedef süre (saniye). Min: 15, Max: 180. Varsayılan: 60. ÖNEMLİ: Kullanıcı ne kadar süre istediyse TAM O SÜREYI yaz! 2 dakika=120, 1 dakika=60, 30 saniye=30, 15 saniye=15. ASLA istenen süreden farklı bir değer gönderme!"},
                "aspect_ratio": {"type": "string", "enum": ["16:9", "9:16", "1:1"], "description": "Video oranı"},
                "plan_confirmed": {"type": "boolean", "description": "ÖNCE kullanıcıya sahne planını gösterip onay aldıysan TRUE yap. Plan göstermeden çağırdıysan FALSE yap (HATA döner)."},
                "scene_descriptions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string", "description": "Sahne açıklaması"},
                            "reference_image_url": {"type": "string", "description": "Sahne için kullanılacak referans görselin URL'si (search_images'dan vb.)"},
                            "model": {
                                "type": "string",
                                "enum": ["auto", "kling", "sora2", "veo", "seedance", "hailuo", "grok_imagine_video"],
                                "description": "Sahne video modeli. auto=varsayılan. Tercih: sora2 (uzun/hikaye), veo (sinematik), kling (genel), grok_imagine_video (sinematik+ses)."
                            }
                        },
                        "required": ["prompt"]
                    },
                    "description": "Onaylanan sahne planları"
                }
            },
            "required": ["prompt", "plan_confirmed"]
        }
    },
    {
        "name": "edit_image",
        "description": "Mevcut bir görseli akıllı düzenleme ile düzenler (Gemini True Inpainting birincil, fallback: FLUX Kontext, Object Removal). Kıyafet değiştirme, nesne ekleme/çıkarma, renk değiştirme gibi işlemler için ideal. PROMPT ÖNEMLİ: Kısa talimatları zenginleştir! Örn: 'gözlüğü sil' → 'Remove the sunglasses, keep the exact same face, pose, lighting, background unchanged.'",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_url": {"type": "string", "description": "Düzenlenecek görselin URL'si"},
                "prompt": {"type": "string", "description": "Detaylı düzenleme talimatı (İngilizce). KISA YAZMA! Neyin değişeceğini VE neyin korunacağını açıkça belirt. Örn: 'Change the shirt color to blue. Keep the exact same face, pose, angle, background, and all other details unchanged.'"}
            },
            "required": ["image_url", "prompt"]
        }
    },
    {
        "name": "upscale_image",
        "description": "Görsel kalitesini ve çözünürlüğünü artırır.",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_url": {"type": "string", "description": "Upscale edilecek görselin URL'si"},
                "scale": {"type": "integer", "enum": [2, 4], "description": "Büyütme faktörü"}
            },
            "required": ["image_url"]
        }
    },
    {
        "name": "remove_background",
        "description": "Görselin arka planını kaldırır.",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_url": {"type": "string", "description": "Arka planı kaldırılacak görselin URL'si"}
            },
            "required": ["image_url"]
        }
    },
    {
        "name": "generate_grid",
        "description": "3x3 grid oluşturur. 9 farklı kamera açısı (angles) veya 9 hikaye paneli (storyboard) üretir. @karakter referansı ile otomatik görsel kullanır.",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_url": {"type": "string", "description": "Referans görsel URL'si (entity tag varsa otomatik alınır)"},
                "mode": {
                    "type": "string",
                    "enum": ["angles", "storyboard"],
                    "description": "Grid modu: angles (9 kamera açısı) veya storyboard (9 hikaye paneli)"
                },
                "aspect_ratio": {
                    "type": "string",
                    "enum": ["16:9", "9:16", "1:1"],
                    "description": "Grid görselinin en-boy oranı"
                },
                "custom_prompt": {"type": "string", "description": "Özel grid promptu (opsiyonel)"}
            }
        }
    },
    {
        "name": "use_grid_panel",
        "description": "Oluşturulmuş grid'den belirli bir paneli seçip işlem yapar. Panel numarası 1-9 arası (3x3: üst-sol=1, alt-sağ=9).",
        "input_schema": {
            "type": "object",
            "properties": {
                "panel_number": {
                    "type": "integer",
                    "description": "Seçilecek panel numarası (1-9). Grid düzeni: 1|2|3 / 4|5|6 / 7|8|9"
                },
                "action": {
                    "type": "string",
                    "enum": ["video", "upscale", "download", "edit"],
                    "description": "Panele uygulanacak işlem: video üret, upscale et, indir veya düzenle"
                },
                "video_prompt": {"type": "string", "description": "Video için hareket/animasyon açıklaması (action=video ise)"},
                "edit_prompt": {"type": "string", "description": "Düzenleme promptu (action=edit ise)"}
            },
            "required": ["panel_number", "action"]
        }
    },
    {
        "name": "semantic_search",
        "description": "Semantik olarak benzer karakterleri, mekanları veya markaları arar. Doğal dil sorgusu ile ilgili entity'leri bulur. Örnek: 'sarışın erkek karakter', 'plaj mekanı', 'spor markası'",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Doğal dil arama sorgusu (örn: 'uzun boylu, atletik erkek karakterler')"
                },
                "entity_type": {
                    "type": "string",
                    "enum": ["character", "location", "brand", "wardrobe", "all"],
                    "description": "Aranacak entity tipi (varsayılan: all)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maksimum sonuç sayısı (varsayılan: 5)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_library_docs",
        "description": "Herhangi bir kütüphanenin (library) güncel API dokümantasyonunu çeker. LLM'lerin eski/yanlış bilgi üretmesini engeller. Örn: 'react', 'nextjs', 'fastapi', 'fal.ai', 'langchain' gibi popüler kütüphaneler için kullanılabilir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "library_name": {
                    "type": "string",
                    "description": "Dokümantasyonu çekilecek kütüphane adı (örn: 'react', 'nextjs', 'fastapi', 'fal-ai')"
                },
                "query": {
                    "type": "string",
                    "description": "Spesifik bir sorgu veya konu (opsiyonel). Örn: 'hooks', 'routing', 'authentication'"
                },
                "tokens": {
                    "type": "integer",
                    "description": "Döndürülecek maksimum token sayısı (varsayılan: 5000)"
                }
            },
            "required": ["library_name"]
        }
    },
    {
        "name": "save_style",
        "description": "Bir stil/moodboard kaydet. Kaydedilen stil sonraki tüm üretimlerde otomatik uygulanır. Örn: 'cyberpunk stili', 'minimalist beyaz', 'retro 80s'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Stil adı (örn: 'cyberpunk', 'minimalist')"},
                "description": {"type": "string", "description": "Stilin detaylı açıklaması (İngilizce). Renkler, ton, atmosfer, ışık, doku vb."},
                "color_palette": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Renk paleti (hex kodları, opsiyonel)"
                },
                "reference_image_url": {"type": "string", "description": "Referans görsel URL (opsiyonel)"}
            },
            "required": ["name", "description"]
        }
    },
    {
        "name": "generate_campaign",
        "description": "Toplu kampanya üretimi. Tek prompt ile birden fazla varyasyon üretir (farklı açılar, formatlar). Instagram, TikTok, YouTube için optimized boyutlarda.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Kampanya açıklaması / ana konsept"},
                "count": {"type": "integer", "description": "Kaç varyasyon üretilsin (varsayılan: 4, max: 9)"},
                "formats": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["post", "story", "reel", "cover"]},
                    "description": "Üretilecek formatlar. post=1:1, story=9:16, reel=9:16, cover=16:9"
                },
                "brand_tag": {"type": "string", "description": "Marka entity tag'i (opsiyonel, örn: @nike)"}
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "transcribe_voice",
        "description": "Sesli mesajı metne çevirir (Whisper API). Kullanıcı ses kaydı gönderdiğinde otomatik kullanılır.",
        "input_schema": {
            "type": "object",
            "properties": {
                "audio_url": {"type": "string", "description": "Ses dosyasının URL'si"},
                "language": {"type": "string", "description": "Dil kodu (varsayılan: 'tr'). 'tr', 'en', 'auto'"}
            },
            "required": ["audio_url"]
        }
    },
    {
        "name": "outpaint_image",
        "description": "Görseli genişletir (outpainting). Görselin kenarlarına yeni içerik ekleyerek boyutunu büyütür. Kırpılmış görselleri genişletme, yatay→dikey dönüşüm, panoramik genişletme için kullan. Yön belirtilmezse her yöne 256px genişletir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_url": {"type": "string", "description": "Genişletilecek görselin URL'si"},
                "prompt": {"type": "string", "description": "Genişletilen alana ne eklenmeli (opsiyonel)"},
                "left": {"type": "integer", "description": "Sola genişletme miktarı (piksel)"},
                "right": {"type": "integer", "description": "Sağa genişletme miktarı (piksel)"},
                "top": {"type": "integer", "description": "Yukarı genişletme miktarı (piksel)"},
                "bottom": {"type": "integer", "description": "Aşağı genişletme miktarı (piksel)"}
            },
            "required": ["image_url"]
        }
    },
    {
        "name": "apply_style",
        "description": "Görsele sanatsal stil uygular (style transfer). Empresyonizm, kübizm, sürrealizm, anime, çizgi film, yağlı boya, suluboya, pixel art gibi stiller uygulanabilir. Moodboard stili aktarımı için de kullanılabilir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_url": {"type": "string", "description": "Stil uygulanacak görselin URL'si"},
                "style": {"type": "string", "description": "Uygulanacak stil (örn: 'impressionism', 'anime', 'oil painting', 'watercolor', 'pixel art', 'cyberpunk')"},
                "prompt": {"type": "string", "description": "Ek stil açıklaması (opsiyonel)"}
            },
            "required": ["image_url", "style"]
        }
    },
    {
        "name": "manage_plugin",
        "description": "Preset yönetimi. Kullanıcı 'preset oluştur' dediğinde sohbetteki mevcut bilgileri (karakter, lokasyon, stil vb.) toplayıp HEMEN bir preset oluştur. Tüm alanların dolu olması GEREKMEZ — elindeki ne varsa onu kullan. Eksik alan engellemez, preset oluşturulur. Başarılı olduğunda kullanıcıya DETAYLI bilgi ver: hangi bilgilerle oluşturuldu, neler eksik, nasıl kullanılır.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "list", "delete"],
                    "description": "İşlem tipi"
                },
                "name": {
                    "type": "string",
                    "description": "Preset adı (create için zorunlu)"
                },
                "description": {
                    "type": "string",
                    "description": "Preset açıklaması (opsiyonel)"
                },
                "plugin_id": {
                    "type": "string",
                    "description": "Silinecek preset ID (delete için)"
                },
                "config": {
                    "type": "object",
                    "description": "Preset ayarları — hepsinin dolu olması gerekmez, mevcut olanları gönder",
                    "properties": {
                        "style": {"type": "string", "description": "Görsel stil (örn: cinematic, anime, minimalist)"},
                        "character_tag": {"type": "string", "description": "Karakter entity tag'i (örn: @emre)"},
                        "location_tag": {"type": "string", "description": "Lokasyon entity tag'i (örn: @paris)"},
                        "timeOfDay": {"type": "string", "description": "Zaman dilimi (örn: golden hour, gece)"},
                        "cameraAngles": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Kamera açıları listesi"
                        },
                        "promptTemplate": {"type": "string", "description": "Prompt şablonu — kullanıcının sohbetteki isteğinden oluştur"},
                        "aspectRatio": {"type": "string", "description": "En-boy oranı"},
                        "model": {"type": "string", "description": "Tercih edilen model"}
                    }
                },
                "is_public": {
                    "type": "boolean",
                    "description": "Toplulukta herkese açık mı (varsayılan: false)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "manage_core_memory",
        "description": "Kullanıcının kendisi hakkında verdiği STABIL bilgileri kalıcı hafızada (Core Memory) yönetir. Sadece kimlik, stil, marka kuralı, çalışma biçimi gibi uzun ömürlü tercihleri kaydet. Sure, adet, model secimi, son referans veya tek seferlik gorev talimatlarini ASLA kaydetme. Kullanıcı bir tercihi belirtirse ekle (add). Fikrini değiştirirse veya silmeni isterse sil (delete). Tüm hafızayı sıfırlamak isterse temizle (clear).",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "delete", "clear"],
                    "description": "İşlem tipi. Yeni bilgi eklemek için 'add', eski bir bilgiyi unutmak için 'delete', her şeyi sıfırlamak için 'clear'."
                },
                "fact_category": {
                    "type": "string",
                    "enum": ["style", "identity", "brand", "general", "workflow"],
                    "description": "Bilginin kategorisi (sadece 'add' işleminde gereklidir)"
                },
                "fact_description": {
                    "type": "string",
                    "description": "Kaydedilecek veya SİLİNECEK bilgi içeriği (örn: 'Kullanıcı Nike markası için çalışıyor'). 'clear' işleminde boş kalabilir."
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "search_web",
        "description": "DuckDuckGo üzerinden internette genel metin araması yapar. Bilinmeyen kavramları, konuları, son dakika olaylarını araştırmak için kullan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Arama terimi"
                },
                "num_results": {
                    "type": "integer",
                    "description": "Kaç sonuç getirileceği (varsayılan: 5)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_images",
        "description": "DuckDuckGo Görsel Arama üzerinden internetten resimler bulur. Resim linklerini (URL) döner. Bir karakterin/kişinin/objenin referans resimlerini (dövmeleri, vücut yapısı vs.) bulmak için kullanırsan, bu URL'leri `generate_image` çağrısındaki `additional_reference_urls` içerisine verebilirsin.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Arama terimi (örn: 'johnny depp tattoos shirtless', 'golden retriever running high quality')"
                },
                "num_results": {
                    "type": "integer",
                    "description": "Kaç resim sonucunun URL'si getirilsin (varsayılan: 3)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "analyze_image",
        "description": "GPT-4o Vision ile bir görseli SON DERECE DETAYLI analiz eder. Görseldeki her şeyi okur: yazılar, logolar, yüz ifadeleri, kıyafetler, mekan detayları, renkler, ışık, objelerin konumları, arka plan, kompozisyon. Bu aracı şu durumlarda kullan: (1) Üretilen görselde hata/eksik aranırken, (2) Kullanıcı 'bunu düzelt/değiştir' dediğinde mevcut görseli analiz etmek için, (3) Referans görsel detaylarını öğrenmek için.",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_url": {
                    "type": "string",
                    "description": "Analiz edilecek resmin URL adresi"
                },
                "question": {
                    "type": "string",
                    "description": "Modele resimle ilgili soracağın açık, spesifik soru. Detaylı analiz için: 'Bu görseldeki her şeyi detaylıca listele: yazılar, kişiler, objeler, renkler, ışık, arka plan, kompozisyon, varsa hatalar.'"
                }
            },
            "required": ["image_url", "question"]
        }
    },
    {
        "name": "analyze_video",
        "description": "Bir video URL'sinden key frame'ler çıkararak GPT-4o Vision ile videoyu analiz eder. Videodaki sahneleri, hareketleri, yazıları, hataları, eksikleri tespit eder. Bu aracı şu durumlarda kullan: (1) Üretilen videoda sorun aranırken, (2) Kullanıcı 'bu videodaki yazıyı değiştir' dediğinde, (3) Referans video/klip içeriğini anlamak için, (4) Videonun kalitesini ve promptla uyumunu kontrol etmek için.",
        "input_schema": {
            "type": "object",
            "properties": {
                "video_url": {
                    "type": "string",
                    "description": "Analiz edilecek videonun URL adresi"
                },
                "question": {
                    "type": "string",
                    "description": "Video hakkında sorulacak soru. Örn: 'Bu videoda neler oluyor, sahneleri listele', 'Videodaki yazıları oku', 'Sahne geçişlerini ve hareketleri anlat'"
                },
                "num_frames": {
                    "type": "integer",
                    "description": "Videodan kaç frame çıkarılsın (varsayılan: 6, max: 12). Kısa videolar için 4, uzun için 8-12 önerilir."
                }
            },
            "required": ["video_url", "question"]
        }
    },
    {
        "name": "save_web_asset",
        "description": "Webt'en bulduğun veya kullanıcının çok beğeneceği bir resim URL'sini doğrudan sistemdeki (DB) Media Asset'lere kalıcı olarak kaydeder. Kullanıcı 'bu resmi bana indir/panelime kaydet' dediğinde bunu kullan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "asset_url": {
                    "type": "string",
                    "description": "Kaydedilecek dosyanın kalıcı URL linki"
                },
                "asset_type": {
                    "type": "string",
                    "enum": ["image", "video"],
                    "description": "Medyanın türü"
                }
            },
            "required": ["asset_url", "asset_type"]
        }
    },
    {
        "name": "generate_music",
        "description": "AI ile müzik/şarkı üretir (MiniMax Music). Metin promptundan profesyonel kalitede müzik oluşturur. Klip, reklam, içerik senesine uygun müzik üretmek için kullan. Şarkı sözleri de verilebilir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Müzik açıklaması. Örn: 'Upbeat electronic dance music with synth leads, energetic and modern, 120 BPM' veya 'Gentle acoustic guitar melody, warm and intimate, folk style'"
                },
                "lyrics": {
                    "type": "string",
                    "description": "Opsiyonel şarkı sözleri. [Verse], [Chorus], [Bridge] yapı etiketleri kullanılabilir."
                },
                "duration": {
                    "type": "integer",
                    "description": "Müzik süresi (saniye). Varsayılan: 30, max: 120"
                }
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "add_audio_to_video",
        "description": "MEVCUT bir videoya MEVCUT bir ses/müzik dosyasını FFmpeg ile birleştirir. Kullanıcı 'videoyu müzikle birleştir', 'videoya ses ekle', 'bu müziği videoya koy' dediğinde MUTLAKA bu aracı kullan. video_url ve audio_url ZORUNLU. edit_video veya generate_video KULLANMA — onlar birleştirme yapmaz!",
        "input_schema": {
            "type": "object",
            "properties": {
                "video_url": {
                    "type": "string",
                    "description": "Müzik eklenecek videonun URL'si"
                },
                "audio_url": {
                    "type": "string",
                    "description": "Eklenecek müzik/ses dosyasının URL'si"
                },
                "replace_audio": {
                    "type": "boolean",
                    "description": "true: Mevcut sesi tamamen değiştir. false: Üstüne ekle (mix). Varsayılan: true"
                }
            },
            "required": ["video_url", "audio_url"]
        }
    },
    {
        "name": "plan_and_execute",
        "description": "Büyük/çok adımlı yaratıcı projeleri OTONOM olarak planla ve uygula. Kampanya, multi-format içerik paketi, marka kit, sosyal medya seti vb. Kullanıcı karmaşık bir istek yaptığında (birden fazla çıktı türü/formatı) BU ARACI KULLAN. İç planlamayı GPT-4o ile yapar, sonra görevleri paralel yürütür. Tek seferde 9'a kadar görsel + 4'e kadar video üretebilir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "Üst düzey proje hedefi (örn: 'Nike yaz kampanyası — 5 Instagram post, 2 story video, 1 kapak görseli')"
                },
                "brand_tag": {
                    "type": "string",
                    "description": "Varsa marka entity tag'i (örn: @nike). Markanın renkleri, tonu otomatik entegre edilir."
                },
                "output_types": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["image", "video", "audio"]},
                    "description": "Üretilecek çıktı türleri (varsayılan: ['image'])"
                },
                "count": {
                    "type": "integer",
                    "description": "Toplam çıktı sayısı (varsayılan: hedeften otomatik çıkar, max 13)"
                },
                "formats": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["post", "story", "reel", "cover", "banner", "thumbnail"]},
                    "description": "Hedef formatlar. post=1:1, story/reel=9:16, cover/banner/thumbnail=16:9"
                },
                "style_notes": {
                    "type": "string",
                    "description": "Ek stil notları (örn: 'Minimalist, pastel renkler, yazısız')"
                }
            },
            "required": ["goal"]
        }
    },
    {
        "name": "advanced_edit_video",
        "description": "FFmpeg ile gelişmiş video düzenleme. Trim (kırpma), slow motion, fade, yazı ekleme, birleştirme, ters çevirme, boyut değiştirme, filtre uygulama gibi işlemler. ÖNEMLİ: Bu araç GÖRSEL düzenleme (nesne silme, stil değiştirme) yapmaz — onun için edit_video kullan. Bu araç TEKNİK video post-production için.",
        "input_schema": {
            "type": "object",
            "properties": {
                "video_url": {"type": "string", "description": "Düzenlenecek videonun URL'si"},
                "operation": {
                    "type": "string",
                    "enum": ["trim", "speed", "fade", "text_overlay", "reverse", "resize", "concat", "loop", "filter", "extract_frame"],
                    "description": "Yapılacak işlem. trim=kırp, speed=hız değiştir, fade=geçiş efekti, text_overlay=yazı ekle, reverse=ters çevir, resize=boyut değiştir, concat=birleştir, loop=tekrarla, filter=filtre uygula, extract_frame=kare çıkar"
                },
                "start_time": {"type": "number", "description": "Trim/text: başlangıç zamanı (saniye)"},
                "end_time": {"type": "number", "description": "Trim: bitiş zamanı (saniye)"},
                "speed": {"type": "number", "description": "Speed: hız çarpanı. 0.25=quarter, 0.5=slow-mo, 2.0=fast, 4.0=timelapse"},
                "fade_in": {"type": "number", "description": "Fade: fade-in süresi (saniye)"},
                "fade_out": {"type": "number", "description": "Fade: fade-out süresi (saniye)"},
                "text": {"type": "string", "description": "Text overlay: gösterilecek metin"},
                "text_position": {
                    "type": "string",
                    "enum": ["top", "center", "bottom", "top-left", "top-right", "bottom-left", "bottom-right"],
                    "description": "Text overlay: metin pozisyonu"
                },
                "font_size": {"type": "integer", "description": "Text overlay: font boyutu (varsayılan: 48)"},
                "font_color": {"type": "string", "description": "Text overlay: renk (white, yellow, red vb.)"},
                "aspect_ratio": {"type": "string", "enum": ["16:9", "9:16", "1:1", "4:3"], "description": "Resize: hedef aspect ratio"},
                "video_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Concat: birleştirilecek video URL'leri listesi"
                },
                "loop_count": {"type": "integer", "description": "Loop: kaç kez tekrar (2-10)"},
                "filter_name": {
                    "type": "string",
                    "enum": ["grayscale", "sepia", "blur", "sharpen", "brightness", "contrast", "vintage", "negative", "vignette"],
                    "description": "Filter: uygulanacak filtre"
                },
                "filter_intensity": {"type": "number", "description": "Filter: filtre yoğunluğu (0.1 - 3.0)"},
                "timestamp": {"type": "number", "description": "Extract frame: kare çıkarılacak zaman (saniye)"}
            },
            "required": ["operation"]
        }
    },
    {
        "name": "audio_visual_sync",
        "description": "Ses ve görüntü senkronizasyonu. Beat detection, ses analizi, beat'e göre kesim listesi, video'dan ses efekti üretimi, akıllı müzik mix ve TTS seslendirme. Kullanıcı 'müziğe göre sahne geçişleri', 'videodan ses efekti çıkar', 'seslendirme ekle' istediğinde kullan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["analyze_audio", "detect_beats", "beat_cut_list", "generate_sfx", "smart_mix", "tts_narration"],
                    "description": "İşlem. analyze_audio=ses analizi. detect_beats=beat tespit. beat_cut_list=beat'e göre kesim noktaları. generate_sfx=videodan ses efekti. smart_mix=akıllı müzik birleştirme. tts_narration=TTS seslendirme."
                },
                "video_url": {"type": "string", "description": "Video URL (generate_sfx, smart_mix, tts_narration için)"},
                "audio_url": {"type": "string", "description": "Ses/müzik URL (analyze_audio, detect_beats, beat_cut_list, smart_mix için)"},
                "text": {"type": "string", "description": "TTS seslendirme metni"},
                "voice": {"type": "string", "enum": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"], "description": "TTS ses tonu (varsayılan: nova)"},
                "start_time": {"type": "number", "description": "TTS başlangıç zamanı (saniye)"},
                "music_volume": {"type": "number", "description": "Müzik ses seviyesi 0.0–1.0 (smart_mix: varsayılan 0.3)"},
                "fade_in": {"type": "number", "description": "Müzik fade-in süresi (saniye)"},
                "fade_out": {"type": "number", "description": "Müzik fade-out süresi (saniye)"},
                "video_duration": {"type": "number", "description": "Beat cut list: video süresi (saniye)"},
                "num_cuts": {"type": "integer", "description": "Beat cut list: kaç kesim noktası"}
            },
            "required": ["operation"]
        }
    },
    # 37. Tool: Resize Image — Tek görsel birçok boyut
    {
        "name": "resize_image",
        "description": "Görseli farklı aspect ratio'lara AI ile dönüştür. Kenarları kırpmadan akıllıca doldurur. Kullanıcı '16:9 yap', 'Instagram story formatı', 'dikey çevir', 'farklı boyutlarda ver' istediğinde kullan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_url": {"type": "string", "description": "Kaynak görsel URL'si"},
                "target_ratios": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["21:9", "16:9", "3:2", "4:3", "5:4", "1:1", "4:5", "3:4", "2:3", "9:16"]},
                    "description": "Hedef boyutlar listesi. Örn: ['16:9', '9:16'] veya tek ['16:9']. Birden fazla verilirse her biri paralel üretilir."
                },
                "prompt": {"type": "string", "description": "Opsiyonel: Doldurma sırasında ek talimat (ör: 'sahil arka planı ekle'). Yoksa doğal doldurma yapılır."},
                "resolution": {"type": "string", "enum": ["0.5K", "1K", "2K", "4K"], "description": "Çıktı çözünürlüğü. Varsayılan: 1K"}
            },
            "required": ["image_url", "target_ratios"]
        }
    }
]

# OpenAI tools formatı
AGENT_TOOLS = convert_to_openai_tools(AGENT_TOOLS_ANTHROPIC)
