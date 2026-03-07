import sys
import os
import uuid
import time

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor,TimeoutError as FuturesTimeoutError

# 添加父目录（Agent）到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrators.decision_orchestrator import DecisionOrchestrator
from core.orchestrators.planning_orchestrators import TaskPlanner
from utils.screen_capture import ScreenCapturer
from utils.image_uploader import upload_to_picgo

load_dotenv()

# 创建线程池用于异步上传（最多 3 个并发任务）
upload_executor = ThreadPoolExecutor(max_workers=3)


app = Flask(__name__)
CORS(app)

# 初始化决策编排器
decision_orchestrator = DecisionOrchestrator()


@app.route('/api/execute', methods=['POST'])
def execute():
    """
    【核心接口】执行用户指令

    完整流程：规划 → 截图 → 决策 → 返回动作
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
                final_prompt = steps[0].get('instruction', prompt)
                print(f"→ 当前执行：{final_prompt}")
            else:
                print("⚠️  Planning 失败，使用原始指令")

        # ========== 步骤 2: 屏幕截图 ==========
        print("\n📸 [Capture] 正在截图...")
        capturer = ScreenCapturer()
        screenshot_path = capturer.capture()
        print(f"✓ 截图已保存：{screenshot_path}")

        # ========== 步骤 3: 转换为 base64（关键优化：不再上传到 PicGo）==========
        print("\n🔄 [Convert] 转换为 base64（无需网络传输）...")
        start_time = time.time()
        screenshot_base64 = capturer.capture_to_base64()
        convert_time = round(time.time() - start_time, 2)
        print(f"✓ Base64 长度：{len(screenshot_base64)} (耗时：{convert_time}s)")

        # ========== 步骤 4: VLM 决策（使用 base64 data URL，避免网络延迟）==========
        print("\n🧠 [Decision] 正在分析...")
        orchestrator = DecisionOrchestrator()

        # 构造 base64 data URL 格式（ModelScope 支持）
        image_data_url = f"data:image/png;base64,{screenshot_base64}"

        start_time = time.time()
        decision_result = orchestrator.decide(
            image_url=image_data_url,  # 使用 base64 格式，无需下载
            user_instruction=final_prompt
        )
        decision_time = round(time.time() - start_time, 2)

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
            'message': f'决策完成：{action}',
            'timing': {
                'convert_time': convert_time,
                'decision_time': decision_time,
                'total_time': round(convert_time + decision_time, 2)
            }
        }

        if use_planning and steps:
            response_data['steps'] = steps
            response_data['total_steps'] = len(steps)
            response_data['current_step'] = 1

        print(f"\n{'=' * 60}")
        print(f"[API] ✅ 执行完成")
        print(f"Thought: {thought[:100]}...")
        print(f"Action: {action}")
        print(f"总耗时：{round(convert_time + decision_time, 2)}s")
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
    【任务规划接口】将复杂指令分解为多个步骤，只在任务开始时调用一次！

    Request:
    {
        "instruction": "打开浏览器并打开一个视频网站",
        "show_thinking": false
    }

    Response:
    {
        "success": true,
        "steps": [
            {"step": 1, "instruction": "双击 Chrome", "expected_action": "CLICK"},
            {"step": 2, "instruction": "点击地址栏", "expected_action": "CLICK"},
            ...
        ],
        "total_steps": 4,
        "task_id": "task_xxx"
    }
    """
    try:
        data = request.get_json()

        if not data or 'instruction' not in data:
            return jsonify({'error': '缺少 instruction 参数'}), 400

        instruction = data['instruction']
        show_thinking = data.get('show_thinking', False)

        print(f"\n{'=' * 60}")
        print(f"[API] 📋 收到规划请求")
        print(f"指令：{instruction}")
        print(f"{'=' * 60}\n")

        planner = TaskPlanner(show_thinking=show_thinking)
        steps = planner.plan(instruction)

        if not steps:
            return jsonify({
                'success': False,
                'error': '任务分解失败',
                'steps': []
            }), 500

        # 生成任务 ID
        task_id = f"task_{uuid.uuid4().hex[:8]}"

        print(f"[API] ✓ 成功分解为 {len(steps)} 个步骤")
        print(f"[API] 任务 ID: {task_id}")

        return jsonify({
            'success': True,
            'steps': steps,
            'total_steps': len(steps),
            'task_id': task_id
        }), 200

    except Exception as e:
        error_msg = f"规划异常：{str(e)}"
        print(f"\n[API] ❌ {error_msg}")

        return jsonify({
            'success': False,
            'error': error_msg
        }), 500


