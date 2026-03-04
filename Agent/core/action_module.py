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
        pyautogui.FAILSAFE = True  # 鼠标移到角落可中断
        pyautogui.PAUSE = 0.5  # 操作间隔

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
            print("[Action] 安全模式：3 秒后执行...")
            time.sleep(3)

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
        x, y = params.get('x'), params.get('y')
        if x is None or y is None:
            return {'success': False, 'message': '缺少坐标参数'}

        pyautogui.moveTo(x, y, duration=0.5)
        pyautogui.click()
        return {'success': True, 'message': f'已点击 ({x}, {y})'}

    def _type(self, params: Dict) -> Dict:
        text = params.get('text')
        needs_enter = params.get('needs_enter', False)

        if not text:
            return {'success': False, 'message': '缺少文本参数'}

        pyautogui.write(text, interval=0.05)
        if needs_enter:
            time.sleep(0.2)
            pyautogui.press('enter')

        return {'success': True, 'message': f'已输入：{text[:50]}...'}

    def _scroll(self, params: Dict) -> Dict:
        direction = params.get('direction', 'down').lower()
        amount = params.get('amount', 'medium').lower()

        amounts = {'small': 1, 'medium': 3, 'large': 5}
        clicks = amounts.get(amount, 3)

        pyautogui.scroll(-clicks if direction == 'down' else clicks)
        return {'success': True, 'message': f'已{direction}滚动'}

    def _key_press(self, params: Dict) -> Dict:
        key = params.get('key')
        if not key:
            return {'success': False, 'message': '缺少按键参数'}

        pyautogui.press(key)
        return {'success': True, 'message': f'已按 {key}'}
