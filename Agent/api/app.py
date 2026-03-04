import sys
import os

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import time

# 添加父目录（Agent）到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.orchestrators.decision_orchestrator import DecisionOrchestrator
from utils.image_uploader import get_image_url

load_dotenv()

app = Flask(__name__)
CORS(app)

# 初始化决策编排器
decision_orchestrator = DecisionOrchestrator()


@app.route('/api/decision', methods=['POST'])
def decision_api():
    """
    决策接口：接收 image_url 和 user_text，返回 VLM 的 thought

    Request Body (JSON):
        {
            "image_url": "https://example.com/image.png",
            "user_text": "点击搜索按钮",
            "step_no": 1,
            "task_id": "task_001"
        }

    Response (JSON):
        {
            "success": true,
            "step_no": 1,
            "task_id": "task_001",
            "thought": "用户想点击搜索按钮...",
            "action": "CLICK",
            "parameters": {...},
            "full_response": {...}
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
    print(f"\n[API] {log_prefix} - 收到请求 - 指令：{user_text}")

    result = decision_orchestrator.decide(image_url, user_text, step_no, task_id)

    if result['success']:
        print(f"[API] ✓ {log_prefix} - 决策成功 - Thought: {result['thought'][:100]}...")
        return jsonify(result), 200
    else:
        print(f"[API] ✗ {log_prefix} - 决策失败：{result['error']}")
        return jsonify(result), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'service': 'GUI-Agent Decision API',
        'timestamp': time.time()
    }), 200

