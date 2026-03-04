import pyautogui
import time
from typing import Dict, Any


class ActionModule:
    """动作执行模块：封装 PyAutoGUI 操作"""

    def __init__(self, safety_mode: bool = True):
        """
        Args:
            safety_mode: 安全模式（操作前暂停）
        """
        self.safety_mode = safety_mode

        # 配置PyAutoGUI
        pyautogui.FAILSAFE = True  # 鼠标移到角落可中断
        pyautogui.PAUSE = 0.5  # 操作间隔

        print("[ActionExecutor] ✓ 初始化完成")
        print(f"[ActionExecutor] 安全模式：{'开启' if safety_mode else '关闭'}")

    def execute(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行动作

        Args:
            action_data: {'action': str, 'parameters': dict}

        Returns:
            {'success': bool, 'message': str}
        """
        action = action_data.get('action', '').upper()
        params = action_data.get('parameters', {})

        print(f"\n[Action] 准备执行：{action}")
        print(f"[Action] 参数：{params}")

        if self.safety_mode:
            print("[Action] 安全模式：1 秒后执行...")
            time.sleep(1)

        try:
            if action == 'CLICK':
                return self._click(params)
            elif action == 'TYPE':
                return self._type(params)
            elif action == 'SCROLL':
                return self._scroll(params)
            elif action == 'KEY_PRESS':
                return self._key_press(params)
            elif action == 'FINISH':
                return {'success': True, 'message': params.get('message', '任务完成')}
            elif action in ['FAILE', 'FAIL']:
                return {'success': False, 'message': params.get('reason', '未知失败')}
            else:
                return {'success': False, 'message': f'未知动作：{action}'}

        except Exception as e:
            return {'success': False, 'message': f'执行失败：{str(e)}'}

    def _click(self, params: Dict) -> Dict:
        """
        点击操作

        Parameters:
            x: 横坐标
            y: 纵坐标
            description: 描述（可选）
        """
        x, y = params.get('x'), params.get('y')
        description = params.get('description', '')
        if x is None or y is None:
            return {'success': False, 'message': '缺少坐标参数'}

        pyautogui.moveTo(x, y, duration=0.5)
        time.sleep(0.2)

        pyautogui.click()
        desc_text = f" - {description}" if description else ""
        message = f"✓ 已点击位置 ({x}, {y}){desc_text}"
        print(f"[ActionExecutor] {message}")

        return {
            'success': True,
            'message': message
        }

    def _type(self, params: Dict) -> Dict:
        """
        文本输入操作

        Parameters:
            text: 要输入的文本
            needs_enter: 是否需要按回车
        """
        text = params.get('text')
        needs_enter = params.get('needs_enter', False)

        if not text:
            return {'success': False, 'message': '缺少文本参数'}

        try:
            # 输入文本
            pyautogui.write(text, interval=0.05)

            # 如需按回车
            if needs_enter:
                time.sleep(0.2)
                pyautogui.press('enter')

            text_preview = text[:50] + ('...' if len(text) > 50 else '')
            message = f"✓ 已输入文本：{text_preview}"
            print(f"[ActionExecutor] {message}")

            return {
                'success': True,
                'message': message
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
            amount: 'small', 'medium', 或 'large'
        """
        direction = params.get('direction', 'down').lower()
        amount = params.get('amount', 'medium').lower()

        # 映射滚动量
        scroll_amounts = {
            'small': 100,
            'medium': 300,
            'large': 600
        }
        clicks = scroll_amounts.get(amount, 3)

        try:
            # 向上滚动为正，向下为负
            if direction == 'up':
                pyautogui.scroll(clicks)
                message = f"✓ 已向上滚动 {amount} 幅度"
            else:
                pyautogui.scroll(-clicks)
                message = f"✓ 已向下滚动 {amount} 幅度"

            print(f"[ActionExecutor] {message}")
            return {
                'success': True,
                'message': message
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'滚动失败：{str(e)}'
            }

    def _key_press(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        按键操作

        Parameters:
            key: 按键名称（如 'enter', 'esc', 'tab' 等）
        """
        key = params.get('key')

        if not key:
            return {
                'success': False,
                'message': '缺少按键参数 (key)'
            }

        try:
            pyautogui.press(key)
            message = f"✓ 已按下按键：{key}"
            print(f"[ActionExecutor] {message}")

            return {
                'success': True,
                'message': message
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'按键失败：{str(e)}'
            }

    def _finish(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        任务完成

        Parameters:
            message: 完成消息
        """
        message = params.get('message', '任务已完成')
        print(f"\n[ActionExecutor] 🎉 {message}")

        return {
            'success': True,
            'message': message
        }

    def _fail(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        任务失败

        Parameters:
            reason: 失败原因
        """
        reason = params.get('reason', '未知原因')
        print(f"\n[ActionExecutor] ❌ 无法完成任务：{reason}")

        return {
            'success': False,
            'message': reason
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


if __name__ == "__main__":
    # 测试
    executor = ActionModule(safety_mode=True)

    print("\n=== 屏幕信息 ===")
    print(executor.get_screen_info())

    # 测试各种操作
    test_actions = [
        {"action": "CLICK", "parameters": {"x": 100, "y": 100, "description": "测试点击"}},
        {"action": "TYPE", "parameters": {"text": "Hello World", "needs_enter": False}},
        {"action": "SCROLL", "parameters": {"direction": "down", "amount": "large"}},
        {"action": "SCROLL", "parameters": {"direction": "up", "amount": "large"}},
        {"action": "KEY_PRESS", "parameters": {"key": "win"}},
        {"action": "FINISH", "parameters": {"message": "测试完成"}},
    ]

    for action in test_actions:
        input("\n按回车执行下一个动作...")
        result = executor.execute(action)
        print(f"结果：{result['message']}")
