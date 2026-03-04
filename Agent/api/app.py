import sys
import os

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import time

# 添加父目录（Agent）到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrators.decision_orchestrator import DecisionOrchestrator
from core.orchestrators.planning_orchestrators import TaskPlanner
from utils.screen_capture import ScreenCapturer
from utils.image_uploader import upload_to_picgo

load_dotenv()

app = Flask(__name__)
CORS(app)

# 初始化决策编排器
decision_orchestrator = DecisionOrchestrator()


@app.route('/api/execute', methods=['POST'])
def execute():
    """
    【核心接口】执行用户指令

    完整流程：规划 → 截图 → 决策 → 返回动作

    Request:
    {
        "prompt": "打开浏览器",           # 用户输入的指令
        "use_planning": true,            # 是否启用 Planning 优化（可选，默认 false）
        "show_thinking": false           # 是否显示思考过程（可选，默认 false）
    }

    Response:
    {
        "success": true,
        "thought": "用户想打开浏览器...",
        "action": "CLICK",
        "parameters": {"x": 100, "y": 200},
        "steps": [...],                  # 如果启用了 planning，返回分解的步骤
        "screenshot_path": "...",
        "message": "执行成功"
    }
    """
    try:
        data = request.get_json()

        if not data or 'prompt' not in data:
            return jsonify({
                'success': False,
                'error': '缺少必要参数：prompt'
            }), 400

        prompt = data['prompt']
        use_planning = data.get('use_planning', False)
        show_thinking = data.get('show_thinking', False)

        print(f"\n{'=' * 60}")
        print(f"[API] 📥 收到执行请求")
        print(f"指令：{prompt}")
        print(f"Planning: {'开启' if use_planning else '关闭'}")
        print(f"{'=' * 60}\n")

        # ========== 步骤 1: Planning（可选）==========
        steps = []
        final_prompt = prompt

        if use_planning:
            print("🧠 [Planning] 开始任务分解...")
            planner = TaskPlanner(show_thinking=show_thinking)
            steps = planner.plan_simple(prompt)

            if steps and len(steps) > 0:
                print(f"✓ 成功分解为 {len(steps)} 个步骤")
                # 取第一个步骤作为当前要执行的指令
                final_prompt = steps[0].get('instruction', prompt)
                print(f"→ 当前执行：{final_prompt}")
            else:
                print("⚠️  Planning 失败，使用原始指令")

        # ========== 步骤 2: 屏幕截图 ==========
        print("\n📸 [Capture] 正在截图...")
        capturer = ScreenCapturer()
        screenshot_path = capturer.capture()
        print(f"✓ 截图已保存：{screenshot_path}")

        # ========== 步骤 3: 上传图片 ==========
        print("\n📤 [Upload] 正在上传到图床...")
        image_url = upload_to_picgo(screenshot_path)

        if not image_url:
            return jsonify({
                'success': False,
                'error': '图片上传失败',
                'screenshot_path': screenshot_path
            }), 500

        print(f"✓ 上传成功：{image_url}")

        # ========== 步骤 4: VLM 决策 ==========
        print("\n🧠 [Decision] 正在分析...")
        orchestrator = DecisionOrchestrator()
        decision_result = orchestrator.decide(
            image_url=image_url,
            user_instruction=final_prompt
        )

        if not decision_result['success']:
            return jsonify(decision_result), 500

        # ========== 步骤 5: 构建响应 ==========
        full_response = decision_result.get('full_response', {})
        thought = full_response.get('thought', '')
        action = full_response.get('action')
        parameters = full_response.get('parameters')

        response_data = {
            'success': True,
            'thought': thought,
            'action': action,
            'parameters': parameters,
            'full_response': full_response,
            'screenshot_path': screenshot_path,
            'message': f'决策完成：{action}'
        }

        # 如果启用了 planning，返回步骤信息
        if use_planning and steps:
            response_data['steps'] = steps
            response_data['total_steps'] = len(steps)
            response_data['current_step'] = 1

        print(f"\n{'=' * 60}")
        print(f"[API] ✅ 执行完成")
        print(f"Thought: {thought[:100]}...")
        print(f"Action: {action}")
        print(f"{'=' * 60}\n")

        return jsonify(response_data), 200

    except Exception as e:
        error_msg = f"执行异常：{str(e)}"
        print(f"\n[API] ❌ {error_msg}")

        return jsonify({
            'success': False,
            'error': error_msg
        }), 500


@app.route('/api/plan', methods=['POST'])
def plan_task():
    """
    任务规划接口：将复杂指令分解为多个步骤

    Request:
    {
        "instruction": "打开浏览器，搜索 AI，下载图片"
    }

    Response:
    {
        "success": true,
        "steps": [
            {"step": 1, "instruction": "...", "expected_action": "CLICK"},
            ...
        ],
        "total_steps": 6
    }
    """
    try:
        data = request.get_json()

        if not data or 'instruction' not in data:
            return jsonify({'error': '缺少 instruction 参数'}), 400

        instruction = data['instruction']

        print(f"\n[API] 收到规划请求：{instruction}")

        planner = TaskPlanner(show_thinking=False)
        steps = planner.plan(instruction)

        if not steps:
            return jsonify({
                'success': False,
                'error': '任务分解失败',
                'steps': []
            }), 500

        print(f"[API] ✓ 成功分解为 {len(steps)} 个步骤")

        return jsonify({
            'success': True,
            'steps': steps,
            'total_steps': len(steps)
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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

