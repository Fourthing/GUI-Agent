import json
import os
import pyautogui
import time

from dotenv import load_dotenv
from openai import OpenAI
from utils.prompt_loader import prompt_loader

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

        # ========== 获取屏幕分辨率==========
        screen_width, screen_height = pyautogui.size()

        # 从配置文件获取 System Prompt
        system_prompt = prompt_loader.get_decision_system_prompt(screen_width, screen_height)

        messages = [
            {
                "role": "system",
                "content": system_prompt
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

        # print(f"{log_prefix} 📋 User Instruction 长度：{len(user_instruction)} 字符")
        # print(f"{log_prefix} 📄 User Instruction:\n{'-' * 60}")
        # print(user_instruction)
        # print(f"{'-' * 60}\n")

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

            total_elapsed = time.time() - start_time
            print(f"{log_prefix} ⏱️  [总计] decide() 总耗时：{total_elapsed:.2f}s\n")

            return {
                'success': True,
                'step_no': step_no,
                'task_id': task_id,
                'thought': action_json.get('thought', ''),
                'action': action_json.get('action') or action_json.get('Action'),
                'parameters': action_json.get('parameters') or action_json.get('Parameters'),
                'full_response': action_json
            }


        except Exception as e:
            import traceback
            total_elapsed = time.time() - start_time
            error_trace = traceback.format_exc()
            print(f"{log_prefix} ❌ 调用失败（耗时 {total_elapsed:.2f}s）：{e}")
            print(f"{log_prefix} 📋 trace：\n{error_trace}")

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

