"""
Prompt çeviri ve zenginleştirme servisi.
Türkçe promptları görsel üretim için optimize edilmiş İngilizce'ye çevirir.
Her görsel üretimde prompt'u ChatGPT/Gemini seviyesine yaklaştırır.

GPT-4o kullanır (OpenAI) - Claude'dan geçiş yapıldı.
"""
from openai import OpenAI
from app.core.config import settings

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY or "sk-placeholder")
    return _client

# Tüm görsel üretimlerde kullanılacak standart negatif prompt
STANDARD_NEGATIVE_PROMPT = (
    "blurry, low quality, distorted, bad anatomy, deformed, disfigured, "
    "text, watermark, signature, grain, noise, ugly, low resolution, "
    "oversaturated, underexposed, overexposed, cropped, out of frame, "
    "extra limbs, extra fingers, mutated hands, poorly drawn face, "
    "duplicate, morbid, mutilated, poorly drawn hands, missing arms, "
    "missing legs, extra arms, extra legs, fused fingers, too many fingers, "
    "long neck, username, error, jpeg artifacts"
)


async def translate_prompt_to_english(turkish_prompt: str, context: str = "") -> str:
    """
    Türkçe prompt'u İngilizce'ye çevirir ve görsel üretim için optimize eder.
    
    Args:
        turkish_prompt: Kullanıcının Türkçe prompt'u
        context: Ek bağlam (karakter özellikleri, lokasyon vs.)
    
    Returns:
        Optimize edilmiş İngilizce prompt
    """
    system_prompt = """You are a world-class prompt engineer for AI image generation (Flux, DALL-E, Stable Diffusion).
You transform simple requests into stunning, photorealistic image prompts.

Rules:
1. Translate non-English text to English
2. ALWAYS add these quality boosters:
   - Lighting: cinematic lighting, volumetric light, soft rim lighting, golden hour, studio lighting
   - Camera: shallow depth of field, bokeh, 85mm lens, rule of thirds composition
   - Quality: 8K UHD, ultra-realistic, hyper-detailed, professional photography, RAW photo
   - Texture: natural skin pores, fine fabric detail, sharp focus, high dynamic range
   - Color: natural color grading, rich tonal range, vibrant yet realistic colors
3. Add scene atmosphere: mood, environment details, background elements
4. For people: realistic skin texture, natural expression, detailed eyes, subsurface scattering
5. For landscapes/objects: intricate details, atmospheric perspective, realistic materials
6. Keep the CORE subject and intent — don't change what the user wants, enhance HOW it looks
7. Output ONLY the final prompt, nothing else. Max 150 words.

Examples of enhancement:
- Input: "uçan araba" → "Futuristic flying car hovering above a neon-lit cyberpunk cityscape at dusk, volumetric fog, cinematic lighting, reflective chrome body, motion blur on background, 8K UHD, hyper-realistic, shallow depth of field, dramatic sky with orange and purple gradient"
- Input: "güneş batan deniz" → "Breathtaking ocean sunset panorama, golden hour light reflecting on calm turquoise water, dramatic cumulus clouds painted in orange and pink, sun barely touching the horizon, volumetric god rays, 8K professional photography, ultra-wide lens, HDR, natural color grading"
"""

    user_message = f"""Turkish prompt to translate and enhance:
{turkish_prompt}

{f"Additional context: {context}" if context else ""}"""

    response = _get_client().chat.completions.create(
        model="gpt-4o-mini",  # Hızlı ve ucuz model - sadece çeviri için
        max_tokens=500,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    )
    
    return response.choices[0].message.content.strip()


async def enhance_character_prompt(
    base_prompt: str,
    physical_attributes: dict = None
) -> str:
    """
    Karakter prompt'unu fiziksel özelliklerle zenginleştirir.
    
    Args:
        base_prompt: Temel karakter açıklaması
        physical_attributes: Fiziksel özellikler dict'i
            - eye_color: Göz rengi
            - hair_color: Saç rengi  
            - hair_style: Saç stili
            - eyebrow_color: Kaş rengi
            - eyebrow_shape: Kaş şekli
            - skin_tone: Ten rengi
            - age: Yaş
            - gender: Cinsiyet
            - facial_features: Yüz özellikleri
            - body_type: Vücut tipi
            - height: Boy
            - clothing: Kıyafet
    
    Returns:
        Zenginleştirilmiş İngilizce karakter prompt'u
    """
    if not physical_attributes:
        physical_attributes = {}
    
    # Fiziksel özellikleri prompt'a dönüştür
    attribute_parts = []
    
    attr_map = {
        "eye_color": "eyes",
        "hair_color": "hair",
        "hair_style": "hairstyle",
        "eyebrow_color": "eyebrows",
        "eyebrow_shape": "eyebrow shape",
        "skin_tone": "skin",
        "age": "age",
        "gender": "",
        "facial_features": "face",
        "body_type": "build",
        "height": "height",
        "clothing": "wearing"
    }
    
    for key, value in physical_attributes.items():
        if value and key in attr_map:
            label = attr_map[key]
            if label:
                attribute_parts.append(f"{value} {label}")
            else:
                attribute_parts.append(value)
    
    attributes_str = ", ".join(attribute_parts) if attribute_parts else ""
    
    system_prompt = """You are an expert at creating detailed character descriptions for AI image generation.

Your task:
1. Take the base description and physical attributes
2. Create a cohesive, detailed character portrait prompt
3. Add professional photography terms for best quality
4. Include realistic details (skin texture, pores, realistic lighting)
5. Make the prompt optimized for photorealistic AI image generation

Output ONLY the final English prompt. No explanations."""

    user_message = f"""Base character description:
{base_prompt}

Physical attributes: {attributes_str if attributes_str else "Not specified - use reasonable defaults"}

Create a detailed, photorealistic character portrait prompt."""

    response = _get_client().chat.completions.create(
        model="gpt-4o-mini",  # Hızlı ve ucuz model
        max_tokens=600,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    )
    
    return response.choices[0].message.content.strip()


async def enrich_prompt(prompt: str) -> str:
    """
    Entity olmayan genel promptları zenginleştirir.
    translate_to_english zaten çeviri + temel zenginleştirme yapıyor,
    bu fonksiyon ek bir katman olarak cinematic kalite ekler.
    
    Kullanım: Entity referansı olmayan saf text-to-image üretimleri.
    """
    if len(prompt.strip()) < 5:
        return prompt
    
    system_prompt = """You are a cinematic prompt enhancer. Take the given image generation prompt and make it MORE vivid and photorealistic.

Add ONLY what's missing:
- If no lighting mentioned: add cinematic lighting, volumetric light
- If no camera details: add shallow depth of field, professional composition
- If no quality terms: add 8K, ultra-realistic, RAW photo quality
- If no atmosphere: add mood and environment details

Do NOT change the subject. Output ONLY the enhanced prompt. Max 120 words."""
    
    try:
        response = _get_client().chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=400,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return prompt  # Hata durumunda orijinal prompt'u döndür


# Convenience function - translates any non-English text
async def translate_to_english(text: str) -> tuple[str, bool]:
    """
    Metni İngilizce'ye çevirir (hangi dilde olursa olsun).
    Eğer metin zaten İngilizce ise ya da çok kısa ise çevirmez.
    
    Returns:
        (translated_text, was_translated)
    """
    # Çok kısa metinleri çevirme
    if len(text.strip()) < 5:
        return text, False
    
    # Her zaman çevir (optimized English prompt için)
    translated = await translate_prompt_to_english(text)
    return translated, True
