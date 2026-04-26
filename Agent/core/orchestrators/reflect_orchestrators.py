"""
Reflect Agent - 视觉验证模块（重构版）
基于 PC-Agent 实现，通过双图对比验证 GUI 操作是否成功执行
支持 A/B/C/D 四种状态判断和 error_flag 机制
"""
from openai import OpenAI
import os
import re
from dotenv import load_dotenv

load_dotenv()


class ReflectAgent:
    """
    Reflect Agent - GUI 操作验证代理（PC-Agent 风格）

    通过对比操作前后的屏幕截图和 UI 元素列表，判断操作是否真正达成用户目标。
    返回细粒度的验证结果（A/B/C/D 四种状态）。
    """

    # 验证状态常量（PC-Agent 标准）
    STATUS_SUCCESS = "A"        # 操作成功且用户目标完全达成
    STATUS_ERROR_PAGE = "B"     # 进入错误状态（404、崩溃等）
    STATUS_NO_CHANGE = "C"      # 屏幕无任何变化
    STATUS_INCOMPLETE = "D"     # 操作执行但用户目标未达成

    def __init__(self):
        """初始化 Reflect Agent"""
        modelscope_token = os.getenv('MODELSCOPE_TOKEN')
        if not modelscope_token:
            raise ValueError("未找到 MODELSCOPE_TOKEN 环境变量")

        self.client = OpenAI(
            base_url='https://api-inference.modelscope.cn/v1',
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
            before_base64: 操作前的屏幕截图（base64 编码）
            after_base64: 操作后的屏幕截图（base64 编码）
            action: 执行的动作类型（CLICK/TYPE/SCROLL 等）
            parameters: 动作的参数（坐标、文本等）
            step_instruction: 当前步骤的指令描述
            before_ui_elements: 操作前的 UI 元素列表（可选）
            after_ui_elements: 操作后的 UI 元素列表（可选）
            context: 额外上下文信息（可选）

        Returns:
            {
                'status': str,              # A/B/C/D
                'success': bool,            # 是否成功
                'error_flag': bool,         # 是否需要纠正/重试
                'confidence': float,        # 置信度 (0.0-1.0)
                'changes': list,            # 检测到的变化
                'analysis': str,            # 详细分析
                'suggestion': str           # 下一步建议
            }
        """
        try:
            # 获取屏幕尺寸（用于 prompt）
            import pyautogui
            screen_width, screen_height = pyautogui.size()

            # 构建验证 prompt（PC-Agent 格式）
            prompt = self._build_prompt(
                instruction=step_instruction,
                action=action,
                parameters=parameters,
                before_ui_elements=before_ui_elements,
                after_ui_elements=after_ui_elements,
                width=screen_width,
                height=screen_height
            )

            # 构造 VLM 请求（双图对比）
            messages = [
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
                            "text": prompt
                        }
                    ]
                }
            ]

            # 调用 VLM 进行验证（使用与决策相同的模型）
            response = self.client.chat.completions.create(
                model='iic/GUI-Owl-7B',
                messages=messages,
                timeout=20
            )

            # 解析响应（纯文本格式）
            result = self._parse_result(response.choices[0].message.content)

            return result

        except Exception as e:
            # 异常情况：返回保守的验证结果
            print(f"[ReflectAgent] 验证异常：{str(e)}")
            return {
                'status': 'C',
                'success': False,
                'error_flag': True,
                'confidence': 0.3,
                'changes': [],
                'analysis': f'验证过程发生异常：{str(e)}',
                'suggestion': '建议重新尝试该操作'
            }

    def _build_prompt(self,
                      instruction: str,
                      action: str,
                      parameters: dict,
                      before_ui_elements: list = None,
                      after_ui_elements: list = None,
                      width: int = None,
                      height: int = None) -> str:
        """
        构建验证 prompt（PC-Agent 格式）

        Args:
            instruction: 用户指令
            action: 动作类型
            parameters: 动作参数
            before_ui_elements: 操作前的 UI 元素列表
            after_ui_elements: 操作后的 UI 元素列表
            width: 屏幕宽度
            height: 屏幕高度

        Returns:
            完整的验证 prompt
        """
        prompt_parts = []

        # 1. 屏幕基本信息
        if width and height:
            prompt_parts.append(
                f"These images are two computer screenshots before and after an operation. "
                f"Their widths are {width} pixels and their heights are {height} pixels.\n\n"
            )
        else:
            prompt_parts.append(
                "These images are two computer screenshots before and after an operation.\n\n"
            )

        # 2. UI 元素说明
        prompt_parts.append(
            "In order to help you better perceive the content in this screenshot, "
            "we extract some information on the current screenshot. "
            "The information consists of format: coordinates; content. "
            "The format of the coordinates is [x, y], x is the pixel from left to right "
            "and y is the pixel from top to bottom; the content is a text or an icon description.\n\n"
        )

        # 3. 操作前的 UI 元素
        if before_ui_elements and len(before_ui_elements) > 0:
            prompt_parts.append("### Before the current operation ###")
            prompt_parts.append("Screenshot information:")
            for elem in before_ui_elements:
                coords = elem.get('position', (0, 0))
                size = elem.get('size', (0, 0))
                center_x = coords[0] + size[0] // 2
                center_y = coords[1] + size[1] // 2
                text = elem.get('title') or elem.get('text') or 'icon'

                if text and text != 'icon' and coords != (0, 0):
                    prompt_parts.append(f"[{center_x}, {center_y}]; {text}")
            prompt_parts.append("\n")

        # 4. 操作后的 UI 元素
        if after_ui_elements and len(after_ui_elements) > 0:
            prompt_parts.append("### After the current operation ###")
            prompt_parts.append("Screenshot information:")
            for elem in after_ui_elements:
                coords = elem.get('position', (0, 0))
                size = elem.get('size', (0, 0))
                center_x = coords[0] + size[0] // 2
                center_y = coords[1] + size[1] // 2
                text = elem.get('title') or elem.get('text') or 'icon'

                if text and text != 'icon' and coords != (0, 0):
                    prompt_parts.append(f"[{center_x}, {center_y}]; {text}")
            prompt_parts.append("\n")

        # 5. 当前操作信息
        prompt_parts.append("### Current operation ###")
        prompt_parts.append(f"The user's instruction is: {instruction}")
        prompt_parts.append(
            "In the process of completing the requirements of instruction, "
            "an operation is performed on the computer. Below are the details of this operation:"
        )

        # 提取操作意图（从 action 和 parameters）
        operation_thought = self._extract_operation_thought(action, parameters)
        prompt_parts.append(f"Operation thought: {operation_thought}")
        prompt_parts.append(f"Operation action: {action}")
        prompt_parts.append("")

        # 6. 响应要求
        prompt_parts.append("### Response requirements ###")
        prompt_parts.append(
            "Now you need to output the following content based on the screenshots "
            "before and after the current operation:"
        )
        prompt_parts.append(
            "1. Whether the result of the \"Operation action\" meets your expectation of \"Operation thought\"?"
        )
        prompt_parts.append(
            "2. IMPORTANT: By carefully examining the screenshot after the operation, "
            "verify if the actual goal described in the user's instruction is achieved."
        )
        prompt_parts.append("Choose one of the following:")
        prompt_parts.append(
            "A: The result of the \"Operation action\" meets my expectation of \"Operation thought\" "
            "AND the actual goal in the instruction is achieved based on the current screenshot."
        )
        prompt_parts.append(
            "B: The \"Operation action\" results in a wrong page and I need to do something to correct this."
        )
        prompt_parts.append("C: The \"Operation action\" produces no changes.")
        prompt_parts.append(
            "D: The \"Operation action\" seems to complete, but the actual goal in the instruction "
            "is NOT achieved based on the current screenshot (e.g., clicked wrong position, wrong item selected)."
        )
        prompt_parts.append("")

        # 7. 输出格式
        prompt_parts.append("### Output format ###")
        prompt_parts.append("Your output format is:")
        prompt_parts.append(
            "### Thought ###\n"
            "Your thought about the question. Please explicitly verify if the goal "
            "in the instruction is achieved by checking the screenshot."
        )
        prompt_parts.append("### Answer ###\nA or B or C or D")

        return "\n".join(prompt_parts)

    def _extract_operation_thought(self, action: str, parameters: dict) -> str:
        """
        从动作和参数中提取操作意图描述

        Args:
            action: 动作类型
            parameters: 动作参数

        Returns:
            操作意图描述字符串
        """
        action_descriptions = {
            'CLICK': '点击某个元素',
            'DOUBLE_CLICK': '双击打开某个元素',
            'RIGHT_CLICK': '右键点击某个元素',
            'TYPE': '输入文本',
            'SCROLL': '滚动页面',
            'KEY_PRESS': '按下功能键',
            'HOTKEY': '按下组合键',
            'DRAG_TO': '拖拽元素'
        }

        base_thought = action_descriptions.get(action, f'执行{action}操作')

        # 添加具体细节
        if action in ['CLICK', 'DOUBLE_CLICK', 'RIGHT_CLICK']:
            if 'element_id' in parameters:
                base_thought += f'（元素 ID: {parameters["element_id"]}）'
            elif 'x' in parameters and 'y' in parameters:
                base_thought += f'（位置: ({parameters["x"]}, {parameters["y"]})）'

        elif action == 'TYPE':
            text = parameters.get('text', '')
            if text:
                preview = text[:30] + ('...' if len(text) > 30 else '')
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

            # 1. 提取 Thought 部分
            thought_match = re.search(
                r'###\s*Thought\s*###\s*\n(.*?)(?=###\s*Answer\s*###|$)',
                response_text,
                re.DOTALL | re.IGNORECASE
            )

            analysis = ''
            if thought_match:
                analysis = thought_match.group(1).strip()

            # 2. 提取 Answer 部分（A/B/C/D）
            answer_match = re.search(
                r'###\s*Answer\s*###\s*\n?\s*([A-D])',
                response_text,
                re.IGNORECASE
            )

            if not answer_match:
                # 尝试直接查找单独的 A/B/C/D
                standalone_match = re.search(
                    r'(?:^|\n)\s*([A-D])\s*(?:$|\n)',
                    response_text
                )
                if standalone_match:
                    status = standalone_match.group(1)
                else:
                    raise ValueError("未找到有效的状态标识（A/B/C/D）")
            else:
                status = answer_match.group(1).upper()

            # 3. 状态映射（PC-Agent 标准）
            status_map = {
                'A': {'status': 'A', 'success': True, 'error_flag': False, 'confidence': 0.9},
                'B': {'status': 'B', 'success': False, 'error_flag': True, 'confidence': 0.8},
                'C': {'status': 'C', 'success': False, 'error_flag': True, 'confidence': 0.7},
                'D': {'status': 'D', 'success': False, 'error_flag': True, 'confidence': 0.6}
            }

            mapped = status_map.get(status, status_map['C'])

            # 4. 提取变化描述（从 Thought 中）
            changes = self._extract_changes_from_analysis(analysis, status)

            # 5. 生成建议
            suggestion = self._generate_suggestion(status, analysis)

            # 6. 构建最终结果
            result = {
                'status': mapped['status'],
                'success': mapped['success'],
                'error_flag': mapped['error_flag'],
                'confidence': mapped['confidence'],
                'changes': changes,
                'analysis': analysis,
                'suggestion': suggestion
            }

            return result

        except Exception as e:
            print(f"[ReflectAgent] 解析异常：{e}")
            print(f"原始响应：{response_text[:300]}...")

            # 返回保守结果
            return {
                'status': 'error',
                'success': False,
                'error_flag': True,
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

        if status == 'A':
            # 成功状态，提取积极变化
            if 'appeared' in analysis.lower() or '显示' in analysis or '出现' in analysis:
                changes.append('目标元素已显示')
            if 'opened' in analysis.lower() or '打开' in analysis:
                changes.append('应用/窗口已打开')
            if 'entered' in analysis.lower() or '输入' in analysis:
                changes.append('文本已输入')

        elif status == 'C':
            changes.append('屏幕无可见变化')

        elif status == 'D':
            # 未完成状态，提取问题
            if 'wrong' in analysis.lower() or '错误' in analysis:
                changes.append('可能点击了错误的位置')
            if 'not found' in analysis.lower() or '未找到' in analysis:
                changes.append('目标元素未找到')

        # 如果没有提取到具体变化，使用默认描述
        if not changes:
            if status == 'A':
                changes.append('操作成功，目标达成')
            elif status == 'B':
                changes.append('进入错误状态')
            elif status == 'C':
                changes.append('无明显变化')
            elif status == 'D':
                changes.append('操作完成但目标未达成')

        return changes

    def _generate_suggestion(self, status: str, analysis: str) -> str:
        """
        根据验证状态生成下一步建议

        Args:
            status: 验证状态
            analysis: 分析文本

        Returns:
            建议字符串
        """
        suggestions = {
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

        return suggestions.get(status, '建议重新评估当前状态并调整策略。')
