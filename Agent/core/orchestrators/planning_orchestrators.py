"""
任务规划器（基于 DeepSeek-V3）
使用 DeepSeek-V3 模型将复杂指令分解为多个可执行的步骤
支持显示思考过程
"""
import time

from openai import OpenAI
import os
import json
from dotenv import load_dotenv

load_dotenv()


class TaskPlanner:
    """任务规划器：将复杂指令分解为步骤序列"""

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

        self.system_prompt = '''你是一名 GUI 操作助手的任务规划专家。你的任务是将用户的复杂指令分解为一系列简单的、可执行的 GUI 原子操作步骤。

## 核心原则
1. 每个步骤必须是单一、明确的操作（点击、输入、滚动等）
2. 步骤之间要有逻辑顺序和因果关系
3. 步骤描述要清晰具体，适合视觉模型理解
4. 考虑操作的上下文和前置条件
5. 通常 1-15 个步骤完成一个复杂任务

## 输出格式要求
你必须输出一个 JSON 数组，每个元素包含以下字段：
{
    "step": <序号，从 1 开始>,
    "instruction": "<清晰的步骤描述，包含具体的 UI 元素和操作>",
    "expected_action": "<预期的动作类型：CLICK/TYPE/SCROLL/KEY_PRESS/FINISH/DOUBLE_CLICK/RIGHT_CLICK/DRAG_TO/HOTKEY>"
}

## 示例 1
用户：打开浏览器，搜索人工智能，下载第一张图片
输出：
[
    {"step": 1, "instruction": "双击桌面上的 Chrome 浏览器图标", "expected_action": "CLICK"},
    {"step": 2, "instruction": "等待浏览器完全加载后，在地址栏中输入 baidu.com 并按回车", "expected_action": "TYPE"},
    {"step": 3, "instruction": "在百度搜索框中输入'人工智能'", "expected_action": "TYPE"},
    {"step": 4, "instruction": "点击百度一下按钮进行搜索", "expected_action": "CLICK"},
    {"step": 5, "instruction": "在搜索结果页面点击'图片'分类标签", "expected_action": "CLICK"},
    {"step": 6, "instruction": "右键点击第一张图片，在弹出菜单中选择'图片另存为'", "expected_action": "CLICK"}
]

## 示例 2
用户：帮我创建一个 PPT，第一页标题是'工作总结'
输出：
[
    {"step": 1, "instruction": "点击开始菜单或桌面搜索框", "expected_action": "CLICK"},
    {"step": 2, "instruction": "输入'PowerPoint'并点击打开应用", "expected_action": "TYPE"},
    {"step": 3, "instruction": "在 PowerPoint 启动界面选择'空白演示文稿'", "expected_action": "CLICK"},
    {"step": 4, "instruction": "在第一页的标题占位符中点击", "expected_action": "CLICK"},
    {"step": 5, "instruction": "输入文本'工作总结'", "expected_action": "TYPE"}
]

请仔细分析用户指令，生成合理的步骤序列。'''

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

            # 调用 DeepSeek-V3 进行流式响应
            response = self.client.chat.completions.create(
                model='deepseek-ai/DeepSeek-V3.2',  # 使用 DeepSeek-V3
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"请将以下指令分解为可执行的步骤：\n\n{user_instruction}"}
                ],
                stream=True,  # 启用流式输出
                extra_body=extra_body
            )

            # 处理流式响应
            thinking_content = ""
            answer_content = ""
            done_thinking = False

            print(f"[TaskPlanner] 🧠 思考过程:")
            print("-" * 60)

            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta

                    # 获取思考内容
                    thinking_chunk = delta.reasoning_content
                    # 获取答案内容
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

            print(f"[TaskPlanner] ✓ 响应接收完成")

            # 解析 JSON 响应
            time.sleep(0.5)
            steps = self._parse_response(answer_content)

            if steps and len(steps) > 0:
                print(f"\n[TaskPlanner] ✅ 成功分解为 {len(steps)} 个步骤")
                for step in steps:
                    step_no = step.get('step', '?')
                    instruction = step.get('instruction', '')
                    action = step.get('expected_action', 'N/A')
                    print(f"  步骤 {step_no}: {instruction[:60]}... ({action})")
            else:
                print(f"[TaskPlanner] ⚠️  分解结果为空")

            return steps

        except Exception as e:
            print(f"\n[TaskPlanner] ❌ 规划失败：{str(e)}")
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