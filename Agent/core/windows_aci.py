# File: Agent/core/windows_aci.py
"""
Windows ACI (Action-Context-Interface) 模块
基于 pywinauto 的 UI Automation 实现
参考 PC-Agent 的 WindowsACI 设计
"""
from typing import List, Dict, Tuple, Any, Optional
import pywinauto
from pywinauto import Desktop
import win32gui
import win32process
import psutil


class UIElement:
    """
    UI 元素包装类
    封装 pywinauto 的控件信息，提供统一接口
    """

    def __init__(self, element=None):
        """
        Args:
            element: pywinauto 的 WindowSpecification 或 control wrapper
        """
        if isinstance(element, pywinauto.application.WindowSpecification):
            self.element = element.wrapper_object()
        else:
            self.element = element  # control wrapper

    def get_attribute_names(self) -> List[str]:
        """获取所有可用属性名"""
        try:
            return list(self.element.element_info.get_properties().keys())
        except Exception as e:
            print(f"[UIElement] 获取属性失败：{e}")
            return []

    def attribute(self, key: str) -> Any:
        """获取指定属性值"""
        try:
            props = self.element.element_info.get_properties()
            return props.get(key, None)
        except Exception as e:
            print(f"[UIElement] 获取属性 {key} 失败：{e}")
            return None

    def children(self) -> List['UIElement']:
        """获取子元素列表"""
        try:
            # 特殊处理：如果是 Desktop 对象，返回所有顶层窗口
            from pywinauto import Desktop as PyDesktop
            if isinstance(self.element, PyDesktop):
                # 获取所有可见的顶层窗口
                windows = self.element.windows()
                return [UIElement(w) for w in windows]

            # 普通控件，使用标准的 children() 方法
            return [UIElement(child) for child in self.element.children()]
        except Exception as e:
            print(f"[UIElement] 获取子元素失败：{e}")
            return []

    def role(self) -> str:
        """返回控件类型（如 Button、Edit、Window）"""
        try:
            return self.element.element_info.control_type
        except Exception:
            return "Unknown"

    def position(self) -> Optional[Tuple[int, int]]:
        """返回左上角坐标 (x, y)"""
        try:
            rect = self.element.rectangle()
            return (rect.left, rect.top)
        except Exception:
            return None

    def size(self) -> Optional[Tuple[int, int]]:
        """返回尺寸 (width, height)"""
        try:
            rect = self.element.rectangle()
            return (rect.width(), rect.height())
        except Exception:
            return None

    def title(self) -> str:
        """返回控件标题/名称"""
        try:
            return self.element.element_info.name or ""
        except Exception:
            return ""

    def text(self) -> str:
        """返回控件文本内容"""
        try:
            return self.element.window_text() or ""
        except Exception:
            return ""

    def is_valid(self) -> bool:
        """检查元素是否有效（有位置和尺寸）"""
        return self.position() is not None and self.size() is not None

    def parse(self) -> Dict:
        """解析为字典格式"""
        position = self.position()
        size = self.size()

        return {
            "position": position,
            "size": size,
            "title": self.title(),
            "text": self.text(),
            "role": self.role(),
        }

    @staticmethod
    def system_wide_element() -> 'UIElement':
        """获取系统级根元素（桌面）"""
        desktop = Desktop(backend="uia")
        return UIElement(desktop)

    @staticmethod
    def get_current_applications() -> List[str]:
        """获取当前运行的应用程序列表"""
        apps = []
        for proc in psutil.process_iter(["pid", "name"]):
            apps.append(proc.info["name"])
        return apps

    @staticmethod
    def get_top_app() -> Optional[str]:
        """获取当前最前端的应用程序"""
        try:
            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            for proc in psutil.process_iter(["pid", "name"]):
                if proc.info["pid"] == pid:
                    return proc.info["name"]
        except Exception as e:
            print(f"[UIElement] 获取前端应用失败：{e}")

        return None

    def __repr__(self):
        return f"UIElement({self.element})"


