"""
屏幕截图模块
使用 PyAutoGUI 实现屏幕截图功能
"""
import pyautogui
import base64
import os
import time
from PIL import Image
from io import BytesIO


class ScreenCapturer:
    """屏幕截图器"""

    def __init__(self, temp_dir: str = None):
        """
        Args:
            temp_dir: 临时截图保存目录，默认在当前目录的 temp_screenshots 文件夹
        """
        if temp_dir is None:
            temp_dir = os.path.join(os.getcwd(), 'temp_screenshots')

        self.temp_dir = temp_dir

        # 确保目录存在
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        # 配置 PyAutoGUI
        pyautogui.FAILSAFE = True  # 启用安全模式
        pyautogui.PAUSE = 0.5  # 操作间隔

    def capture(self, save_path: str = None) -> str:
        """
        截取整个屏幕

        Args:
            save_path: 保存路径（可选），如果为 None 则自动生成

        Returns:
            str: 保存的文件路径
        """
        if save_path is None:
            timestamp = int(time.time())
            save_path = os.path.join(self.temp_dir, f'screen_{timestamp}.png')

        try:
            # 使用 PyAutoGUI 截图
            screenshot = pyautogui.screenshot()
            screenshot.save(save_path)

            print(f"[ScreenCapturer] ✓ 截图已保存：{save_path}")
            return save_path

        except Exception as e:
            raise Exception(f"截图失败：{str(e)}")

    def capture_region(self, region: tuple, save_path: str = None) -> str:
        """
        截取屏幕指定区域

        Args:
            region: (left, top, width, height)
            save_path: 保存路径（可选）

        Returns:
            str: 保存的文件路径
        """
        if save_path is None:
            timestamp = int(time.time())
            save_path = os.path.join(self.temp_dir, f'region_{timestamp}.png')

        try:
            screenshot = pyautogui.screenshot(region=region)
            screenshot.save(save_path)

            print(f"[ScreenCapturer] ✓ 区域截图已保存：{save_path}")
            return save_path

        except Exception as e:
            raise Exception(f"区域截图失败：{str(e)}")

    def capture_to_base64(self) -> str:
        """
        截取屏幕并返回 base64 编码

        Returns:
            str: base64 编码的图片数据
        """
        try:
            screenshot = pyautogui.screenshot()

            # 转换为 base64
            buffered = BytesIO()
            screenshot.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

            print(f"[ScreenCapturer] ✓ 截图已转换为 base64")
            return img_base64

        except Exception as e:
            raise Exception(f"截图转 base64 失败：{str(e)}")

    def get_screen_size(self) -> tuple:
        """
        获取屏幕分辨率

        Returns:
            tuple: (width, height)
        """
        return pyautogui.size()

    def get_mouse_position(self) -> tuple:
        """
        获取鼠标当前位置

        Returns:
            tuple: (x, y)
        """
        return pyautogui.position()


# 便捷函数
def capture_screen(save_path: str = None) -> str:
    """快捷截图函数"""
    capturer = ScreenCapturer()
    return capturer.capture(save_path)


def capture_screen_to_base64() -> str:
    """快捷截图并转 base64"""
    capturer = ScreenCapturer()
    return capturer.capture_to_base64()


if __name__ == "__main__":
    # 测试
    capturer = ScreenCapturer()

    print("屏幕分辨率:", capturer.get_screen_size())
    print("鼠标位置:", capturer.get_mouse_position())

    # 截图测试
    path = capturer.capture()
    print(f"截图保存路径：{path}")

    # base64 测试
    base64_data = capturer.capture_to_base64()
    print(f"Base64 长度：{len(base64_data)}")
