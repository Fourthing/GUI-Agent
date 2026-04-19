"""
Reflect Agent - 视觉验证模块
基于双图对比验证 GUI 操作是否成功执行
支持 A/B/C/D/E 五种状态判断和 error_flag 机制
"""
from openai import OpenAI
import os
import json
from dotenv import load_dotenv

load_dotenv()


class ReflectAgent:
    """
    Reflect Agent - GUI 操作验证代理

    通过对比操作前后的屏幕截图，判断操作是否真正达成目标。
    返回细粒度的验证结果（A/B/C/D/E 五种状态）。
    """

    # 验证状态常量
    STATUS_SUCCESS = "A"  # 操作成功且目标完全达成
    STATUS_ERROR_PAGE = "B"  # 进入错误状态（404、崩溃等）
    STATUS_NO_CHANGE = "C"  # 屏幕无任何变化
    STATUS_INCOMPLETE = "D"  # 操作完成但目标未达成
    STATUS_PARTIAL = "E"  # 部分成功，需要额外操作

    def __init__(self):
        """初始化 Reflect Agent"""
        modelscope_token = os.getenv('MODELSCOPE_TOKEN')
        if not modelscope_token:
            raise ValueError("未找到 MODELSCOPE_TOKEN 环境变量")

        self.client = OpenAI(
            base_url='https://api-inference.modelscope.cn/v1',
            api_key=modelscope_token,
        )

        self.system_prompt = '''你是一名专业的 GUI 操作验证专家。你的任务是通过对比操作前后的屏幕截图，判断某个 GUI 操作是否真正达成了预期目标。

## 核心职责
1. 对比两张截图的 UI 元素列表和视觉内容
2. 判断操作是否达成了**用户指令的实际目标**
3. 给出明确的验证结论（A/B/C/D）

## 验证状态说明（仅 4 种）

### A - 成功 (Success)
操作完全达成用户指令的目标，屏幕变化符合预期。

**示例**: 
- 用户要"关闭窗口" → 窗口确实消失了
- 用户要"输入 Hello" → 文本框中显示了 "Hello"

### B - 错误状态 (Error Page/State)
进入了错误页面或异常状态（404、崩溃弹窗、网络错误等）。

### C - 无变化 (No Change)
两张截图几乎完全相同，操作未生效。

### D - 未完成 (Incomplete)
操作执行了，但用户指令的目标**未达成**。
例如：点击了错误的按钮、输入了错误的位置、只完成了部分步骤。

## 输出格式（严格遵循）
你必须按照以下格式输出，不要添加任何额外内容：

### Thought ###
在这里详细分析：
1. 操作前后的关键差异是什么
2. 这些差异是否符合操作的预期
3. 用户指令的目标是否真正达成

### Answer ###
A 或 B 或 C 或 D（只能选一个字母）

## 关键判断原则
1. **关注用户目标**：不是"屏幕有没有变化"，而是"用户想要的结果出现了吗"
2. **结合 UI 元素**：优先使用提供的 UI 元素列表进行精确对比
'''

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
        验证 GUI 操作是否成功

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
                'status': str,              # A/B/C/D/E
                'success': bool,            # 是否成功
                'error_flag': bool,         # 是否需要纠正/重试
                'confidence': float,        # 置信度
                'changes': list,            # 检测到的变化
                'analysis': str,            # 详细分析
                'suggestion': str           # 下一步建议
            }
        """
        try:
            # 构建验证 prompt
            prompt = self._build_prompt(
                action=action,
                parameters=parameters,
                step_instruction=step_instruction,
                before_ui_elements=before_ui_elements,
                after_ui_elements=after_ui_elements,
                context=context
            )

            # 构造 VLM 请求（双图对比）
            messages = [
                {
                    "role": "system",
                    "content": self.system_prompt
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
                            "text": prompt
                        }
                    ]
                }
            ]

            # 调用 DeepSeek-V3 进行验证
            # 调用 VLM 进行验证（使用与决策相同的模型）
            response = self.client.chat.completions.create(
                model='iic/GUI-Owl-7B',  # 改为与决策相同的模型
                messages=messages,
            )

            # 解析响应
            result = self._parse_result(response.choices[0].message.content)

            return result

        except Exception as e:
            # 异常情况：返回保守的验证结果
            print(f"[ReflectAgent] 验证异常：{str(e)}")
            return {
                'status': 'C',  # 默认认为无变化
                'success': False,
                'error_flag': True,  # 建议重试
                'confidence': 0.3,
                'changes': [],
                'analysis': f'验证过程发生异常：{str(e)}',
                'suggestion': '建议重新尝试该操作'
            }

    def _build_prompt(self,
                      action: str,
                      parameters: dict,
                      step_instruction: str,
                      before_ui_elements: list = None,
                      after_ui_elements: list = None,
                      context: dict = None) -> str:
        """
        构建验证 prompt

        Args:
            action: 动作类型
            parameters: 动作参数
            step_instruction: 步骤指令
            context: 上下文信息

        Returns:
            完整的验证 prompt
        """
        prompt_parts = []

        # 1. 操作信息
        prompt_parts.append("【操作信息】")
        prompt_parts.append(f"动作类型：{action}")
        prompt_parts.append(f"操作参数：{parameters}")
        prompt_parts.append(f"预期目标：{step_instruction}")
        prompt_parts.append("")

        # 2. 上下文信息（如果有）
        if context:
            prompt_parts.append("【上下文信息】")
            if 'attempt' in context:
                prompt_parts.append(f"当前尝试次数：第{context['attempt']}次")
            if 'history' in context and len(context['history']) > 0:
                last_action = context['history'][-1]
                prompt_parts.append(f"上一步操作：{last_action.get('action', '未知')}")
            prompt_parts.append("")

        # 3. 验证要求
        prompt_parts.append("【验证要求】")
        prompt_parts.append("请仔细对比这两张截图（第一张是操作前，第二张是操作后），完成以下任务：")
        prompt_parts.append("1. 详细描述两张截图的所有视觉差异")
        prompt_parts.append("2. 判断这些差异是否表明操作成功达成了预期目标")
        prompt_parts.append("3. 如果没有达成，分析可能的原因")
        prompt_parts.append("4. 如果失败了，给出具体的纠正建议")
        prompt_parts.append("")

        # 4. 输出格式强调
        prompt_parts.append("【重要】请严格按照以下 JSON 格式输出：")
        prompt_parts.append('''{
    "status": "A|B|C|D|E",
    "success": true/false,
    "confidence": 0.0-1.0,
    "changes_detected": ["变化 1", "变化 2"],
    "analysis": "详细分析...",
    "suggestion": "下一步建议..."
}''')

        return "\n".join(prompt_parts)

    def _parse_result(self, response_text: str) -> dict:
        """
        解析 VLM 响应

        Args:
            response_text: VLM 返回的文本

        Returns:
            解析后的验证结果字典
        """
        try:
            # 清理可能的 markdown 标记
            response_text = response_text.strip()
            if response_text.startswith('```json'):
                response_text=response_text[7:]
            if response_text.endswith('```'):
                response_text=response_text[:-3]
            response_text=response_text.strip()
            # 尝试直接 JSON 解析
            result_json = json.loads(response_text)

            # 提取字段（带默认值）
            raw_status = result_json.get('status', 'C')

            # 状态映射：原始状态 → (标准化状态，success, error_flag)
            status_map = {
                'A': ('A', True, False),  # 成功
                'B': ('B', False, True),  # 错误
                'C': ('C', False, True),  # 无变化
                'D': ('D', False, True),  # 未完成
                'E': ('E', True, False)  # 部分成功
            }

            mapped = status_map.get(raw_status, ('C', False, True))

            # 构建标准化结果
            result = {
                'status': mapped[0],
                'success': mapped[1],
                'error_flag': mapped[2],
                'confidence': float(result_json.get('confidence', 0.5)),
                'changes': result_json.get('changes_detected', []),
                'analysis': result_json.get('analysis', ''),
                'suggestion': result_json.get('suggestion', '')
            }

            # 验证置信度范围
            if not (0.0 <= result['confidence'] <= 1.0):
                result['confidence'] = 0.5

            return result

        except json.JSONDecodeError as e:
            print(f"[ReflectAgent] JSON 解析失败：{e}")
            print(f"原始响应：{response_text[:200]}...")

            # 返回保守结果
            return {
                'status': 'C',
                'success': False,
                'error_flag': True,
                'confidence': 0.3,
                'changes': [],
                'analysis': f'响应格式错误，无法解析：{str(e)}',
                'suggestion': '建议重新尝试或检查操作步骤'
            }
        except Exception as e:
            print(f"[ReflectAgent] 解析异常：{e}")
            return {
                'status': 'C',
                'success': False,
                'error_flag': True,
                'confidence': 0.3,
                'changes': [],
                'analysis': f'解析过程出错：{str(e)}',
                'suggestion': '建议重新尝试该操作'
            }