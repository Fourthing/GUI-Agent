from openai import OpenAI
import os
import json
import time
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class DecisionOrchestrator:
    """VLM 决策编排器：调用 GUI-Owl 模型分析屏幕截图"""

    def __init__(self):
        modelscope_token = os.getenv('MODELSCOPE_TOKEN')
        if not modelscope_token:
            raise ValueError("未找到 MODELSCOPE_TOKEN 环境变量")

        self.client = OpenAI(
            base_url='https://api-inference.modelscope.cn/v1',
            api_key=modelscope_token,
        )

        self.operation_history = []

    def decide(self, image_url: str, user_instruction: str, step_no: int = 1, task_id: str = None) -> dict:
        """
        基于屏幕图像和指令生成操作决策

        Args:
            image_url: 屏幕截图 URL
            user_instruction: 用户指令
            step_no: 步骤编号（可选，默认 1）
            task_id: 任务 ID（可选）

        Returns:
            dict: {
                'success': bool,
                'step_no': int,
                'task_id': str,
                'thought': str,
                'action': str,
                'parameters': dict,
                'full_response': dict
            }
        """
        start_time = time.time()
        log_prefix = f"[Task:{task_id}] Step:{step_no}" if task_id else f"Step:{step_no}"

        # ========== 获取屏幕分辨率（新增！）==========
        import pyautogui
        screen_width, screen_height = pyautogui.size()

        messages = [
            {
                "role": "system",
                "content": '''
## 1. 核心角色 (Core Role)
你是一个顶级的 AI 视觉操作代理。你的任务是结合UI元素列表分析电脑屏幕截图，理解用户的指令（user_instruction），然后将任务分解为单一、精确的 GUI 原子操作。（优先使用快捷键和UI元素进行操作）

## 2. [CRITICAL] JSON Schema & 绝对规则
你的输出**必须**是一个严格符合以下规则的 JSON 对象。
- **[R1] 严格的 JSON**: 回复必须是且只能是一个 JSON 对象，禁止添加额外文本。
- **[R2] thought 结构**: "在这里描述思考过程。例如：用户想打开浏览器，我看到了 Chrome 图标，所以下一步是点击它。"
- **[R3] Action 值**: 必须为大写字符串（如 "CLICK", "TYPE"）。
- **[R4] parameters 结构**: 优先使用element_Id（UI元素列表内的ID），否则必须与工具集中的模板完全一致。

## 3. 工具集 (Available Actions)
### CLICK
- **功能**: 单击屏幕。
- **Parameters 模板**: {"x": <integer>, "y": <integer>, "description": "<string, optional>"}

### TYPE
- **功能**: 输入文本。
- **Parameters 模板**: {"text": "<string>", "needs_enter": <boolean>}

### SCROLL
- **功能**: 滚动窗口。
- **Parameters 模板**: {"direction": "<'up' or 'down'>", "amount": "<'small', 'medium', or 'large'>"}

### KEY_PRESS
- **功能**: 按下功能键。
- **Parameters 模板**: {"key": "<string: e.g., 'enter', 'esc'>"}

### FINISH
- **功能**: 任务成功完成。
- **Parameters 模板**: {"message": "<string: 总结完成情况>"}

### FAILE
- **功能**: 任务无法完成。
- **Parameters 模板**: {"reason": "<string: 清晰解释失败原因>"}

## 4. 当前屏幕信息和坐标参数规范
- **屏幕分辨率**: {screen_width} x {screen_height} 像素
- **有效坐标范围**: 
  - X 轴：0 到 {screen_width - 1}（从左到右）
  - Y 轴：0 到 {screen_height - 1}（从上到下）
- **重要区域参考**:
  - 左上角坐标：(0, 0)
  - 右上角坐标：({screen_width - 1}, 0)
  - 左下角坐标：(0, {screen_height - 1})
  - 右下角坐标：({screen_width - 1}, {screen_height - 1})
  - 中间区域坐标：（{screen_width/2},{screen_height/2}）
- **坐标输出要求**:
  - "x": 必须是一个整数，表示横坐标
  - "y": 必须是一个整数，表示纵坐标

## 5. 思维与决策框架
目标分析 → 屏幕观察 → 行动决策 → 构建输出 → 最终验证
'''
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    },
                    {
                        "type": "text",
                        "text": user_instruction
                    }
                ]
            }
        ]

        try:
            print(f"{log_prefix} ⏱️  [VLM] 开始调用 ModelScope API...")
            api_start_time = time.time()

            completion = self.client.chat.completions.create(
                model='iic/GUI-Owl-7B',
                messages=messages
            )

            api_elapsed = time.time() - api_start_time
            print(f"{log_prefix} ⏱️  [VLM] API 响应耗时：{api_elapsed:.2f}s")

            response_content = completion.choices[0].message.content.strip()
            print(f"{log_prefix} VLM 原始响应：{response_content}")

            # 解析 JSON 响应
            parse_start_time = time.time()
            if response_content.startswith('```json'):
                response_content = response_content[7:]
            if response_content.endswith('```'):
                response_content = response_content[:-3]
            response_content = response_content.strip()
            action_json = json.loads(response_content)
            parse_elapsed = time.time() - parse_start_time

            print(f"{log_prefix} 解析成功的动作：{action_json}")
            print(f"{log_prefix} ⏱️  [JSON] 解析耗时：{parse_elapsed:.3f}s")
            print(f"{log_prefix} 解析成功的动作：{action_json}")

            total_elapsed = time.time() - start_time
            print(f"{log_prefix} ⏱️  [总计] decide() 总耗时：{total_elapsed:.2f}s\n")

            return {
                'success': True,
                'step_no': step_no,
                'task_id': task_id,
                'thought': action_json.get('thought', ''),
                'action': action_json.get('Action'),
                'parameters': action_json.get('parameters'),
                'full_response': action_json
            }

        except Exception as e:
            total_elapsed = time.time() - start_time
            print(f"{log_prefix} ❌ 调用失败（耗时 {total_elapsed:.2f}s）：{e}")
            return {
                'success': False,
                'step_no': step_no,
                'task_id': task_id,
                'error': str(e),
                'thought': '',
                'action': None,
                'parameters': None,
                'full_response': None
            }
