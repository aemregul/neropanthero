"""
Veritabanı modelleri.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ============== KULLANICI ==============

class User(Base):
    """Kullanıcı modeli."""
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # OAuth users may not have password
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # OAuth fields
    google_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Tek Asistan: her kullanıcının bir ana chat session'ı var
    main_chat_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    
    sessions: Mapped[list["Session"]] = relationship(back_populates="user")


# ============== OTURUM ==============

class Session(Base):
    """Proje oturumu — her proje bir session'dır."""
    __tablename__ = "sessions"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), default="Yeni Proje")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, default=dict)
    
    # Proje metadata alanları
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # reklam, sosyal_medya, film, kişisel
    cover_image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    project_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)  # Stil, marka, ek veri
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    user: Mapped["User"] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(back_populates="session")
    entities: Mapped[list["Entity"]] = relationship(back_populates="session")
    tasks: Mapped[list["Task"]] = relationship(back_populates="session")


# ============== MESAJ ==============

class Message(Base):
    """Sohbet mesajı."""
    __tablename__ = "messages"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    session: Mapped["Session"] = relationship(back_populates="messages")


# ============== VARLIK (ENTITY) ==============

class Entity(Base):
    """Karakter, mekan, kostüm, nesne."""
    __tablename__ = "entities"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Entity artık user'a bağlı - proje silinse de entity kalır!
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)  # 📈 INDEX
    # Session opsiyonel - entity belirli bir projeyle ilişkilendirilebilir ama zorunlu değil
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)  # 📈 INDEX
    entity_type: Mapped[str] = mapped_column(String(50), index=True)  # 📈 INDEX
    name: Mapped[str] = mapped_column(String(255))
    tag: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    
    # Referans görsel (yüz/vücut tutarlılığı için)
    reference_image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)  # 📈 INDEX
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Faz 2 hazırlık
    embedding_vector: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    
    user: Mapped["User"] = relationship("User")
    session: Mapped[Optional["Session"]] = relationship(back_populates="entities")
    assets: Mapped[list["EntityAsset"]] = relationship(back_populates="entity")


# ============== ÜRETİLEN ASSET ==============

class GeneratedAsset(Base):
    """Üretilen görsel/video."""
    __tablename__ = "generated_assets"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"))
    task_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    asset_type: Mapped[str] = mapped_column(String(50))
    url: Mapped[str] = mapped_column(String(1024))
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model_params: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Akıllı Agent özellikleri
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("generated_assets.id", ondelete="SET NULL"), 
        nullable=True
    )
    
    # Faz 2 hazırlık
    embedding_vector: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    
    entity_links: Mapped[list["EntityAsset"]] = relationship(back_populates="asset")
    task: Mapped[Optional["Task"]] = relationship(back_populates="assets")
    
    # Parent-child ilişkisi
    parent_asset: Mapped[Optional["GeneratedAsset"]] = relationship(
        "GeneratedAsset", 
        remote_side="GeneratedAsset.id",
        backref="child_assets"
    )


# ============== VARLIK-ASSET BAĞLANTISI ==============

class EntityAsset(Base):
    """Varlık-Asset ilişkisi."""
    __tablename__ = "entity_assets"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"))
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("generated_assets.id", ondelete="CASCADE"))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    entity: Mapped["Entity"] = relationship(back_populates="assets")
    asset: Mapped["GeneratedAsset"] = relationship(back_populates="entity_links")


# ============== GÖREV ==============

class Task(Base):
    """İş akışı görevi."""
    __tablename__ = "tasks"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"))
    parent_task_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    task_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="pending")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    input_data: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    output_data: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    session: Mapped["Session"] = relationship(back_populates="tasks")
    assets: Mapped[list["GeneratedAsset"]] = relationship(back_populates="task")
    subtasks: Mapped[list["Task"]] = relationship(back_populates="parent_task")
    parent_task: Mapped[Optional["Task"]] = relationship(back_populates="subtasks", remote_side="Task.id")


# ============== AGENT DURUMU ==============

