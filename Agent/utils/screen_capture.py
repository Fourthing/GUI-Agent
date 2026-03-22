"""
屏幕截图模块
使用 PyAutoGUI 实现屏幕截图功能
"""
import pyautogui
import base64
import os
import time
from PIL import Image
import io
import base64


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

        # 获取屏幕尺寸
        self.screen_width, self.screen_height = pyautogui.size()

        # VLM 支持的最大尺寸
        self.MAX_WIDTH = 2048
        self.MAX_HEIGHT = 2048

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
            """捕获屏幕截图并保存到文件"""
            screenshot = pyautogui.screenshot()
            file_path = f"screenshots/screenshot_{int(time.time())}.png"

            print(f"[ScreenCapturer] ✓ 截图已保存：{save_path}")
            screenshot.save(file_path)
            return file_path

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

            # ========== 处理大尺寸图片 ==========
            if (screenshot.width > self.MAX_WIDTH or
                    screenshot.height > self.MAX_HEIGHT):
                print(f"⚠️  原始截图尺寸: {screenshot.width}x{screenshot.height}")
                print(f"📏 正在调整到最大支持尺寸...")

                # 计算缩放比例（保持宽高比）
                scale_w = self.MAX_WIDTH / screenshot.width
                scale_h = self.MAX_HEIGHT / screenshot.height
                scale = min(scale_w, scale_h)

                new_width = int(screenshot.width * scale)
                new_height = int(screenshot.height * scale)

                # 缩放图片（高质量）
                resized_screenshot = screenshot.resize(
                    (new_width, new_height),
                    Image.Resampling.LANCZOS
                )

                print(f"✅ 已调整尺寸: {new_width}x{new_height}")

                # 使用缩放后的图片
                screenshot = resized_screenshot

            # 将图像转换为 base64
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG")
            img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return img_str

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
