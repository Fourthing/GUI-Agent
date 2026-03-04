from openai import OpenAI
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import json

# 加载环境变量
load_dotenv()

app = Flask(__name__)

# 初始化 OpenAI 客户端
client = OpenAI(
    base_url='https://api-inference.modelscope.cn/v1',
    api_key=os.getenv('MODELSCOPE_TOKEN', 'ms-086b0baa-9eff-4184-b58d-266d717d7359'),
)


def call_vlm(image_url: str, user_text: str) -> dict:
    """
    调用 VLM 模型进行决策

    Args:
        image_url: 图片 URL
        user_text: 用户指令

    Returns:
        包含 thought 的字典
    """
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

## 4. 思维与决策框架
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
                    "text": user_text
                }
            ]
        }
    ]

    try:
        completion = client.chat.completions.create(
            model='iic/GUI-Owl-7B',
            messages=messages
        )

        response_content = completion.choices[0].message.content.strip()

        # 解析 JSON 响应
        action_json = json.loads(response_content)

        return {
            'success': True,
            'thought': action_json.get('thought', ''),
            'full_response': action_json
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'thought': ''
        }


@app.route('/api/decision', methods=['POST'])
def decision_api():
    """
    决策接口：接收 image_url 和 user_text，返回 VLM 的 thought

    Request Body (JSON):
        {
            "image_url": "https://example.com/image.png",
            "user_text": "点击搜索按钮",
            "step_no": 1,              # 步骤编号（可选，默认 1）
            "task_id": "task_001"      # 任务 ID（可选）
        }

    Response (JSON):
        {
            "success": true,
            "step_no": 1,
            "task_id": "task_001",
            "thought": "用户想点击搜索按钮...",
            "full_response": {...},
            "is_final_step": false
        }
    """
    data = request.get_json()

    if not data:
        return jsonify({
            'success': False,
            'error': '请求体不能为空'
        }), 400

    image_url = data.get('image_url')
    user_text = data.get('user_text')
    step_no = data.get('step_no', 1)
    task_id = data.get('task_id', None)

    if not image_url or not user_text:
        return jsonify({
            'success': False,
            'error': '缺少必要参数：image_url 和 user_text'
        }), 400

    log_prefix = f"[Task:{task_id}] Step:{step_no}" if task_id else f"Step:{step_no}"
    print(f"[API] {log_prefix} - 指令：{user_text}")

    result = call_vlm(image_url, user_text)

    if result['success']:
        response_data = {
            'success': True,
            'step_no': step_no,
            'task_id': task_id,
            'thought': result['thought'],
            'full_response': result['full_response'],
            'is_final_step': result['full_response'].get('action') in ['FINISH', 'FAILE', 'FAIL']
        }

        print(f"[API] ✓ {log_prefix} - 决策成功")
        return jsonify(response_data), 200
    else:
        error_response = {
            'success': False,
            'step_no': step_no,
            'task_id': task_id,
            'error': result['error'],
            'thought': ''
        }
        print(f"[API] ✗ {log_prefix} - 决策失败：{result['error']}")
        return jsonify(error_response), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'service': 'GUI-Agent Decision API'
    }), 200


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 GUI-Agent Decision API 启动")
    print("=" * 60)
    print("接口地址：http://localhost:5000/api/decision")
    print("请求方法：POST")
    print("请求参数：image_url, user_text")
    print("=" * 60)

    app.run(host='0.0.0.0', port=5000, debug=True)
