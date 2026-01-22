"""
UI 自动化模块 - 使用 uiautomator2 实现 Android UI 自动化操作

设计原则:
1. 优先使用 Intent 和 ADB 命令,避免 UI 坐标依赖
2. UI 操作必须有超时和重试机制
3. 每个 UI 操作前验证元素是否存在
4. 支持多语言关键词匹配
"""

import time
import logging
from typing import List, Callable, Optional, Dict, Any, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    import uiautomator2 as u2
else:
    try:
        import uiautomator2 as u2
    except ImportError:
        u2 = None
        logging.warning("uiautomator2 未安装,UI 自动化功能将不可用")

logger = logging.getLogger(__name__)


class UIAutomation:
    """UI 自动化操作封装"""
    
    def __init__(self, device_serial: Optional[str] = None):
        """
        初始化 UI 自动化
        
        Args:
            device_serial: 设备序列号,为 None 时连接默认设备
        """
        if u2 is None:
            raise RuntimeError("uiautomator2 未安装,请运行: pip install uiautomator2")
        
        self.device_serial = device_serial
        self.d: Optional[Any] = None  # 使用 Any 避免类型检查问题
        self.default_timeout = 10
        self.default_check_interval = 0.5
    
    def connect(self) -> Any:
        """连接到设备"""
        if self.d is None:
            logger.info(f"连接到设备: {self.device_serial or '默认设备'}")
            self.d = u2.connect(self.device_serial) if self.device_serial else u2.connect()
            logger.info(f"设备信息: {self.d.info}")
        return self.d
    
    def disconnect(self):
        """断开设备连接"""
        if self.d:
            self.d = None
            logger.info("已断开设备连接")
    
    # ==================== 通用 UI 等待函数 ====================
    
    def wait_for_ui_element(
        self,
        selector: Callable[[Any], Any],
        timeout: Optional[int] = None,
        check_interval: Optional[float] = None
    ) -> bool:
        """
        等待 UI 元素出现
        
        Args:
            selector: 元素选择器函数
            timeout: 超时时间(秒)
            check_interval: 检查间隔(秒)
        
        Returns:
            bool: 元素是否出现
        """
        d = self.connect()
        timeout = timeout or self.default_timeout
        check_interval = check_interval or self.default_check_interval
        
        deadline = time.time() + timeout
        
        while time.time() < deadline:
            try:
                element = selector(d)
                if element.exists:
                    logger.debug(f"UI 元素已出现")
                    return True
            except Exception as e:
                logger.debug(f"检查 UI 元素时出错: {e}")
            
            time.sleep(check_interval)
        
        logger.warning(f"等待 UI 元素超时({timeout}秒)")
        return False
    
    def click_by_keywords(
        self,
        keywords: List[str],
        timeout: int = 5
    ) -> bool:
        """
        根据关键词列表尝试点击按钮
        
        Args:
            keywords: 关键词列表
            timeout: 超时时间(秒)
        
        Returns:
            bool: 是否成功点击
        """
        d = self.connect()
        deadline = time.time() + timeout
        
        while time.time() < deadline:
            for keyword in keywords:
                try:
                    # 尝试精确匹配
                    if d(text=keyword).exists:
                        logger.info(f"点击按钮: {keyword}")
                        d(text=keyword).click()
                        time.sleep(0.5)
                        return True
                    
                    # 尝试模糊匹配
                    if d(textContains=keyword).exists:
                        logger.info(f"点击按钮(模糊匹配): {keyword}")
                        d(textContains=keyword).click()
                        time.sleep(0.5)
                        return True
                except Exception as e:
                    logger.debug(f"点击关键词 '{keyword}' 失败: {e}")
            
            time.sleep(0.5)
        
        logger.warning(f"未找到可点击的关键词: {keywords}")
        return False
    
    def find_switch_by_label(
        self,
        label: str,
        timeout: int = 5
    ) -> Optional[Any]:
        """
        根据标签查找开关控件
        
        Args:
            label: 开关标签文本
            timeout: 超时时间(秒)
        
        Returns:
            Optional[u2.UiObject]: 开关控件对象,未找到返回 None
        """
        d = self.connect()
        deadline = time.time() + timeout
        
        while time.time() < deadline:
            try:
                # 方法 1: 查找包含标签的 Switch 控件
                switch = d(text=label, className="android.widget.Switch")
                if switch.exists:
                    return switch
                
                # 方法 2: 查找标签旁边的 Switch
                if d(text=label).exists:
                    # 获取标签的父容器
                    parent = d(text=label).parent()
                    # 在父容器中查找 Switch
                    switch = parent.child(className="android.widget.Switch")
                    if switch.exists:
                        return switch
                
                # 方法 3: 模糊匹配
                switch = d(textContains=label, className="android.widget.Switch")
                if switch.exists:
                    return switch
                
            except Exception as e:
                logger.debug(f"查找开关控件失败: {e}")
            
            time.sleep(0.5)
        
        logger.warning(f"未找到开关控件: {label}")
        return None
    
    # ==================== 系统初始化向导自动化 ====================
    
    def complete_setup_wizard(
        self,
        skip_keywords: Optional[List[str]] = None,
        next_keywords: Optional[List[str]] = None,
        agree_keywords: Optional[List[str]] = None,
        max_steps: int = 20
    ) -> bool:
        """
        完成 Android 初始化向导
        
        Args:
            skip_keywords: "跳过"按钮的关键词列表
            next_keywords: "下一步"按钮的关键词列表
            agree_keywords: "同意"按钮的关键词列表
            max_steps: 最多尝试步数
        
        Returns:
            bool: 是否成功完成
        """
        d = self.connect()
        
        # 默认关键词
        skip_keywords = skip_keywords or ["跳过", "Skip", "不使用", "Not now", "No thanks"]
        next_keywords = next_keywords or ["下一步", "Next", "继续", "Continue", "开始", "Start"]
        agree_keywords = agree_keywords or ["同意", "Agree", "接受", "Accept", "我同意", "I agree"]
        
        logger.info("开始完成初始化向导")
        
        for step in range(max_steps):
            logger.debug(f"初始化向导步骤 {step + 1}/{max_steps}")
            
            # 检查是否已完成(进入主屏幕)
            if self._is_on_home_screen():
                logger.info("✅ 初始化向导已完成")
                return True
            
            # 尝试点击"跳过"
            if self.click_by_keywords(skip_keywords, timeout=2):
                continue
            
            # 尝试点击"下一步"
            if self.click_by_keywords(next_keywords, timeout=2):
                continue
            
            # 尝试点击"同意"
            if self.click_by_keywords(agree_keywords, timeout=2):
                continue
            
            # 如果没有可点击的按钮,等待 2 秒
            logger.debug("未找到可点击的按钮,等待...")
            time.sleep(2)
        
        logger.warning("初始化向导可能未完成,请手动检查")
        return False
    
    def _is_on_home_screen(self) -> bool:
        """检查是否在主屏幕"""
        d = self.connect()
        
        # 检查常见的 Launcher 标识
        launcher_ids = [
            "com.google.android.apps.nexuslauncher:id/workspace",
            "com.android.launcher3:id/workspace",
            "com.google.android.apps.nexuslauncher:id/hotseat",
        ]
        
        for launcher_id in launcher_ids:
            if d(resourceId=launcher_id).exists:
                return True
        
        # 检查是否有应用图标
        if d(className="android.widget.ImageView", clickable=True).count > 5:
            return True
        
        return False
    
    def skip_wifi_setup(self) -> bool:
        """跳过 WiFi 设置"""
        logger.info("跳过 WiFi 设置")
        return self.click_by_keywords(["跳过", "Skip", "稍后设置", "Set up later"])
    
    def skip_google_account(self) -> bool:
        """跳过 Google 账号登录"""
        logger.info("跳过 Google 账号登录")
        return self.click_by_keywords(["跳过", "Skip", "稍后", "Later", "不使用", "No thanks"])
    
    # ==================== 开发者模式自动化 ====================
    
    def enable_developer_mode(
        self,
        about_phone_keywords: Optional[List[str]] = None,
        build_number_keywords: Optional[List[str]] = None
    ) -> bool:
        """
        开启开发者模式
        
        Args:
            about_phone_keywords: "关于手机"的关键词列表
            build_number_keywords: "版本号"的关键词列表
        
        Returns:
            bool: 是否成功开启
        """
        d = self.connect()
        
        about_phone_keywords = about_phone_keywords or ["关于手机", "About phone", "About device"]
        build_number_keywords = build_number_keywords or ["版本号", "Build number"]
        
        logger.info("开始开启开发者模式")
        
        try:
            # 1. 打开设置
            d.app_start("com.android.settings")
            time.sleep(2)
            
            # 2. 导航到"关于手机"
            if not self._find_and_click_by_keywords(about_phone_keywords):
                logger.error("未找到'关于手机'")
                return False
            time.sleep(1)
            
            # 3. 点击"版本号" 7 次
            logger.info("点击'版本号' 7 次")
            for i in range(7):
                if not self._find_and_click_by_keywords(build_number_keywords):
                    logger.error(f"第 {i + 1} 次点击'版本号'失败")
                    return False
                time.sleep(0.3)
            
            # 4. 检测是否出现"您已处于开发者模式"
            time.sleep(1)
            if d(textContains="开发者模式").exists or d(textContains="Developer mode").exists:
                logger.info("✅ 开发者模式已开启")
                return True
            else:
                logger.warning("未检测到开发者模式提示,但可能已开启")
                return True
            
        except Exception as e:
            logger.error(f"开启开发者模式失败: {e}")
            return False
        finally:
            # 返回主屏幕
            d.press("home")
    
    def enable_usb_debugging(
        self,
        system_keywords: Optional[List[str]] = None,
        developer_options_keywords: Optional[List[str]] = None,
        usb_debugging_keywords: Optional[List[str]] = None
    ) -> bool:
        """
        开启 USB 调试
        
        Args:
            system_keywords: "系统"的关键词列表
            developer_options_keywords: "开发者选项"的关键词列表
            usb_debugging_keywords: "USB 调试"的关键词列表
        
        Returns:
            bool: 是否成功开启
        """
        d = self.connect()
        
        system_keywords = system_keywords or ["系统", "System"]
        developer_options_keywords = developer_options_keywords or ["开发者选项", "开发人员选项", "Developer options"]
        usb_debugging_keywords = usb_debugging_keywords or ["USB 调试", "USB调试", "USB debugging"]
        
        logger.info("开始开启 USB 调试")
        
        try:
            # 1. 打开设置
            d.app_start("com.android.settings")
            time.sleep(2)
            
            # 2. 进入"系统"
            if not self._find_and_click_by_keywords(system_keywords):
                logger.warning("未找到'系统',尝试直接查找'开发者选项'")
            else:
                time.sleep(1)
            
            # 3. 进入"开发者选项"
            if not self._find_and_click_by_keywords(developer_options_keywords):
                logger.error("未找到'开发者选项'")
                return False
            time.sleep(1)
            
            # 4. 开启 USB 调试
            usb_debug_switch = None
            for keyword in usb_debugging_keywords:
                usb_debug_switch = self.find_switch_by_label(keyword)
                if usb_debug_switch:
                    break
            
            if not usb_debug_switch:
                logger.error("未找到 USB 调试开关")
                return False
            
            # 检查是否已开启
            if usb_debug_switch.info.get("checked"):
                logger.info("USB 调试已经开启")
                return True
            
            # 点击开关
            logger.info("点击 USB 调试开关")
            usb_debug_switch.click()
            time.sleep(1)
            
            # 5. 确认授权弹窗
            if d(text="确定").exists or d(text="允许").exists or d(text="OK").exists:
                logger.info("确认 USB 调试授权")
                if d(text="确定").exists:
                    d(text="确定").click()
                elif d(text="允许").exists:
                    d(text="允许").click()
                else:
                    d(text="OK").click()
                time.sleep(1)
            
            logger.info("✅ USB 调试已开启")
            return True
            
        except Exception as e:
            logger.error(f"开启 USB 调试失败: {e}")
            return False
        finally:
            # 返回主屏幕
            d.press("home")
    
    def _find_and_click_by_keywords(
        self,
        keywords: List[str],
        scroll_if_not_found: bool = True
    ) -> bool:
        """
        查找并点击包含关键词的元素
        
        Args:
            keywords: 关键词列表
            scroll_if_not_found: 如果未找到是否滚动查找
        
        Returns:
            bool: 是否成功点击
        """
        d = self.connect()
        
        for keyword in keywords:
            # 先尝试直接查找
            if d(text=keyword).exists:
                d(text=keyword).click()
                return True
            if d(textContains=keyword).exists:
                d(textContains=keyword).click()
                return True
        
        # 如果未找到且允许滚动,尝试滚动查找
        if scroll_if_not_found:
            for keyword in keywords:
                try:
                    if d(scrollable=True).exists:
                        d(scrollable=True).scroll.to(text=keyword)
                        if d(text=keyword).exists:
                            d(text=keyword).click()
                            return True
                except Exception:
                    pass
        
        return False
    
    # ==================== APatch 操作自动化 ====================
    
    def open_apatch(self, package_name: str = "me.bmax.apatch") -> bool:
        """
        打开 APatch 应用
        
        Args:
            package_name: APatch 包名
        
        Returns:
            bool: 是否成功打开
        """
        d = self.connect()
        
        try:
            logger.info(f"打开 APatch 应用: {package_name}")
            d.app_start(package_name)
            time.sleep(2)
            return True
        except Exception as e:
            logger.error(f"打开 APatch 失败: {e}")
            return False
    
    def input_apatch_password(self, password: str) -> bool:
        """
        输入 APatch 密码
        
        Args:
            password: 密码
        
        Returns:
            bool: 是否成功输入
        """
        d = self.connect()
        
        try:
            # 查找密码输入框
            if d(className="android.widget.EditText").exists:
                logger.info("输入 APatch 密码")
                d(className="android.widget.EditText").set_text(password)
                d.press("enter")
                time.sleep(2)
                return True
            else:
                logger.warning("未找到密码输入框,可能已登录")
                return True
        except Exception as e:
            logger.error(f"输入密码失败: {e}")
            return False
    
    def patch_boot_img(self, boot_img_path: str) -> bool:
        """
        通过 UI 自动化修补 boot.img
        
        Args:
            boot_img_path: boot.img 在设备上的路径
        
        Returns:
            bool: 是否成功修补
        """
        d = self.connect()
        
        try:
            logger.info("开始修补 boot.img")
            
            # 1. 查找"修补"或"Patch"按钮
            patch_keywords = ["修补", "Patch", "安装", "Install"]
            if not self.click_by_keywords(patch_keywords, timeout=5):
                logger.error("未找到修补按钮")
                return False
            
            time.sleep(1)
            
            # 2. 选择 boot.img 文件
            if not self._select_file_from_picker(boot_img_path):
                logger.error("选择 boot.img 失败")
                return False
            
            # 3. 等待修补完成
            logger.info("等待修补完成...")
            if self.wait_for_ui_element(
                lambda d: d(textContains="成功") or d(textContains="Success") or d(textContains="完成"),
                timeout=300  # 5 分钟超时
            ):
                logger.info("✅ boot.img 修补完成")
                return True
            else:
                logger.error("修补超时或失败")
                return False
            
        except Exception as e:
            logger.error(f"修补 boot.img 失败: {e}")
            return False
    
    def install_apatch_modules(
        self,
        module_files: List[str],
        password: Optional[str] = None
    ) -> bool:
        """
        自动安装 APatch 模块
        
        Args:
            module_files: 模块文件名列表
            password: APatch 密码(如果需要)
        
        Returns:
            bool: 是否全部安装成功
        """
        d = self.connect()
        
        try:
            # 1. 打开 APatch
            if not self.open_apatch():
                return False
            
            # 2. 输入密码(如果需要)
            if password:
                self.input_apatch_password(password)
            
            # 3. 导航到模块管理页面
            module_keywords = ["模块", "Module", "Modules"]
            if not self.click_by_keywords(module_keywords, timeout=5):
                logger.warning("未找到模块入口,尝试其他方式")
                # 尝试点击菜单
                if d(description="更多选项").exists or d(description="More options").exists:
                    (d(description="更多选项") if d(description="更多选项").exists else d(description="More options")).click()
                    time.sleep(0.5)
                    if not self.click_by_keywords(["模块管理", "Module manager"], timeout=3):
                        logger.error("无法进入模块管理页面")
                        return False
            
            time.sleep(2)
            
            # 4. 逐个安装模块
            success_count = 0
            for module_file in module_files:
                if self._install_single_module(module_file):
                    success_count += 1
                else:
                    logger.warning(f"模块 {module_file} 安装失败")
            
            logger.info(f"模块安装完成: {success_count}/{len(module_files)}")
            
            # 5. 提示重启
            if success_count > 0:
                logger.info("所有模块安装完成,建议重启设备以激活模块")
            
            return success_count == len(module_files)
            
        except Exception as e:
            logger.error(f"安装模块失败: {e}")
            return False
    
    def _install_single_module(self, module_file: str) -> bool:
        """安装单个模块"""
        d = self.connect()
        
        try:
            logger.info(f"正在安装模块: {module_file}")
            
            # 1. 点击"安装"或"+"按钮
            install_keywords = ["安装", "Install", "添加", "Add"]
            if not self.click_by_keywords(install_keywords, timeout=3):
                # 尝试点击 FAB 按钮
                if d(className="android.widget.ImageButton", clickable=True).exists:
                    d(className="android.widget.ImageButton", clickable=True).click()
                else:
                    logger.error("未找到安装按钮")
                    return False
            
            time.sleep(1)
            
            # 2. 选择文件
            if not self._select_file_from_picker(module_file):
                return False
            
            # 3. 等待安装完成
            if self.wait_for_ui_element(
                lambda d: d(textContains="成功") or d(textContains="Success"),
                timeout=30
            ):
                logger.info(f"✅ 模块 {module_file} 安装成功")
                time.sleep(2)
                return True
            else:
                logger.warning(f"模块 {module_file} 安装可能失败")
                return False
                
        except Exception as e:
            logger.error(f"安装模块 {module_file} 失败: {e}")
            return False
    
    def _select_file_from_picker(self, filename: str) -> bool:
        """从文件选择器中选择文件"""
        d = self.connect()
        
        try:
            # 显示根目录
            if d(description="显示根目录").exists or d(description="Show roots").exists:
                (d(description="显示根目录") if d(description="显示根目录").exists else d(description="Show roots")).click()
                time.sleep(1)
            
            # 导航到 Download 目录
            download_keywords = ["Download", "下载", "Downloads"]
            for keyword in download_keywords:
                if d(text=keyword).exists or d(textContains=keyword).exists:
                    (d(text=keyword) if d(text=keyword).exists else d(textContains=keyword)).click()
                    time.sleep(1)
                    break
            
            # 选择文件
            if d(textContains=filename).exists:
                d(textContains=filename).click()
                time.sleep(1)
                return True
            
            # 如果未找到,尝试滚动查找
            if d(scrollable=True).exists:
                d(scrollable=True).scroll.to(textContains=filename)
                if d(textContains=filename).exists:
                    d(textContains=filename).click()
                    time.sleep(1)
                    return True
            
            logger.error(f"未找到文件: {filename}")
            return False
            
        except Exception as e:
            logger.error(f"选择文件失败: {e}")
            return False