class WindowsACI:
    """
    Windows Action-Context-Interface
    负责从系统 UI Automation 提取界面元素
    """

    def __init__(self, top_app_only: bool = True, ocr: bool = False):
        """
        Args:
            top_app_only: 是否只分析最前端的应用窗口
            ocr: 是否启用 OCR（预留，暂不实现）
        """
        self.top_app_only = top_app_only
        self.ocr = ocr
        self.nodes: List[Dict] = []
        self.index_out_of_range_flag = False

        # 初始化 pywinauto Desktop
        self.desktop = Desktop(backend="uia")

    def get_active_apps(self) -> List[str]:
        """获取活动应用列表"""
        return UIElement.get_current_applications()

    def get_top_app(self) -> Optional[str]:
        """获取最前端应用"""
        return UIElement.get_top_app()

    def preserve_nodes(self,
                       tree: UIElement,
                       exclude_roles: set = None) -> List[Dict]:
        """
        从 UI 树中提取并保留节点信息

        Args:
            tree: UI 树根节点
            exclude_roles: 要排除的角色类型集合

        Returns:
            提取的元素列表
        """
        if exclude_roles is None:
            # 默认排除无意义的容器类角色
            exclude_roles = {"Pane", "Group", "Unknown", "TitleBar"}

        preserved_nodes = []

        def traverse_and_preserve(element: UIElement):
            """递归遍历 UI 树"""
            role = element.role()

            # 如果不是排除的角色，则保存
            if role not in exclude_roles:
                position = element.position()
                size = element.size()

                # 验证有效性
                if position and size:
                    x, y = position
                    w, h = size

                    # 过滤掉无效区域
                    if x >= 0 and y >= 0 and w > 0 and h > 0:
                        preserved_nodes.append({
                            "position": (x, y),
                            "size": (w, h),
                            "title": element.title(),
                            "text": element.text(),
                            "role": role,
                        })

            # 递归处理子元素
            children = element.children()
            if children:
                for child_element in children:
                    traverse_and_preserve(child_element)

        # 开始遍历
        traverse_and_preserve(tree)

        return preserved_nodes

    def linearize_and_annotate_tree(self,
                                    obs: Dict,
                                    show_all_elements: bool = False) -> List[Dict]:
        """
        线性化并标注 UI 树（核心接口）

        Args:
            obs: 观测字典，包含'screenshot'等信息
            show_all_elements: 如果为空是否显示所有元素

        Returns:
            元素列表
        """
        # 获取当前活动窗口
        try:
            if self.top_app_only:
                # 只获取最前端窗口
                hwnd = win32gui.GetForegroundWindow()
                tree = self.desktop.window(handle=hwnd).wrapper_object()
            else:
                # 获取整个桌面
                tree = self.desktop

            # 包装为 UIElement
            ui_element = UIElement(tree)

            # 排除常见无用角色
            exclude_roles = {"Pane", "Group", "Unknown", "TitleBar"}
            # exclude_roles = set()  # 调试时可打开

            # 提取节点
            preserved_nodes = self.preserve_nodes(ui_element, exclude_roles).copy()

            # 如果没有提取到元素，尝试不排除任何角色
            if not preserved_nodes and show_all_elements:
                preserved_nodes = self.preserve_nodes(
                    ui_element, exclude_roles=set()
                ).copy()

            # 保存节点
            self.nodes = preserved_nodes

            print(f"[WindowsACI] ✓ 提取到 {len(preserved_nodes)} 个 UI 元素")

            return preserved_nodes

        except Exception as e:
            print(f"[WindowsACI] ✗ 提取 UI 树失败：{e}")
            self.nodes = []
            return []

    def find_element(self, element_id: int) -> Optional[Dict]:
        """
        根据 ID 查找元素

        Args:
            element_id: 元素索引 ID

        Returns:
            元素字典，找不到返回 None
        """
        if not self.nodes:
            print("[WindowsACI] ⚠️  没有元素可选")
            return None

        try:
            return self.nodes[element_id]
        except IndexError:
            print(f"[WindowsACI] ⚠️  元素 ID {element_id} 超出范围")
            self.index_out_of_range_flag = True
            return self.nodes[0] if self.nodes else None

    def click(self,
              element_id: int,
              num_clicks: int = 1,
              button_type: str = "left",
              hold_keys: List[str] = []) -> str:
        """
        生成点击命令

        Args:
            element_id: 元素 ID
            num_clicks: 点击次数
            button_type: 鼠标按钮类型
            hold_keys: 需要按住的修饰键

        Returns:
            PyAutoGUI 执行代码字符串
        """
        node = self.find_element(element_id)
        if not node:
            return ""

        coordinates: Tuple[int, int] = node["position"]
        sizes: Tuple[int, int] = node["size"]

        # 计算中心点
        x = int(coordinates[0] + sizes[0] // 2)
        y = int(coordinates[1] + sizes[1] // 2)

        # 生成命令
        command = "import pyautogui; "

        # 添加修饰键
        for k in hold_keys:
            command += f"pyautogui.keyDown('{k}'); "

        # 点击命令
        command += f"pyautogui.click({x}, {y}, clicks={num_clicks}, button='{button_type}'); "

        # 释放修饰键
        for k in hold_keys:
            command += f"pyautogui.keyUp('{k}'); "

        return command

    def type_text(self,
                  element_id: Optional[int] = None,
                  text: str = "",
                  overwrite: bool = False,
                  enter: bool = False) -> str:
        """
        生成输入命令

        Args:
            element_id: 元素 ID（None 表示在当前位置输入）
            text: 要输入的文本
            overwrite: 是否覆盖现有文本
            enter: 输入后是否按回车

        Returns:
            PyAutoGUI 执行代码字符串
        """
        if element_id is not None:
            node = self.find_element(element_id)
        else:
            node = None

        if node is not None:
            # 先点击元素
            coordinates = node["position"]
            sizes = node["size"]

            x = int(coordinates[0] + sizes[0] // 2)
            y = int(coordinates[1] + sizes[1] // 2)

            command = "import pyautogui; "
            command += f"pyautogui.click({x}, {y}); "

            # 如果需要覆盖
            if overwrite:
                command += "pyautogui.hotkey('ctrl', 'a', interval=0.5); pyautogui.press('backspace'); "

            # 输入文本
            command += f"pyautogui.write({repr(text)}); "

            # 回车
            if enter:
                command += "pyautogui.press('enter'); "
        else:
            # 直接在当前位置输入
            command = "import pyautogui; "

            if overwrite:
                command += "pyautogui.hotkey('ctrl', 'a', interval=0.5); pyautogui.press('backspace'); "

            command += f"pyautogui.write({repr(text)}); "

            if enter:
                command += "pyautogui.press('enter'); "

        return command

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "total_elements": len(self.nodes),
            "top_app": self.get_top_app(),
        }
