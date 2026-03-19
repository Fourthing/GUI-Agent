from openai import OpenAI
import os
import json
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
        log_prefix = f"[Task:{task_id}] Step:{step_no}" if task_id else f"Step:{step_no}"

        # ========== 获取屏幕分辨率（新增！）==========
        import pyautogui
        screen_width, screen_height = pyautogui.size()

        messages = [
            {
                "role": "system",
                "content": '''## 1. 核心角色 (Core Role)
你是一个顶级的 AI 视觉操作代理。你的任务是分析电脑屏幕截图，理解用户的指令，然后将任务分解为单一、精确的 GUI 原子操作。

## 2. [CRITICAL] JSON Schema & 绝对规则
你的输出**必须**是一个严格符合以下规则的 JSON 对象。
- **[R1] 严格的 JSON**: 回复必须是且只能是一个 JSON 对象，禁止添加额外文本。
- **[R2] thought 结构**: "在这里描述思考过程。例如：用户想打开浏览器，我看到了 Chrome 图标，所以下一步是点击它。"
- **[R3] Action 值**: 必须为大写字符串（如 "CLICK", "TYPE"）。
- **[R4] parameters 结构**: 必须与工具集中的模板完全一致。

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
- 输出时参考："x": 100, // ← 必须是单个整数（横坐标） "y": 200, // ← 必须是单个整数（纵坐标）。请检查输出，不能出现单个x和y是一个数组的情况！！！比如“'x': [1204, 13]”

## 5. Reflect 验证机制
你的每个操作决策都会被 Reflect Agent 验证系统检查。

### 验证流程
1. 你生成操作决策（如 "CLICK at (100, 200)"）
2. 系统执行你的操作
3. Reflect Agent 对比操作前后的屏幕截图
4. Reflect 返回验证结果（A/B/C/D/E 五种状态）
   - A: 操作成功且目标达成 ✅
   - B: 进入错误状态（如 404、崩溃）❌
   - C: 屏幕无变化（可能点错了位置）⚠️
   - D: 操作完成但目标未达成（需要补充操作）⚠️
   - E: 部分成功（可以继续）✅

### 如果收到 Reflect 反馈
当系统检测到操作失败时，你会收到如下反馈信息：

【重要反馈】上一步操作未能完全达成目标。
验证状态：C
检测到的变化：[]
分析：点击后界面没有任何反应
建议：请重新检查点击位置是否准确

此时你应该：
1. **仔细重新分析**屏幕截图
2. **反思之前的决策**为什么失败
3. **调整策略**（如更换点击位置、尝试不同的 UI 元素）
4. **生成纠正操作**

### 提高成功率的关键
- **精确定位**: 确保坐标在目标元素的中心区域
- **状态感知**: 考虑操作后屏幕应该发生什么变化
- **可验证性**: 你的操作应该产生明显的视觉变化
- **保守策略**: 如果不确定，选择更安全的操作方式

### 示例场景
**场景 1**: 点击搜索框
- 你的决策：CLICK at (520, 180)
- 期望结果：光标在搜索框闪烁
- Reflect 验证：状态 A（成功）✅

**场景 2**: 输入文字但未按回车
- 你的决策：TYPE text="PC-Agent paper"
- 实际结果：文字已输入，但没有执行搜索
- Reflect 验证：状态 D（未完成）⚠️
- 下次决策：KEY_PRESS key="enter"（纠正）

**场景 3**: 点错位置
- 你的决策：CLICK at (100, 200)
- 实际结果：屏幕无变化
- Reflect 验证：状态 C（无变化）⚠️
- 下次决策：重新定位正确的点击位置

## 6. 思维与决策框架
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
            completion = self.client.chat.completions.create(
                model='iic/GUI-Owl-7B',
                messages=messages
            )

            response_content = completion.choices[0].message.content.strip()
            print(f"{log_prefix} VLM 原始响应：{response_content}")

            # 解析 JSON 响应
            action_json = json.loads(response_content)

            print(f"{log_prefix} 解析成功的动作：{action_json}")

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
            print(f"{log_prefix} 调用失败：{e}")
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
