import pyautogui
import time
from typing import Dict, Any, Optional, Tuple
from PIL import Image


class ActionModule:
    """动作执行模块：封装 PyAutoGUI 操作"""

    def __init__(self, safety_mode: bool = True):
        """
        Args:
            safety_mode: 安全模式（操作前暂停）
        """
        self.safety_mode = safety_mode

        # 配置 PyAutoGUI
        pyautogui.FAILSAFE = True  # 鼠标移到角落可中断
        pyautogui.PAUSE = 0.3  # 操作间隔（缩短到 0.3s）

        print("[ActionModule] ✓ 初始化完成")
        print(f"[ActionModule] 安全模式：{'开启' if safety_mode else '关闭'}")

    def execute(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行动作

        Args:
            action_data: {
                'action': str,
                'parameters': dict,
                'description': str (可选)
            }

        Returns:
            {
                'success': bool,
                'message': str,
                'action': str,
                'before_screenshot': str (可选),
                'after_screenshot': str (可选)
            }
        """
        action = action_data.get('action', '').upper()
        params = action_data.get('parameters', {})
        description = action_data.get('description', '')

        # 清理字段名大小写问题
        if not params:
            params = action_data.get('Parameters', {})

        print(f"\n[Action] 📍 准备执行：{action}")
        print(f"[Action] 参数：{params}")
        if description:
            print(f"[Action] 描述：{description}")

        if self.safety_mode:
            print(f"[Action] ⚠️  安全模式：1 秒后执行...")
            time.sleep(1)

        try:
            # 执行前截图（用于后续验证）
            before_screenshot = self._capture_current_state()

            # 分发到对应的执行方法
            if action == 'CLICK':
                result = self._click(params)
            elif action == 'TYPE':
                result = self._type(params)
            elif action == 'SCROLL':
                result = self._scroll(params)
            elif action == 'KEY_PRESS':
                result = self._key_press(params)
            elif action == 'DOUBLE_CLICK':
                result = self._double_click(params)
            elif action == 'RIGHT_CLICK':
                result = self._right_click(params)
            elif action == 'DRAG_TO':
                result = self._drag_to(params)
            elif action == 'HOTKEY':
                result = self._hotkey(params)
            elif action == 'FINISH':
                result = {'success': True, 'message': params.get('message', '任务完成')}
            elif action in ['FAILE', 'FAIL']:
                result = {'success': False, 'message': params.get('reason', '未知失败')}
            else:
                result = {'success': False, 'message': f'未知动作：{action}'}

            # 执行后截图（用于后续验证）
            after_screenshot = self._capture_current_state()

            # 合并结果
            result['action'] = action
            if before_screenshot:
                result['before_screenshot'] = before_screenshot
            if after_screenshot:
                result['after_screenshot'] = after_screenshot

            return result

        except Exception as e:
            return {
                'success': False,
                'message': f'执行失败：{str(e)}',
                'action': action
            }

    def _capture_current_state(self) -> Optional[str]:
        """截取当前屏幕状态（base64）"""
        try:
            screenshot = pyautogui.screenshot()

            # 转换为 base64
            from io import BytesIO
            import base64

            buffered = BytesIO()
            screenshot.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

            return img_base64
        except:
            return None

    def _normalize_coordinates(self, x, y) -> Tuple[int, int]:
        """
        标准化坐标处理

        支持：
        - 单个数字：x=100
        - 数组格式：x=[100, 200] → 取第一个
        - 字符串格式：x="100" → 转整数
        """
        # 处理 x
        if isinstance(x, list):
            x = x[0] if len(x) > 0 else 0
        elif isinstance(x, str):
            try:
                x = int(x)
            except:
                x = 0

        # 处理 y
        if isinstance(y, list):
            y = y[0] if len(y) > 0 else 0
        elif isinstance(y, str):
            try:
                y = int(y)
            except:
                y = 0

        return int(x), int(y)

    def _click(self, params: Dict) -> Dict:
        """
        点击操作

        Parameters:
            x: 横坐标（支持数字、数组、字符串）
            y: 纵坐标
            description: 描述（可选）
            clicks: 点击次数（默认 1）
            interval: 点击间隔（默认 0.1s）
        """
        x_raw = params.get('x')
        y_raw = params.get('y')
        description = params.get('description', '')
        clicks = params.get('clicks', 1)
        interval = params.get('interval', 0.1)

        if x_raw is None or y_raw is None:
            return {'success': False, 'message': '缺少坐标参数 (x, y)'}

        # 标准化坐标
        x, y = self._normalize_coordinates(x_raw, y_raw)

        try:
            # 移动鼠标到指定位置
            pyautogui.moveTo(x, y, duration=0.5)
            time.sleep(0.1)

            # 点击
            pyautogui.click(x=x, y=y, clicks=clicks, interval=interval)

            desc_text = f" - {description}" if description else ""
            message = f"✓ 已点击位置 ({x}, {y}){desc_text}"
            print(f"[Action] {message}")

            return {
                'success': True,
                'message': message,
                'executed_action': 'CLICK',
                'coordinates': (x, y)
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'点击失败：{str(e)}'
            }

    def _double_click(self, params: Dict) -> Dict:
        """双击操作"""
        params['clicks'] = 2
        params['interval'] = 0.2
        return self._click(params)

    def _right_click(self, params: Dict) -> Dict:
        """右键点击"""
        x_raw = params.get('x')
        y_raw = params.get('y')

        if x_raw is None or y_raw is None:
            return {'success': False, 'message': '缺少坐标参数'}

        x, y = self._normalize_coordinates(x_raw, y_raw)

        try:
            pyautogui.moveTo(x, y, duration=0.5)
            pyautogui.rightClick()

            message = f"✓ 已右键点击 ({x}, {y})"
            print(f"[Action] {message}")

            return {
                'success': True,
                'message': message
            }
        except Exception as e:
            return {'success': False, 'message': f'右键点击失败：{str(e)}'}

    def _type(self, params: Dict) -> Dict:
        """
        文本输入操作

        Parameters:
            text: 要输入的文本
            needs_enter: 是否需要按回车
            interval: 字符间隔（默认 0.05s）
        """
        text = params.get('text')
        needs_enter = params.get('needs_enter', False)
        interval = params.get('interval', 0.05)

        if not text:
            return {'success': False, 'message': '缺少文本参数 (text)'}

        try:
            # 输入文本
            pyautogui.write(text, interval=interval)

            # 如需按回车
            if needs_enter:
                time.sleep(0.2)
                pyautogui.press('enter')

            text_preview = text[:50] + ('...' if len(text) > 50 else '')
            message = f"✓ 已输入文本：{text_preview}"
            print(f"[Action] {message}")

            return {
                'success': True,
                'message': message,
                'executed_action': 'TYPE',
                'input_length': len(text)
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'输入失败：{str(e)}'
            }

    def _scroll(self, params: Dict) -> Dict:
        """
        滚动操作

        Parameters:
            direction: 'up' 或 'down'
            amount: 滚动像素量（正数向上，负数向下）
                     或使用 'small'(100), 'medium'(300), 'large'(600)
            x: 滚动中心 x 坐标（可选）
            y: 滚动中心 y 坐标（可选）
        """
        direction = params.get('direction', 'down').lower()
        amount_param = params.get('amount', 300)
        x = params.get('x')
        y = params.get('y')

        # 如果是字符串，映射为像素值
        if isinstance(amount_param, str):
            scroll_amounts = {
                'small': 100,
                'medium': 300,
                'large': 600
            }
            amount = scroll_amounts.get(amount_param, 300)
        else:
            amount = int(amount_param)

        # 根据方向调整符号
        if direction == 'up':
            amount = abs(amount)
        else:
            amount = -abs(amount)

        try:
            # 如果指定了坐标，先移动鼠标
            if x is not None and y is not None:
                x_norm, y_norm = self._normalize_coordinates(x, y)
                pyautogui.moveTo(x_norm, y_norm, duration=0.3)

            # 执行滚动
            pyautogui.scroll(amount)

            direction_text = "向上" if direction == 'up' else "向下"
            message = f"✓ 已{direction_text}滚动 {abs(amount)} 像素"
            print(f"[Action] {message}")

            return {
                'success': True,
                'message': message,
                'executed_action': 'SCROLL',
                'scroll_amount': amount
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'滚动失败：{str(e)}'
            }

    def _key_press(self, params: Dict) -> Dict:
        """
        按键操作

        Parameters:
            key: 按键名称（如 'enter', 'esc', 'tab' 等）
            presses: 按压次数（默认 1）
            interval: 按压间隔（默认 0.1s）
        """
        key = params.get('key')
        presses = params.get('presses', 1)
        interval = params.get('interval', 0.1)

        if not key:
            return {'success': False, 'message': '缺少按键参数 (key)'}

        try:
            pyautogui.press(key, presses=presses, interval=interval)

            message = f"✓ 已按下按键：{key}"
            print(f"[Action] {message}")

            return {
                'success': True,
                'message': message,
                'executed_action': 'KEY_PRESS'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'按键失败：{str(e)}'
            }

    def _hotkey(self, params: Dict) -> Dict:
        """
        组合键操作

        Parameters:
            keys: 按键列表，如 ['ctrl', 'c']
        """
        keys = params.get('keys', [])

        if not keys:
            return {'success': False, 'message': '缺少按键参数 (keys)'}

        try:
            pyautogui.hotkey(*keys)

            keys_str = '+'.join(keys)
            message = f"✓ 已按下组合键：{keys_str}"
            print(f"[Action] {message}")

            return {
                'success': True,
                'message': message,
                'executed_action': 'HOTKEY'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'组合键失败：{str(e)}'
            }

    def _drag_to(self, params: Dict) -> Dict:
        """
        拖拽操作

        Parameters:
            startX: 起始 X 坐标
            startY: 起始 Y 坐标
            endX: 结束 X 坐标
            endY: 结束 Y 坐标
            duration: 拖拽持续时间（默认 1.0s）
        """
        start_x = params.get('startX')
        start_y = params.get('startY')
        end_x = params.get('endX')
        end_y = params.get('endY')
        duration = params.get('duration', 1.0)

        if None in [start_x, start_y, end_x, end_y]:
            return {'success': False, 'message': '缺少坐标参数'}

        try:
            # 标准化坐标
            start_x, start_y = self._normalize_coordinates(start_x, start_y)
            end_x, end_y = self._normalize_coordinates(end_x, end_y)

            # 移动到起始点
            pyautogui.moveTo(start_x, start_y, duration=0.3)

            # 按下鼠标左键
            pyautogui.mouseDown()

            # 移动到终点
            pyautogui.moveTo(end_x, end_y, duration=duration)

            # 释放鼠标
            pyautogui.mouseUp()

            message = f"✓ 已从 ({start_x}, {start_y}) 拖拽到 ({end_x}, {end_y})"
            print(f"[Action] {message}")

            return {
                'success': True,
                'message': message,
                'executed_action': 'DRAG_TO'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'拖拽失败：{str(e)}'
            }

    def get_screen_info(self) -> Dict[str, Any]:
        """获取当前屏幕信息"""
        screen_width, screen_height = pyautogui.size()
        current_x, current_y = pyautogui.position()

        return {
            'screen_size': (screen_width, screen_height),
            'current_position': (current_x, current_y),
            'timestamp': time.time()
        }

    def wait_for_loading(self, seconds: float = 2.0):
        """等待加载（简单延迟）"""
        print(f"[Action] ⏳ 等待 {seconds} 秒...")
        time.sleep(seconds)


if __name__ == "__main__":
    # 测试
    executor = ActionModule(safety_mode=True)

    print("\n=== 屏幕信息 ===")
    info = executor.get_screen_info()
    print(f"分辨率：{info['screen_size']}")
    print(f"鼠标位置：{info['current_position']}")

    # 测试各种操作
    test_actions = [
        {"action": "CLICK", "parameters": {"x": 100, "y": 100, "description": "测试点击"}},
        {"action": "DOUBLE_CLICK", "parameters": {"x": [150], "y": "150"}},  # 测试数组和字符串
        {"action": "TYPE", "parameters": {"text": "Hello World", "needs_enter": False}},
        {"action": "SCROLL", "parameters": {"direction": "down", "amount": "medium"}},
        {"action": "KEY_PRESS", "parameters": {"key": "enter"}},
        {"action": "HOTKEY", "parameters": {"keys": ["ctrl", "c"]}},
        {"action": "FINISH", "parameters": {"message": "测试完成"}},
    ]

    for action in test_actions:
        input("\n按回车执行下一个动作...")
        result = executor.execute(action)
        print(f"结果：{result['message']}")
        if result.get('success'):
            print(f"✓ 执行成功")
        else:
            print(f"✗ 执行失败")
