"""
Reflect Agent - 视觉验证模块
通过双图对比验证 GUI 操作是否成功执行
支持 A/B/C/D 四种状态判断和 error_flag 机制
"""
import os
import re
import time
import traceback

import pyautogui
from dotenv import load_dotenv
from openai import OpenAI
from utils.prompt_loader import prompt_loader

load_dotenv()


class ReflectAgent:
    """
    Reflect Agent - GUI 操作验证代理（PC-Agent 风格）

    职责：
    - 通过对比操作前后的屏幕截图和UI元素变化
    - 验证 GUI 操作是否成功达成用户指令的目标
    - 返回 A/B/C/D 四种状态及详细分析
    """

    # API 配置常量
    MODELSCOPE_BASE_URL = 'https://api-inference.modelscope.cn/v1'
    VLM_MODEL_NAME = 'iic/GUI-Owl-7B'
    API_TIMEOUT = 20

    # 文本处理常量
    TEXT_PREVIEW_LENGTH = 30
    LOG_RESPONSE_LENGTH = 300

    # 状态映射表：将 A/B/C/D 映射到内部状态
    STATUS_MAP = {
        'A': {'status': 'A', 'success': True, 'error_flag': False},
        'B': {'status': 'B', 'success': False, 'error_flag': True},
        'C': {'status': 'C', 'success': False, 'error_flag': True},
        'D': {'status': 'D', 'success': False, 'error_flag': True}
    }

    # 验证状态常量
    STATUS_SUCCESS = "A"
    STATUS_ERROR_PAGE = "B"
    STATUS_NO_CHANGE = "C"
    STATUS_INCOMPLETE = "D"

    # 各状态的默认建议
    DEFAULT_SUGGESTIONS = {
        'A': '操作已成功，可以继续下一步任务。',
        'B': '检测到错误状态，建议：\n'
             '1. 检查是否进入了错误的页面或应用\n'
             '2. 尝试返回上一页或重新导航\n'
             '3. 如果持续出错，可能需要调整操作策略',
        'C': '操作未产生效果，建议：\n'
             '1. 确认点击的元素是否正确\n'
             '2. 尝试使用双击代替单击\n'
             '3. 检查是否有弹窗遮挡\n'
             '4. 重新尝试该操作',
        'D': '操作执行但目标未达成，建议：\n'
             '1. 仔细检查当前屏幕状态\n'
             '2. 可能需要执行额外的操作步骤\n'
             '3. 考虑使用不同的方法达成目标\n'
             '4. 分析是否需要先完成前置条件'
    }

    # 动作类型描述映射
    ACTION_DESCRIPTIONS = {
        'CLICK': '点击某个元素',
        'DOUBLE_CLICK': '双击打开某个元素',
        'RIGHT_CLICK': '右键点击某个元素',
        'TYPE': '输入文本',
        'SCROLL': '滚动页面',
        'KEY_PRESS': '按下功能键',
        'HOTKEY': '按下组合键',
        'DRAG_TO': '拖拽元素'
    }

    # 预编译的正则表达式（提升性能）
    THOUGHT_PATTERN = re.compile(
        r'###\s*Thought\s*###\s*\n(.*?)(?=###\s*Answer\s*###|$)',
        re.DOTALL | re.IGNORECASE
    )
    ANSWER_PATTERN = re.compile(
        r'###\s*Answer\s*###\s*\n?\s*([A-D])',
        re.IGNORECASE
    )
    SUGGESTION_PATTERN = re.compile(
        r'###\s*Suggestion\s*###\s*\n(.*?)(?=###\s*Answer\s*###|$)',
        re.DOTALL | re.IGNORECASE
    )
    STANDALONE_STATUS_PATTERN = re.compile(
        r'(?:^|\n)\s*([A-D])\s*(?:$|\n)'
    )

    def __init__(self):
        """初始化 Reflect Agent"""
        modelscope_token = os.getenv('MODELSCOPE_TOKEN')
        if not modelscope_token:
            raise ValueError("未找到 MODELSCOPE_TOKEN 环境变量")

        self.client = OpenAI(
            base_url=self.MODELSCOPE_BASE_URL,
            api_key=modelscope_token,
        )

    def verify(self,
               before_base64: str,
               after_base64: str,
               action: str,
               parameters: dict,
               step_instruction: str,
               before_ui_elements: list = None,
               after_ui_elements: list = None,
               context: dict = None) -> dict:
        """
        验证 GUI 操作是否成功（PC-Agent 风格）

        Args:
            before_base64: 操作前截图的 base64 编码
            after_base64: 操作后截图的 base64 编码
            action: 动作类型（CLICK/TYPE/SCROLL等）
            parameters: 动作参数字典
            step_instruction: 当前步骤的具体指令
            before_ui_elements: 操作前的 UI 元素列表
            after_ui_elements: 操作后的 UI 元素列表
            context: 额外的上下文信息（可选）

        Returns:
            dict: {
                'status': str,          # A/B/C/D 状态标识
                'success': bool,        # 是否成功
                'error_flag': bool,     # 是否有错误
                'changes': list[str],   # 检测到的变化列表
                'analysis': str,        # VLM 的分析文本
                'suggestion': str       # 下一步建议
            }
        """
        start_time = time.time()
        print(f"\n{'=' * 60}")
        print(f"[ReflectAgent] 🔍 开始验证操作")
        print(f"动作：{action} | 指令：{step_instruction[:50]}...")
        print(f"{'=' * 60}\n")

        try:
            # 获取屏幕尺寸
            screen_width, screen_height = pyautogui.size()

            # 提取操作意图
            operation_thought = self._extract_operation_thought(action, parameters)

            # 构建 System Prompt（固定部分：角色定义、验证标准、输出格式）
            system_prompt = prompt_loader.get_reflect_system_prompt()

            # 构建 User Prompt（动态部分：屏幕信息、UI元素、操作详情）
            user_prompt = prompt_loader.build_reflect_user_prompt(
                instruction=step_instruction,
                action=action,
                operation_thought=operation_thought,
                before_ui_elements=before_ui_elements,
                after_ui_elements=after_ui_elements,
                width=screen_width,
                height=screen_height
            )

            # 构造 VLM 请求（System + User + 双图对比）
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
                                "url": f"data:image/png;base64,{before_base64}"
                            }
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{after_base64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": user_prompt
                        }
                    ]
                }
            ]

            # print(f"[ReflectAgent] 📋 User Prompt 长度：{len(user_prompt)} 字符")
            # print(f"\n[ReflectAgent] 📄 User Prompt :\n{user_prompt}")
            # print(f"{'-' * 60}\n")

            # 调用 VLM 进行验证
            print(f"[ReflectAgent] ⏱️  [VLM] 开始分析双图差异...")
            api_start_time = time.time()

            response = self.client.chat.completions.create(
                model=self.VLM_MODEL_NAME,
                messages=messages,
                timeout=self.API_TIMEOUT
            )

            api_elapsed = time.time() - api_start_time
            print(f"[ReflectAgent] ⏱️  [VLM] API 响应耗时：{api_elapsed:.2f}s")

            # 解析响应
            parse_start_time = time.time()
            result = self._parse_result(response.choices[0].message.content)
            parse_elapsed = time.time() - parse_start_time

            print(f"[ReflectAgent] ✅ 验证结果：状态={result['status']} | "
                  f"成功={result['success']}")
            print(f"[ReflectAgent] ⏱️  [JSON] 解析耗时：{parse_elapsed:.3f}s")

            total_elapsed = time.time() - start_time
            print(f"[ReflectAgent] ⏱️  [总计] verify() 总耗时：{total_elapsed:.2f}s\n")

            return result

        except Exception as e:
            total_elapsed = time.time() - start_time
            error_trace = traceback.format_exc()
            print(f"[ReflectAgent] ❌ 验证失败（耗时 {total_elapsed:.2f}s）：{e}")
            print(f"[ReflectAgent] 📋 trace：\n{error_trace}")

            return {
                'status': 'C',
                'success': False,
                'error_flag': True,
                'changes': ['验证过程发生异常'],
                'analysis': f'验证过程发生异常：{str(e)}',
                'suggestion': '建议重新尝试该操作或检查VLM服务状态'
            }

    def _extract_operation_thought(self, action: str, parameters: dict) -> str:
        """
        从动作和参数中提取操作意图描述

        Args:
            action: 动作类型
            parameters: 动作参数

        Returns:
            操作意图描述字符串
        """
        base_thought = self.ACTION_DESCRIPTIONS.get(action, f'执行{action}操作')

        # 添加具体细节
        if action in ['CLICK', 'DOUBLE_CLICK', 'RIGHT_CLICK']:
            if 'element_id' in parameters:
                base_thought += f'（元素 ID: {parameters["element_id"]}）'
            elif 'x' in parameters and 'y' in parameters:
                base_thought += f'（位置: ({parameters["x"]}, {parameters["y"]})）'

        elif action == 'TYPE':
            text = parameters.get('text', '')
            if text:
                preview = text[:self.TEXT_PREVIEW_LENGTH] + ('...' if len(text) > self.TEXT_PREVIEW_LENGTH else '')
                base_thought += f'（文本: "{preview}"）'

        elif action == 'KEY_PRESS':
            key = parameters.get('key', '')
            if key:
                base_thought += f'（按键: {key}）'

        elif action == 'HOTKEY':
            keys = parameters.get('keys', [])
            if keys:
                base_thought += f'（组合键: {"+".join(keys)}）'

        return base_thought

    def _parse_result(self, response_text: str) -> dict:
        """
        解析 VLM 响应（纯文本格式）

        Args:
            response_text: VLM 返回的文本

        Returns:
            解析后的验证结果字典
        """
        try:
            response_text = response_text.strip()

            # 1. 提取 Thought 部分（复用预编译正则）
            thought_match = self.THOUGHT_PATTERN.search(response_text)

            analysis = ''
            if thought_match:
                analysis = thought_match.group(1).strip()

            # 2. 提取 Answer 部分（A/B/C/D）（复用预编译正则）
            answer_match = self.ANSWER_PATTERN.search(response_text)

            # 3. 提取 Suggestion 部分
            suggestion_match = self.SUGGESTION_PATTERN.search(response_text)
            vlm_suggestion = ''
            if suggestion_match:
                vlm_suggestion = suggestion_match.group(1).strip()

            if not answer_match:
                # 尝试直接查找单独的 A/B/C/D
                standalone_match = self.STANDALONE_STATUS_PATTERN.search(response_text)
                if standalone_match:
                    status = standalone_match.group(1)
                else:
                    raise ValueError("未找到有效的状态标识（A/B/C/D）")
            else:
                status = answer_match.group(1).upper()

            # 4. 状态映射（PC-Agent 标准）
            mapped = self.STATUS_MAP.get(status, self.STATUS_MAP[self.STATUS_NO_CHANGE])

            # 5. 提取变化描述（从 Thought 中）
            changes = self._extract_changes_from_analysis(analysis, status)

            # 6. 生成建议：优先使用 VLM 生成的，如果没有则使用兜底建议
            suggestion = self._generate_suggestion(status, analysis, vlm_suggestion)

            # 7. 构建最终结果
            result = {
                'status': mapped['status'],
                'success': mapped['success'],
                'error_flag': mapped['error_flag'],
                'changes': changes,
                'analysis': analysis,
                'suggestion': suggestion
            }

            return result

        except Exception as e:
            print(f"[ReflectAgent] 解析异常：{e}")
            print(f"原始响应：{response_text[:self.LOG_RESPONSE_LENGTH]}...")

            # 返回保守结果（补充完整字段）
            return {
                'status': 'C',
                'success': False,
                'error_flag': True,
                'changes': ['解析验证结果失败'],
                'analysis': f'VLM响应解析异常：{str(e)}',
                'suggestion': '建议重新尝试该操作或检查VLM服务状态'
            }

    def _extract_changes_from_analysis(self, analysis: str, status: str) -> list:
        """
        从分析文本中提取变化描述

        Args:
            analysis: 分析文本
            status: 验证状态

        Returns:
            变化描述列表
        """
        changes = []

        if status == self.STATUS_SUCCESS:
            # 成功状态，提取积极变化
            if 'appeared' in analysis.lower() or '显示' in analysis or '出现' in analysis:
                changes.append('目标元素已显示')
            if 'opened' in analysis.lower() or '打开' in analysis:
                changes.append('应用/窗口已打开')
            if 'entered' in analysis.lower() or '输入' in analysis:
                changes.append('文本已输入')

        elif status == self.STATUS_NO_CHANGE:
            changes.append('屏幕无可见变化')

        elif status == self.STATUS_INCOMPLETE:
            # 未完成状态，提取问题
            if 'wrong' in analysis.lower() or '错误' in analysis:
                changes.append('可能点击了错误的位置')
            if 'not found' in analysis.lower() or '未找到' in analysis:
                changes.append('目标元素未找到')

        # 如果没有提取到具体变化，使用默认描述
        if not changes:
            if status == self.STATUS_SUCCESS:
                changes.append('操作成功，目标达成')
            elif status == self.STATUS_ERROR_PAGE:
                changes.append('进入错误状态')
            elif status == self.STATUS_NO_CHANGE:
                changes.append('无明显变化')
            elif status == self.STATUS_INCOMPLETE:
                changes.append('操作完成但目标未达成')

        return changes

    def _generate_suggestion(self, status: str, analysis: str, vlm_suggestion: str = '') -> str:
        """
        根据验证状态生成下一步建议
        Args:
            status: 验证状态
            analysis: 分析文本
            vlm_suggestion: VLM 生成的建议（可选）

        Returns:
            建议字符串
        """
        # 如果 VLM 生成了有效建议，优先使用
        if vlm_suggestion and len(vlm_suggestion) > 0:
            return vlm_suggestion

        # 否则使用固定的兜底建议
        return self.DEFAULT_SUGGESTIONS.get(
            status,
            '建议重新评估当前状态并调整策略。'
        )