@app.route('/api/decision', methods=['POST'])
def decision():
    """
    【单步决策接口】基于当前屏幕截图和指令，生成操作动作

    使用异步上传：截图后立即开始 VLM 决策，同时后台上传图片

    Request:
    {
        "prompt": "双击桌面上的 Chrome 浏览器图标",
        "task_id": "task_xxx",
        "step_no": 1
    }

    Response:
    {
        "success": true,
        "thought": "...",
        "action": "CLICK",
        "parameters": {"x": 100, "y": 200},
        "screenshot_url": "https://...",  # 图床 URL（可能还在上传中）
        "upload_status": "completed|pending|failed",  # 上传状态
        "step_no": 1,
        "task_id": "task_xxx"
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
        task_id = data.get('task_id', None)
        step_no = data.get('step_no', 1)

        log_prefix = f"[Task:{task_id}] Step:{step_no}" if task_id else f"Step:{step_no}"

        print(f"\n{'=' * 60}")
        print(f"[API] 📥 收到决策请求")
        print(f"{log_prefix} 指令：{prompt}")
        print(f"{'=' * 60}\n")

        # ========== 步骤 1: 屏幕截图 ==========
        print(f"{log_prefix} 📸 [Capture] 正在截图...")
        capturer = ScreenCapturer()
        screenshot_path = capturer.capture()
        print(f"✓ 截图已保存：{screenshot_path}")

        # ========== 步骤 2: 转换为 base64（用于 VLM 调用）==========
        print(f"{log_prefix} 🔄 [Convert] 转换为 base64...")
        start_time = time.time()
        screenshot_base64 = capturer.capture_to_base64()
        convert_time = round(time.time() - start_time, 2)
        print(f"✓ Base64 长度：{len(screenshot_base64)} (耗时：{convert_time}s)")

        # ========== 步骤 3: 异步上传到图床（不阻塞）==========
        print(f"{log_prefix} 🚀 [Upload] 启动异步上传...")
        upload_future = upload_executor.submit(upload_to_picgo, screenshot_path)

        # ========== 步骤 4: VLM 决策（使用 base64，立即开始）==========
        print(f"{log_prefix} 🧠 [Decision] 正在分析...")
        orchestrator = DecisionOrchestrator()

        image_data_url = f"data:image/png;base64,{screenshot_base64}"

        decision_start_time = time.time()
        decision_result = orchestrator.decide(
            image_url=image_data_url,
            user_instruction=prompt,
            step_no=step_no,
            task_id=task_id
        )
        decision_time = round(time.time() - decision_start_time, 2)

        if not decision_result['success']:
            return jsonify(decision_result), 500

        # ========== 步骤 5: 检查上传状态（非阻塞）==========
        screenshot_url = None
        upload_status = "pending"
        upload_time = 0

        try:
            # 尝试等待上传完成（最多等 0.1 秒）
            screenshot_url = upload_future.result(timeout=0.1)
            if screenshot_url:
                upload_status = "completed"
                upload_time = round(time.time() - decision_start_time, 2)
                print(f"{log_prefix} ✓ 上传完成：{screenshot_url}")
            else:
                upload_status = "failed"
                print(f"{log_prefix} ⚠️  上传失败")
        except FuturesTimeoutError:
            # 上传还没完成，但不等待了
            upload_status = "pending"
            print(f"{log_prefix} ⏳ 上传进行中（后台继续）")
        except Exception as e:
            upload_status = "failed"
            print(f"{log_prefix} ⚠️  上传异常：{e}")

        # ========== 步骤 6: 构建响应 ==========
        full_response = decision_result.get('full_response', {})
        thought = full_response.get('thought', '')
        action = full_response.get('action') or full_response.get('Action') or 'UNKNOWN'
        parameters = full_response.get('parameters') or full_response.get('Parameters') or {}

        if action == 'UNKNOWN':
            print(f"{log_prefix} ⚠️  警告：未找到 action 字段")

        response_data = {
            'success': True,
            'thought': thought,
            'action': action,
            'parameters': parameters,
            'full_response': full_response,
            'screenshot_path': screenshot_path,
            'screenshot_url': screenshot_url,
            'upload_status': upload_status,  # completed/pending/failed
            'step_no': step_no,
            'task_id': task_id,
            'timing': {
                'convert_time': convert_time,
                'decision_time': decision_time,
                'total_time': round(time.time() - start_time, 2)
            }
        }

        print(f"\n{'=' * 60}")
        print(f"[API] ✅ 决策完成")
        print(f"Thought: {thought[:100]}...")
        print(f"Action: {action}")
        if screenshot_url:
            print(f"截图 URL: {screenshot_url}")
        else:
            print(f"截图上传状态：{upload_status}（稍后可通过 screenshot_path 访问本地文件）")
        print(f"总耗时：{response_data['timing']['total_time']}s")
        print(f"{'=' * 60}\n")

        return jsonify(response_data), 200

    except Exception as e:
        error_msg = f"决策异常：{str(e)}"
        print(f"\n[API] ❌ {error_msg}")

        return jsonify({
            'success': False,
            'error': error_msg
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'service': 'GUI-Agent Decision API',
        'timestamp': time.time()
    }), 200