class AgentState(Base):
    """Agent beyin durumu."""
    __tablename__ = "agent_states"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), unique=True)
    current_goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_plan: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    context_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    working_memory: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ============== PLUGİN ==============

class Plugin(Base):
    """Plugin tanımları."""
    __tablename__ = "plugins"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(50), default="1.0.0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    capabilities: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============== KULLANICI AYARLARI ==============

class UserSettings(Base):
    """Kullanıcı ayarları."""
    __tablename__ = "user_settings"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    theme: Mapped[str] = mapped_column(String(50), default="dark")
    language: Mapped[str] = mapped_column(String(10), default="tr")
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_save: Mapped[bool] = mapped_column(Boolean, default=True)
    default_model: Mapped[str] = mapped_column(String(100), default="claude")
    settings_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ============== AI MODELLERİ ==============

class AIModel(Base):
    """AI model tanımları."""
    __tablename__ = "ai_models"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    model_type: Mapped[str] = mapped_column(String(50))  # llm, image, video, audio
    provider: Mapped[str] = mapped_column(String(100))  # anthropic, openai, fal, etc.
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(10), default="🤖")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_api_key: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============== YÜKLÜ PLUGİNLER ==============

class InstalledPlugin(Base):
    """Kullanıcının yüklediği pluginler."""
    __tablename__ = "installed_plugins"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    plugin_id: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(10), default="🔌")
    category: Mapped[str] = mapped_column(String(50), default="general")
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============== KULLANIM İSTATİSTİKLERİ ==============

class UsageStats(Base):
    """API kullanım istatistikleri."""
    __tablename__ = "usage_stats"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    api_calls: Mapped[int] = mapped_column(Integer, default=0)
    images_generated: Mapped[int] = mapped_column(Integer, default=0)
    videos_generated: Mapped[int] = mapped_column(Integer, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============== PRESETLER (Kullanıcı Tanımlı) ==============

class Preset(Base):
    """Kullanıcının oluşturduğu özel presetler."""
    __tablename__ = "presets"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(10), default="✨")
    color: Mapped[str] = mapped_column(String(20), default="#22c55e")
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ============== ÇÖP KUTUSU ==============

class TrashItem(Base):
    """Silinen öğeler."""
    __tablename__ = "trash_items"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    item_type: Mapped[str] = mapped_column(String(50))  # entity, asset, session, plugin
    item_id: Mapped[str] = mapped_column(String(100))
    item_name: Mapped[str] = mapped_column(String(255))
    original_data: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # 3 gün sonra silinecek


# ============== KULLANICI TERCİHLERİ (AGENT İÇİN) ==============

class UserPreferences(Base):
    """
    Agent için kullanıcı tercihleri.
    Görsel üretim, video, stil tercihleri vb.
    """
    __tablename__ = "user_preferences"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    
    # Görsel tercihleri
    default_aspect_ratio: Mapped[str] = mapped_column(String(20), default="16:9")
    default_style: Mapped[str] = mapped_column(String(50), default="realistic")  # realistic, anime, illustration, etc.
    default_image_model: Mapped[str] = mapped_column(String(100), default="fal-ai/flux-pro/v1.1-ultra")
    
    # Video tercihleri
    default_video_model: Mapped[str] = mapped_column(String(100), default="fal-ai/kling-video/v1.5/pro/text-to-video")
    default_video_duration: Mapped[int] = mapped_column(Integer, default=5)  # saniye
    
    # Agent davranış tercihleri
    auto_face_swap: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_upscale: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_translate_prompts: Mapped[bool] = mapped_column(Boolean, default=True)  # TR→EN
    
    # Dil tercihi
    response_language: Mapped[str] = mapped_column(String(10), default="tr")
    
    # Favori entity'ler (JSON array of tags)
    favorite_entities: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    
    # Öğrenilmiş tercihler (agent tarafından güncellenir)
    learned_preferences: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    # Örn: {"preferred_colors": ["#FF0000"], "common_prompts": ["professional photo"]}
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    user: Mapped["User"] = relationship("User")


