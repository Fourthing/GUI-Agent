"""
任务规划器（基于 DeepSeek-V3）
使用 DeepSeek-V3 模型将复杂指令分解为多个可执行的步骤
支持显示思考过程
"""
import json
import os
import time

from openai import OpenAI
from dotenv import load_dotenv
from utils.prompt_loader import prompt_loader

load_dotenv()


class TaskPlanner:
    """任务规划器：将复杂指令分解为步骤序列"""

    # 配置常量
    API_RESPONSE_DELAY = 0.5  # API 响应后的延迟时间（秒）
    INSTRUCTION_PREVIEW_LENGTH = 60  # 步骤描述预览长度
    MAX_STEPS_DISPLAY = 15  # 最大步骤数参考值

    def __init__(self, show_thinking: bool = True):
        """
        Args:
            show_thinking: 是否显示思考过程
        """
        self.show_thinking = show_thinking

        # 初始化客户端
        llm_token = os.getenv('MODELSCOPE_TOKEN')

        if not llm_token:
            raise ValueError("未找到 MODELSCOPE_TOKEN 环境变量")

        self.client = OpenAI(
            base_url='https://api-inference.modelscope.cn/v1',
            api_key=llm_token,
        )

    def plan(self, user_instruction: str) -> list:
        """
        将复杂指令分解为步骤序列

        Args:
            user_instruction: 用户的复杂指令

        Returns:
            steps: 步骤列表
        """
        print(f"\n{'=' * 60}")
        print(f"[TaskPlanner] 📋 开始规划任务")
        print(f"指令：{user_instruction}")
        print(f"{'=' * 60}\n")

        try:
            # 设置思考控制参数
            extra_body = {
                # 启用思考模式
                "enable_thinking": True
            }

            # 从配置文件获取 System Prompt
            system_prompt = prompt_loader.get_planning_system_prompt()

            # 调用 DeepSeek-V3 进行流式响应
            response = self.client.chat.completions.create(
                model='deepseek-ai/DeepSeek-V3.2',  # 使用 DeepSeek-V3
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"请将以下指令分解为可执行的步骤：\n\n{user_instruction}"}
                ],
                stream=True,  # 启用流式输出
                extra_body=extra_body
            )

            # 处理流式响应
            thinking_content = ""
            answer_content = ""
            done_thinking = False

            # 处理流式响应
            thinking_content, answer_content = self._process_stream_response(response)

            print(f"[TaskPlanner] ✓ 响应接收完成")

            # 解析 JSON 响应
            time.sleep(self.API_RESPONSE_DELAY)
            steps = self._parse_response(answer_content)

            if steps and len(steps) > 0:
                print(f"\n[TaskPlanner] ✅ 成功分解为 {len(steps)} 个步骤")
                for step in steps:
                    step_no = step.get('step', '?')
                    instruction = step.get('instruction', '')
                    action = step.get('expected_action', 'N/A')
                    print(f"  步骤 {step_no}: {instruction[:self.INSTRUCTION_PREVIEW_LENGTH]}... ({action})")
            else:
                print(f"[TaskPlanner] ⚠️  分解结果为空")

            return steps

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"\n[TaskPlanner] ❌ 规划失败：{str(e)}")
            print(f"[TaskPlanner] 📋 错误堆栈：\n{error_trace}")
            return []

    def _parse_response(self, response_text: str) -> list:
        """解析 LLM 响应，提取步骤列表"""
        try:
            # 清理可能的 markdown 标记
            response_text = response_text.strip()

            if response_text.startswith('json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]

            response_text = response_text.strip()

            # 尝试直接解析
            steps = json.loads(response_text)

            # 验证格式
            if isinstance(steps, list):
                return steps
            elif isinstance(steps, dict) and 'steps' in steps:
                return steps['steps']
            else:
                print(f"[TaskPlanner] 响应格式不正确")
                return []

        except json.JSONDecodeError as e:
            print(f"[TaskPlanner] JSON 解析失败：{e}")
            print(f"原始文本：{response_text}")
            return []
        except Exception as e:
            print(f"[TaskPlanner] 解析异常：{e}")
            return []

    def plan_simple(self, user_instruction: str) -> list:
        """
        简化版本：不显示思考过程，直接返回结果

        Args:
            user_instruction: 用户指令

        Returns:
            steps: 步骤列表
        """
        # 临时关闭思考显示
        old_setting = self.show_thinking
        self.show_thinking = False

        result = self.plan(user_instruction)

        # 恢复设置
        self.show_thinking = old_setting

        return result

    def _process_stream_response(self, response) -> tuple:
        """
        处理流式响应

        Args:
            response: OpenAI 流式响应对象

        Returns:
            (thinking_content, answer_content): 思考内容和答案内容
        """
        thinking_content = ""
        answer_content = ""
        done_thinking = False

        print(f"[TaskPlanner] 🧠 思考过程:")
        print("-" * 60)

        for chunk in response:
            if not chunk.choices or len(chunk.choices) == 0:
                continue

            delta = chunk.choices[0].delta
            thinking_chunk = delta.reasoning_content
            answer_chunk = delta.content

            # 处理思考部分
            if thinking_chunk:
                thinking_content += thinking_chunk
                if self.show_thinking:
                    print(thinking_chunk, end='', flush=True)

            # 处理回答部分
            elif answer_chunk:
                if not done_thinking:
                    if self.show_thinking:
                        print('\n\n' + '=' * 60)
                        print('[TaskPlanner] 💡 最终答案:\n' + '=' * 60)
                    done_thinking = True

                answer_content += answer_chunk
                if self.show_thinking:
                    print(answer_chunk, end='', flush=True)

        if self.show_thinking:
            print("\n")

        return thinking_content, answer_content


if __name__ == "__main__":
    # 测试
    planner = TaskPlanner(show_thinking=True)

    test_instructions = [
        "打开浏览器，搜索人工智能，下载第一张图片",
        "帮我创建一个 PPT，第一页标题是'工作总结'",
        "打开记事本，输入'Hello World'，保存到桌面"
    ]

    for instruction in test_instructions:
        print(f"\n{'=' * 60}")
        print(f"测试指令：{instruction}")
        print(f"{'=' * 60}")

        steps = planner.plan(instruction)

        if steps:
            print(f"\n📋 分解结果:")
            for step in steps:
                print(f"  {step['step']}. {step['instruction']} ({step.get('expected_action', 'N/A')})")

        input("\n按回车继续下一个测试...")
