"""
设备适配器 - Device Adapter

提供设备无关的抽象接口，支持多型号、多语言
"""

from abc import ABC, abstractmethod
from typing import List, Dict
from pathlib import Path
import yaml
from loguru import logger


class DeviceAdapter(ABC):
    """设备适配器基类"""
    
    def __init__(self, model: str, language: str = "zh_CN"):
        """
        初始化设备适配器
        
        Args:
            model: 设备型号
            language: UI 语言
        """
        self.model = model
        self.language = language
        self.config_path = Path(f"devices/{model}/config.yaml")
        self.config = self._load_config()
        self.keywords = self.config.get("ui", {}).get("keywords", {})
    
    def _load_config(self) -> Dict:
        """加载设备配置"""
        if not self.config_path.exists():
            logger.warning(f"设备配置不存在: {self.config_path}")
            return {}
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    
    @abstractmethod
    def get_ui_keywords(self, key: str) -> List[str]:
        """
        获取 UI 元素关键词（支持多语言）
        
        Args:
            key: 关键词键名
        
        Returns:
            关键词列表
        """
        pass
    
    @abstractmethod
    def get_settings_path(self) -> List[str]:
        """
        获取设置应用的导航路径
        
        Returns:
            导航路径列表
        """
        pass
    
    def get_flash_script(self) -> str:
        """
        获取刷机脚本路径
        
        Returns:
            刷机脚本路径
        """
        import platform
        
        if platform.system() == "Windows":
            script_key = "flash_script_windows"
        else:
            script_key = "flash_script_unix"
        
        return self.config.get("resources", {}).get(script_key, "")


class PixelAdapter(DeviceAdapter):
    """Pixel 系列通用适配器"""
    
    def __init__(self, model: str, language: str = "zh_CN"):
        super().__init__(model, language)
        logger.info(f"Pixel 适配器初始化: model={model}, language={language}")
    
    def get_ui_keywords(self, key: str) -> List[str]:
        """从配置文件加载关键词"""
        keyword_dict = self.keywords.get(key, {})
        
        # 优先使用指定语言的关键词
        if self.language in keyword_dict:
            return keyword_dict[self.language]
        
        # 回退到英语
        if "en_US" in keyword_dict:
            return keyword_dict["en_US"]
        
        # 返回所有语言的关键词
        all_keywords = []
        for lang_keywords in keyword_dict.values():
            all_keywords.extend(lang_keywords)
        return all_keywords
    
    def get_settings_path(self) -> List[str]:
        """Pixel 设备的设置路径"""
        if self.language == "zh_CN":
            return ["系统", "开发者选项"]
        else:
            return ["System", "Developer options"]


class Pixel5Adapter(PixelAdapter):
    """Pixel 5 专用适配器"""
    
    def __init__(self, language: str = "zh_CN"):
        super().__init__("redfin", language)


class Pixel8Adapter(PixelAdapter):
    """Pixel 8 专用适配器"""
    
    def __init__(self, language: str = "zh_CN"):
        super().__init__("shiba", language)


class DeviceAdapterFactory:
    """设备适配器工厂"""
    
    # 友好名称到代号的映射
    MODEL_ALIASES = {
        "pixel5": "redfin",
        "pixel5a": "barbet",
        "pixel6": "oriole",
        "pixel6pro": "raven",
        "pixel6a": "bluejay",
        "pixel7": "panther",
        "pixel7pro": "cheetah",
        "pixel7a": "lynx",
        "pixel8": "shiba",
        "pixel8pro": "husky",
    }
    
    # 设备型号到适配器的映射
    ADAPTERS = {
        "redfin": Pixel5Adapter,      # Pixel 5
        "barbet": Pixel5Adapter,       # Pixel 5a
        "oriole": PixelAdapter,        # Pixel 6
        "raven": PixelAdapter,         # Pixel 6 Pro
        "bluejay": PixelAdapter,       # Pixel 6a
        "panther": PixelAdapter,       # Pixel 7
        "cheetah": PixelAdapter,       # Pixel 7 Pro
        "lynx": PixelAdapter,          # Pixel 7a
        "shiba": Pixel8Adapter,        # Pixel 8
        "husky": Pixel8Adapter,        # Pixel 8 Pro
    }
    
    @staticmethod
    def create(model: str, language: str = "auto") -> DeviceAdapter:
        """
        根据设备型号创建适配器
        
        Args:
            model: 设备型号（支持友好名称如 pixel5 或代号如 redfin）
            language: UI 语言
        
        Returns:
            设备适配器实例
        
        Raises:
            ValueError: 不支持的设备型号
        """
        # 自动检测语言
        if language == "auto":
            language = "zh_CN"  # 默认中文
        
        # 转换友好名称为代号
        model_code = DeviceAdapterFactory.MODEL_ALIASES.get(model.lower(), model)
        
        adapter_class = DeviceAdapterFactory.ADAPTERS.get(model_code)
        
        if not adapter_class:
            logger.error(f"不支持的设备型号: {model}")
            raise ValueError(f"不支持的设备型号: {model}")
        
        logger.info(f"创建设备适配器: {adapter_class.__name__} (model={model}, code={model_code})")
        return adapter_class(language)
    
    @staticmethod
    def list_supported_devices() -> List[str]:
        """
        列出所有支持的设备型号
        
        Returns:
            设备型号列表
        """
        return list(DeviceAdapterFactory.ADAPTERS.keys())


# 测试代码
if __name__ == "__main__":
    logger.add("logs/device_adapter_test.log", rotation="10 MB")
    
    # 列出支持的设备
    print("支持的设备:")
    for model in DeviceAdapterFactory.list_supported_devices():
        print(f"  - {model}")
    
    # 创建 Pixel 5 适配器
    print("\n创建 Pixel 5 适配器:")
    adapter = DeviceAdapterFactory.create("redfin", "zh_CN")
    
    # 测试关键词获取
    print(f"  系统关键词: {adapter.get_ui_keywords('system')}")
    print(f"  开发者选项关键词: {adapter.get_ui_keywords('developer_options')}")
    print(f"  设置路径: {adapter.get_settings_path()}")
