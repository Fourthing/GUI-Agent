"""
Prompt 加载器 - 从 Python 模块加载 AI 模型的提示词
"""
from typing import Dict

from config.prompts import (
    DECISION_SYSTEM_PROMPT_TEMPLATE,
    PLANNING_SYSTEM_PROMPT,
    REFLECT_PROMPT_PARTS,
    REFLECT_SYSTEM_PROMPT
)


class PromptLoader:
    """Prompt 配置加载器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_decision_system_prompt(self, screen_width: int, screen_height: int) -> str:
        """
        获取 Decision Orchestrator 的 System Prompt

        Args:
            screen_width: 屏幕宽度
            screen_height: 屏幕高度

        Returns:
            格式化后的 System Prompt
        """
        # 使用 Template.substitute()，不会与 JSON 的花括号冲突
        return DECISION_SYSTEM_PROMPT_TEMPLATE.substitute(
            screen_width=screen_width,
            screen_height=screen_height,
            screen_width_minus_1=screen_width - 1,
            screen_height_minus_1=screen_height - 1,
            screen_width_half=screen_width // 2,
            screen_height_half=screen_height // 2
        )

    def get_planning_system_prompt(self) -> str:
        """获取 Planning Orchestrator 的 System Prompt"""
        return PLANNING_SYSTEM_PROMPT

    def get_reflect_prompt_parts(self) -> Dict[str, str]:
        """获取 Reflect Orchestrator 的 Prompt 片段"""
        return REFLECT_PROMPT_PARTS

    def build_reflect_prompt(
        self,
        instruction: str,
        action: str,
        operation_thought: str,
        before_ui_elements: list = None,
        after_ui_elements: list = None,
        width: int = None,
        height: int = None
    ) -> str:
        """
        构建 Reflect Orchestrator 的验证 Prompt
        """
        parts = REFLECT_PROMPT_PARTS
        prompt_parts = []

        # 1. 屏幕基本信息
        if width and height:
            prompt_parts.append(
                parts['screen_info_with_size'].format(width=width, height=height) + "\n\n"
            )
        else:
            prompt_parts.append(parts['screen_info_without_size'] + "\n\n")

        # 2. UI 元素说明
        prompt_parts.append(parts['ui_elements_intro'] + "\n\n")

        # 3. 操作前的 UI 元素
        if before_ui_elements and len(before_ui_elements) > 0:
            prompt_parts.append(parts['before_operation_header'])
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
            prompt_parts.append(parts['after_operation_header'])
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
        prompt_parts.append(parts['current_operation_header'])
        prompt_parts.append(parts['user_instruction_prefix'].format(instruction=instruction))
        prompt_parts.append(parts['operation_context'])
        prompt_parts.append(parts['operation_thought_prefix'].format(thought=operation_thought))
        prompt_parts.append(parts['operation_action_prefix'].format(action=action))
        prompt_parts.append("")

        # 6. 响应要求
        prompt_parts.append(parts['response_requirements_header'])
        prompt_parts.append(parts['response_requirement_1'])
        prompt_parts.append(parts['response_requirement_2'])
        prompt_parts.append(parts['response_requirement_3'])
        prompt_parts.append(parts['choose_one_instruction'])
        prompt_parts.append(parts['option_a'])
        prompt_parts.append(parts['option_b'])
        prompt_parts.append(parts['option_c'])
        prompt_parts.append(parts['option_d'])
        prompt_parts.append("")

        # 7. 输出格式
        prompt_parts.append(parts['output_format_header'])
        prompt_parts.append(parts['output_format_instruction'])
        prompt_parts.append(parts['thought_format'])
        prompt_parts.append(parts['answer_format'])

        return "\n".join(prompt_parts)

    def reload(self):
        """重新加载配置（Python 模块需要重启服务）"""
        print("[PromptLoader] ⚠️  Python 模块配置需要重启服务才能生效")


# 全局单例
prompt_loader = PromptLoader()
