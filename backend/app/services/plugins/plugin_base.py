"""
Plugin Base - Tüm pluginlerin türetileceği abstract base class.

Minecraft tarzı modüler plugin sistemi.
Pluginler dinamik olarak yüklenip kaldırılabilir.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum


class PluginCategory(str, Enum):
    """Plugin kategorileri."""
    IMAGE_GENERATION = "image_generation"
    VIDEO_GENERATION = "video_generation"
    IMAGE_EDITING = "image_editing"
    VIDEO_EDITING = "video_editing"
    WEB_SCRAPING = "web_scraping"
    AUDIO = "audio"
    ANALYSIS = "analysis"
    UTILITY = "utility"


@dataclass
class PluginInfo:
    """Plugin meta bilgileri."""
    name: str
    display_name: str
    version: str
    description: str
    category: PluginCategory
    author: str = "Nero Panthero"
    requires_api_key: bool = False
    api_key_env_var: Optional[str] = None
    capabilities: list[str] = field(default_factory=list)
    config_schema: dict = field(default_factory=dict)


@dataclass
class PluginResult:
    """Plugin çalışma sonucu."""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None
    cost_estimate: Optional[float] = None


class PluginBase(ABC):
    """
    Abstract Plugin Base Class.
    
    Tüm pluginler bu sınıftan türetilmeli.
    
    Örnek kullanım:
    ```python
    class MyPlugin(PluginBase):
        @property
        def info(self) -> PluginInfo:
            return PluginInfo(
                name="my_plugin",
                display_name="My Plugin",
                ...
            )
        
        async def execute(self, action, params):
            ...
    ```
    """
    
    def __init__(self):
        self._is_enabled = True
        self._config: dict = {}
    
    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """Plugin bilgilerini döndür."""
        pass
    
    @property
    def is_enabled(self) -> bool:
        """Plugin aktif mi?"""
        return self._is_enabled
    
    def enable(self):
        """Plugin'i aktif et."""
        self._is_enabled = True
    
    def disable(self):
        """Plugin'i devre dışı bırak."""
        self._is_enabled = False
    
    def configure(self, config: dict):
        """Plugin ayarlarını güncelle."""
        self._config.update(config)
    
    def get_config(self) -> dict:
        """Plugin ayarlarını döndür."""
        return self._config.copy()
    
    @abstractmethod
    async def execute(self, action: str, params: dict) -> PluginResult:
        """
        Plugin'in ana çalışma metodu.
        
        Args:
            action: Yapılacak işlem (örn: "generate_image", "upscale")
            params: İşlem parametreleri
        
        Returns:
            PluginResult: İşlem sonucu
        """
        pass
    
    @abstractmethod
    def get_available_actions(self) -> list[str]:
        """Plugin'in desteklediği action listesi."""
        pass
    
    def validate_params(self, action: str, params: dict) -> tuple[bool, Optional[str]]:
        """
        Parametre doğrulama (opsiyonel override).
        
        Returns:
            (is_valid, error_message)
        """
        return True, None
    
    async def health_check(self) -> bool:
        """
        Plugin sağlık kontrolü.
        API bağlantısı, credentials vs. kontrol eder.
        """
        return True
    
    def __repr__(self) -> str:
        status = "✅" if self.is_enabled else "❌"
        return f"<{self.info.name} {self.info.version} {status}>"
