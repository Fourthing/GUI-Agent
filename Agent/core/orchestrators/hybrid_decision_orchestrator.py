# File: Agent/core/orchestrators/hybrid_decision_orchestrator.py
"""
混合决策编排器
结合 ACI、规则引擎和 VLM，智能选择最优决策路径
"""
from .decision_orchestrator import DecisionOrchestrator
from ..windows_aci import WindowsACI
from PIL import Image
import time
from typing import Dict, Optional


class HybridDecisionOrchestrator:
    """混合决策器"""

    def __init__(self):
        self.aci = WindowsACI(top_app_only=True)
        self.vlm_orchestrator = DecisionOrchestrator()

        # 决策统计
        self.stats = {
            'aci_based_decisions': 0,
            'rule_based_decisions': 0,
            'vlm_based_decisions': 0,
            'total_decisions': 0
        }

    def decide(self,
               screenshot: Image.Image,
               user_instruction: str,
               step_no: int = 1,
               task_id: str = None) -> dict:
        """
        混合决策主流程（改进版）

        决策树:
        1. 使用 ACI 提取 UI 元素
        2. 将 UI 元素注入到 VLM prompt 中
        3. VLM 根据 UI 元素 + 截图做出决策
        """
        start_time = time.time()
        log_prefix = f"[Task:{task_id}] Step:{step_no}" if task_id else f"Step:{step_no}"

        print(f"\n{log_prefix} 🧠 [HybridDecision] 开始决策分析...")

        # ========== Step 1: 使用 ACI 提取 UI 元素 ==========
        print(f"{log_prefix} 🔍 [ACI] 正在提取 UI 元素...")

        obs = {'screenshot': screenshot}
        ui_elements = self.aci.linearize_and_annotate_tree(obs)

        if not ui_elements:
            print(f"{log_prefix} ⚠️  [ACI] 未提取到元素，使用纯视觉决策")
            ui_elements = []
        else:
            print(f"{log_prefix} ✓ [ACI] 提取到 {len(ui_elements)} 个元素")

        # ========== Step 2: 调用 VLM 决策（注入 UI 元素信息）==========
        print(f"{log_prefix} 🤖 [VLM] 调用 VLM 决策（含 UI 元素增强）...")

        vlm_result = self._vlm_decision_with_aci(
            screenshot=screenshot,
            ui_elements=ui_elements,
            user_instruction=user_instruction,
            step_no=step_no,
            task_id=task_id
        )

        decision_time = time.time() - start_time

        self.stats['vlm_based_decisions'] += 1
        self.stats['total_decisions'] += 1

        print(f"{log_prefix} 🤖 [VLM] VLM 决策完成 (耗时：{decision_time:.2f}s)")

        return {
            **vlm_result,
            'decision_method': 'aci_enhanced_vlm',
            'decision_time': decision_time,
            'step_no': step_no,
            'task_id': task_id
        }

    def _vlm_decision_with_aci(self,
                               screenshot: Image.Image,
                               ui_elements: list,
                               user_instruction: str,
                               step_no: int,
                               task_id: str) -> dict:
        """
        调用 VLM 决策，并注入 ACI 提取的 UI 元素信息

        参考 PC-Agent 的设计：
        1. ACI 负责提取准确的 UI 结构
        2. VLM 负责智能决策（结合截图 + UI 元素列表）
        """
        from ..windows_aci import WindowsACI
        from utils.screen_capture import ScreenCapturer

        capturer = ScreenCapturer()
        base64_image = capturer.pil_to_base64(screenshot)

        # 构建增强的 prompt，注入 UI 元素信息
        enhanced_instruction = user_instruction

        if ui_elements:
            # 构建 UI 元素列表文本
            ui_info = "\n\n【界面 UI 元素列表】（由 Windows UI Automation 提取）\n"
            ui_info += "格式：ID | 角色 | 标题/文本 | 位置\n"
            ui_info += "-" * 80 + "\n"

            # 限制显示的元素数量（避免 prompt 过长）
            max_elements = 50
            displayed_elements = ui_elements[:max_elements]

            for idx, elem in enumerate(displayed_elements):
                role = elem.get('role', 'Unknown')
                title = elem.get('title', '')
                text = elem.get('text', '')
                position = elem.get('position', (0, 0))

                # 优先使用 title，其次 text
                description = title or text or '未命名'

                ui_info += f"ID={idx:2d} | [{role:15s}] | {description:30s} | 位置={position}\n"

            if len(ui_elements) > max_elements:
                ui_info += f"... 还有 {len(ui_elements) - max_elements} 个元素未显示\n"

            ui_info += "\n【使用说明】\n"
            ui_info += "1. 上述 UI 元素列表提供了界面中所有可交互元素的准确信息\n"
            ui_info += "2. 执行 CLICK 等操作时，优先使用 element_id（例如：element_id=5）\n"
            ui_info += "3. element_id 会在执行时自动转换为准确的屏幕坐标\n"
            ui_info += "4. 如果找不到合适的 element_id，再使用 x/y 坐标\n"

            enhanced_instruction = user_instruction + ui_info

        # 调用原始的 VLM 决策
        result = self.vlm_orchestrator.decide(
            image_url=f"data:image/png;base64,{base64_image}",
            user_instruction=enhanced_instruction,
            step_no=step_no,
            task_id=task_id
        )

        return result

    def get_stats(self) -> dict:
        """获取决策统计"""
        total = self.stats['total_decisions']
        if total == 0:
            return self.stats

        return {
            **self.stats,
            'aci_enhanced_percentage': f"{self.stats['vlm_based_decisions'] / total * 100:.1f}%"
        }
