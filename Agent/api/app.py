import sys
import os
import uuid
import time

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor,TimeoutError as FuturesTimeoutError
from utils.database import db

# 添加父目录（Agent）到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrators.decision_orchestrator import DecisionOrchestrator
from core.orchestrators.planning_orchestrators import TaskPlanner
from core.orchestrators.reflect_orchestrators import ReflectAgent
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
    废弃！！！！！【核心接口】执行用户指令

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

        task_db_record = None
        step_db_ids = []

        try:
            # 创建任务执行记录
            task_db_record = db.create_task(
                task_id=task_id,
                instruction=instruction,
                total_steps=len(steps)
            )
            print(f"[Database] ✓ 创建任务记录：{task_db_record['id']}")

            # 创建每个步骤的执行记录
            for step in steps:
                step_record = db.create_step(
                    task_db_id=task_db_record['id'],
                    step_no=step.get('step', 0),
                    instruction=step.get('instruction', ''),
                    expected_action=step.get('expected_action', '')
                )
                step_db_ids.append(step_record['id'])

            print(f"[Database] ✓ 创建 {len(steps)} 个步骤记录")

        except Exception as db_error:
            print(f"[Database] ⚠️  创建数据库记录失败：{str(db_error)}")
            # 数据库失败不影响主流程

        response_data = {
            'success': True,
            'steps': steps,
            'total_steps': len(steps),
            'task_id': task_id
        }

        # 如果有数据库记录，返回数据库 ID
        if task_db_record:
            response_data['task_db_id'] = task_db_record['id']

        return jsonify(response_data), 200

    except Exception as e:
        error_msg = f"规划异常：{str(e)}"
        print(f"\n[API] ❌ {error_msg}")

        # ========== 新增：记录错误到数据库 ==========
        try:
            db.log_error(
                error_level='ERROR',
                error_type='planning_exception',
                error_message=str(e),
                stack_trace=None,
                context={'instruction': instruction}
            )
        except Exception:
            pass  # 忽略数据库错误

        return jsonify({
            'success': False,
            'error': error_msg
        }), 500


@app.route('/api/decision', methods=['POST'])
def decision():
    """
    决策 + 自动执行 + 数据库记录

    完整流程：
    1. 初始化数据库记录（任务 + 步骤）
    2. 循环：截图 → 决策 → 执行 → Reflect 验证
    3. 每次尝试都记录到数据库
    4. 根据最终结果更新数据库状态
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
        auto_execute = data.get('auto_execute', True)
        safety_mode = data.get('safety_mode', False)
        max_retries = data.get('max_retries', 2)

        log_prefix = f"[Task:{task_id}] Step:{step_no}" if task_id else f"Step:{step_no}"

        print(f"\n{'=' * 60}")
        print(f"[API] 📥 收到决策请求")
        print(f"{log_prefix} 指令：{prompt}")
        print(f"{'=' * 60}\n")

        # ========== 步骤 A: 初始化数据库记录 ==========
        task_db_id = None
        step_db_id = None
        decision_db_id = None

        try:
            if task_id:
                # 1. 查找或创建任务记录
                task_record = db.get_task_by_id(task_id)

                if not task_record:
                    # 任务不存在，创建新任务
                    task_record = db.create_task(
                        task_id=task_id,
                        instruction=prompt,
                        total_steps=1
                    )
                    print(f"[Database] ✓ 创建新任务记录：{task_record['id']}")
                else:
                    print(f"[Database] ℹ️  使用已有任务记录：{task_record['id']}")

                task_db_id = task_record['id']

                # 2. 查找或创建步骤记录
                from supabase import create_client
                supabase_client = create_client(
                    os.getenv('SUPABASE_URL'),
                    os.getenv('SUPABASE_KEY')
                )

                result = supabase_client.table('step_executions').select('*') \
                    .eq('task_id', task_db_id) \
                    .eq('step_no', step_no) \
                    .execute()

                if result.data and len(result.data) > 0:
                    # 步骤已存在
                    step_db_id = result.data[0]['id']
                    print(f"[Database] ℹ️  使用已有步骤记录：{step_db_id}")

                    # 更新步骤状态为 running
                    db.update_step_status(step_db_id=step_db_id, status='running')
                else:
                    # 创建新步骤
                    step_record = db.create_step(
                        task_db_id=task_db_id,
                        step_no=step_no,
                        instruction=prompt,
                        expected_action=None
                    )
                    step_db_id = step_record['id']
                    print(f"[Database] ✓ 创建步骤记录：{step_db_id}")

        except Exception as db_error:
            print(f"[Database] ⚠️  数据库初始化失败：{str(db_error)}")
            # 数据库失败不影响主流程

        # ========== 步骤 B: 初始化执行状态 ==========
        retry_count = 0
        retry_history = []
        last_error_reason = ""
        final_decision_result = None
        final_execution_result = None
        final_reflect_result = None
        final_screenshot_path = None
        final_screenshot_url = None
        final_upload_status = "pending"
        final_convert_time = 0
        final_decision_time = 0

        start_time = time.time()

        # ========== 步骤 C: 主循环（决策 → 执行 → 验证 → 重试）==========
        while retry_count <= max_retries:
            attempt_num = retry_count + 1
            print(f"\n{'=' * 60}")
            print(f"{log_prefix} 🔄 第 {attempt_num} 次尝试 (重试计数：{retry_count}/{max_retries})")
            print(f"{'=' * 60}\n")

            # 1. 屏幕截图（执行前）
            print(f"{log_prefix} 📸 [Capture] 正在截图（执行前）...")
            capturer = ScreenCapturer()
            screenshot_path = capturer.capture()
            before_screenshot_base64 = capturer.capture_to_base64()
            print(f"✓ 截图已保存：{screenshot_path}")

            # 2. 转换为 base64
            print(f"{log_prefix} 🔄 [Convert] 转换为 base64...")
            convert_start = time.time()
            convert_time = round(time.time() - convert_start, 2)
            print(f"✓ Base64 长度：{len(before_screenshot_base64)} (耗时：{convert_time}s)")

            # 3. 异步上传
            print(f"{log_prefix} 🚀 [Upload] 启动异步上传...")
            upload_future = upload_executor.submit(upload_to_picgo, screenshot_path)

            # 4. VLM 决策
            print(f"{log_prefix} 🧠 [Decision] 正在分析...")
            orchestrator = DecisionOrchestrator()

            image_data_url = f"data:image/png;base64,{before_screenshot_base64}"

            # 如果是重试且有过 Reflect 反馈
            if retry_count > 0 and final_reflect_result:
                retry_prompt = f"""{prompt}

【重要反馈】上一步操作未能完全达成目标。
验证状态：{final_reflect_result.get('status', '未知')}
检测到的变化：{final_reflect_result.get('changes', [])}
分析：{final_reflect_result.get('analysis', '')[:200]}
建议：{final_reflect_result.get('suggestion', '')}

请根据上述反馈重新分析屏幕并生成纠正操作。"""

                user_instruction_for_vlm = retry_prompt
            else:
                user_instruction_for_vlm = prompt

            decision_start = time.time()
            decision_result = orchestrator.decide(
                image_url=image_data_url,
                user_instruction=user_instruction_for_vlm,
                step_no=step_no,
                task_id=task_id
            )
            decision_time = round(time.time() - decision_start, 2)

            if not decision_result['success']:
                print(f"{log_prefix} ❌ VLM 决策失败")
                retry_count += 1
                last_error_reason = decision_result.get('error', '未知错误')

                retry_history.append({
                    'attempt': attempt_num,
                    'stage': 'decision',
                    'error': last_error_reason
                })

                # 记录失败的决策到数据库
                if step_db_id:
                    try:
                        decision_record = db.create_decision(
                            step_db_id=step_db_id,
                            attempt_no=attempt_num,
                            thought=None,
                            action_type=None,
                            parameters=None,
                            full_response=None
                        )
                        decision_db_id = decision_record['id']
                        print(f"[Database] ✓ 创建决策记录（失败）")
                    except Exception as db_err:
                        print(f"[Database] ⚠️  记录决策失败：{str(db_err)}")

                if retry_count <= max_retries:
                    print(f"{log_prefix} ⏳ 等待 1 秒后重试...")
                    time.sleep(1)
                continue

            final_decision_result = decision_result

            # 5. 自动执行
            execution_result = None

            if auto_execute:
                print(f"\n{log_prefix} ⚙️  [Execute] 准备自动执行...")

                full_response = decision_result.get('full_response', {})
                action = (full_response.get('action') or
                          full_response.get('Action') or
                          '').strip().upper()
                parameters = full_response.get('parameters') or full_response.get('Parameters') or {}
                description = full_response.get('description', '')

                if action and action not in ['FINISH', 'FAILE', 'FAIL']:
                    action_data = {
                        'action': action,
                        'parameters': parameters,
                        'description': description
                    }

                    print(f"{log_prefix} 📍 执行动作：{action}")
                    print(f"{log_prefix} 参数：{parameters}")

                    from core.action_module import ActionModule
                    executor = ActionModule(safety_mode=safety_mode)
                    execution_result = executor.execute(action_data)

                    if execution_result.get('success'):
                        print(f"{log_prefix} ✅ 执行成功：{execution_result.get('message')}")

                        # 6. 再次截图（执行后）
                        print(f"{log_prefix} 📸 [Capture] 正在截图（执行后）...")
                        after_screenshot_base64 = capturer.capture_to_base64()

                        # 7. Reflect 验证
                        print(f"{log_prefix} 🔍 [Reflect] 正在验证操作结果...")
                        reflect_agent = ReflectAgent()

                        reflect_result = reflect_agent.verify(
                            before_base64=before_screenshot_base64,
                            after_base64=after_screenshot_base64,
                            action=action,
                            parameters=parameters,
                            step_instruction=prompt,
                            context={
                                'attempt': attempt_num,
                                'history': retry_history
                            }
                        )

                        final_reflect_result = reflect_result

                        print(f"\n{log_prefix} 🔍 Reflect 验证结果:")
                        print(f"  状态：{reflect_result['status']}")
                        print(f"  成功：{reflect_result['success']}")
                        print(f"  错误标志：{reflect_result['error_flag']}")
                        print(f"  置信度：{reflect_result['confidence']:.2f}")
                        print(f"  变化：{reflect_result['changes'][:3] if reflect_result['changes'] else []}")
                        print(f"  分析：{reflect_result['analysis'][:100]}...")
                        if reflect_result['suggestion']:
                            print(f"  建议：{reflect_result['suggestion'][:100]}...")

                        # 基于 Reflect 结果做决策
                        if reflect_result['status'] == 'A':
                            print(f"\n{log_prefix} ✅ Reflect 验证通过，操作成功")
                            final_execution_result = execution_result

                            # ========== 记录成功的决策和验证到数据库 ==========
                            if step_db_id:
                                try:
                                    # 创建决策记录
                                    decision_record = db.create_decision(
                                        step_db_id=step_db_id,
                                        attempt_no=attempt_num,
                                        thought=full_response.get('thought', ''),
                                        action_type=action,
                                        parameters=parameters,
                                        full_response=full_response
                                    )
                                    decision_db_id = decision_record['id']

                                    # 更新决策执行结果
                                    db.update_decision_result(
                                        decision_db_id=decision_db_id,
                                        execution_success=True,
                                        execution_message=execution_result.get('message'),
                                        decision_time_ms=int(decision_time * 1000),
                                        screenshot_url=final_screenshot_url
                                    )

                                    # 创建 Reflect 验证记录
                                    db.create_verification(
                                        decision_db_id=decision_db_id,
                                        status=reflect_result['status'],
                                        success=reflect_result['success'],
                                        error_flag=reflect_result['error_flag'],
                                        confidence=reflect_result['confidence'],
                                        changes_detected=reflect_result['changes'],
                                        analysis=reflect_result['analysis'],
                                        suggestion=reflect_result['suggestion'],
                                        diagnosis=reflect_result.get('diagnosis'),
                                        retry_recommendation=reflect_result.get('retry_recommendation')
                                    )

                                    print(f"[Database] ✓ 记录决策和验证结果")

                                    # 更新步骤状态为成功
                                    db.update_step_status(
                                        step_db_id=step_db_id,
                                        status='success',
                                        retry_count=retry_count
                                    )

                                except Exception as db_err:
                                    print(f"[Database] ⚠️  记录结果失败：{str(db_err)}")

                            break  # 成功，退出循环

                        elif reflect_result['status'] == 'B':
                            print(f"\n{log_prefix} ❌ 进入错误状态：{reflect_result['analysis']}")
                            retry_count += 1
                            last_error_reason = f"错误状态：{reflect_result['analysis']}"

                        elif reflect_result['status'] == 'C':
                            print(f"\n{log_prefix} ⚠️ 屏幕无变化，可能操作未生效")
                            retry_count += 1
                            last_error_reason = f"屏幕无变化：{reflect_result['analysis']}"

                        elif reflect_result['status'] == 'D':
                            print(f"\n{log_prefix} ⚠️ 操作完成但目标未达成：{reflect_result['suggestion']}")
                            retry_count += 1
                            last_error_reason = f"未完成：{reflect_result['suggestion']}"

                        elif reflect_result['status'] == 'E':
                            print(f"\n{log_prefix} ✅ 部分成功，可以继续：{reflect_result['analysis']}")
                            final_execution_result = execution_result

                            # 记录部分成功的结果
                            if step_db_id and decision_db_id is None:
                                try:
                                    decision_record = db.create_decision(
                                        step_db_id=step_db_id,
                                        attempt_no=attempt_num,
                                        thought=full_response.get('thought', ''),
                                        action_type=action,
                                        parameters=parameters,
                                        full_response=full_response
                                    )
                                    decision_db_id = decision_record['id']

                                    db.create_verification(
                                        decision_db_id=decision_db_id,
                                        status=reflect_result['status'],
                                        success=reflect_result['success'],
                                        error_flag=reflect_result['error_flag'],
                                        confidence=reflect_result['confidence'],
                                        changes_detected=reflect_result['changes'],
                                        analysis=reflect_result['analysis'],
                                        suggestion=reflect_result['suggestion']
                                    )

                                    db.update_step_status(
                                        step_db_id=step_db_id,
                                        status='success',
                                        retry_count=retry_count
                                    )

                                except Exception as db_err:
                                    print(f"[Database] ⚠️  记录部分成功结果失败：{str(db_err)}")

                            break  # 部分成功，退出循环

                        retry_history.append({
                            'attempt': attempt_num,
                            'stage': 'reflect',
                            'reflect_status': reflect_result['status'],
                            'error': last_error_reason
                        })

                        if retry_count <= max_retries:
                            print(f"{log_prefix} ⏳ 等待 2 秒后重试...")
                            time.sleep(2)

                    else:
                        print(f"{log_prefix} ❌ 执行失败：{execution_result.get('message')}")
                        retry_count += 1
                        last_error_reason = execution_result.get('message', '未知错误')

                        retry_history.append({
                            'attempt': attempt_num,
                            'stage': 'execution',
                            'error': last_error_reason
                        })

                        if retry_count <= max_retries:
                            print(f"{log_prefix} ⏳ 等待 2 秒后重试...")
                            time.sleep(2)
                else:
                    print(f"{log_prefix} ⚠️  无需执行或特殊动作：{action}")
                    execution_result = {
                        'success': True,
                        'message': f'动作类型：{action}，无需执行',
                        'action': action
                    }
                    final_execution_result = execution_result
                    after_screenshot_base64 = capturer.capture_to_base64()
                    break
            else:
                print(f"{log_prefix} ℹ️  跳过自动执行（auto_execute=false）")
                execution_result = {'success': True, 'message': '未执行'}
                final_execution_result = execution_result
                after_screenshot_base64 = capturer.capture_to_base64()
                break

            # 检查上传状态
            screenshot_url = None
            upload_status = "pending"

            try:
                screenshot_url = upload_future.result(timeout=0.1)
                if screenshot_url:
                    upload_status = "completed"
                    print(f"{log_prefix} ✓ 上传完成：{screenshot_url}")
                else:
                    upload_status = "failed"
            except FuturesTimeoutError:
                upload_status = "pending"
                print(f"{log_prefix} ⏳ 上传进行中")
            except Exception as e:
                upload_status = "failed"
                print(f"{log_prefix} ⚠️  上传异常：{e}")

            final_screenshot_path = screenshot_path
            final_screenshot_url = screenshot_url
            final_upload_status = upload_status
            final_convert_time = convert_time
            final_decision_time = decision_time

        # ========== 步骤 D: 处理最终状态 ==========
        final_success = (retry_count <= max_retries) and \
                        (final_execution_result.get('success') if final_execution_result else False) and \
                        (final_reflect_result.get('success', False) if final_reflect_result else True)

        # 更新数据库中的步骤状态
        if step_db_id:
            try:
                if final_success:
                    db.update_step_status(
                        step_db_id=step_db_id,
                        status='success',
                        retry_count=retry_count
                    )
                else:
                    db.update_step_status(
                        step_db_id=step_db_id,
                        status='failed',
                        retry_count=retry_count
                    )
            except Exception as db_err:
                print(f"[Database] ⚠️  更新步骤状态失败：{str(db_err)}")

        # ========== 步骤 E: 构建最终响应 ==========
        full_response = final_decision_result.get('full_response', {}) if final_decision_result else {}
        thought = full_response.get('thought', '') if full_response else ''
        action = (full_response.get('action') or
                  full_response.get('Action') or
                  'UNKNOWN') if full_response else 'UNKNOWN'
        parameters = (full_response.get('parameters') or
                      full_response.get('Parameters') or
                      {}) if full_response else {}

        if action == 'UNKNOWN' and final_decision_result:
            print(f"{log_prefix} ⚠️  警告：未找到 action 字段")

        response_data = {
            'success': final_success,
            'thought': thought,
            'action': action,
            'parameters': parameters,
            'full_response': full_response,
            'screenshot_path': final_screenshot_path,
            'screenshot_url': final_screenshot_url,
            'upload_status': final_upload_status,
            'step_no': step_no,
            'task_id': task_id,
            'execution_result': final_execution_result,
            'reflect_result': final_reflect_result,
            'retry_count': retry_count,
            'retry_history': retry_history,
            'final_attempt': retry_count + 1,
            'timing': {
                'convert_time': final_convert_time,
                'decision_time': final_decision_time,
                'total_time': round(time.time() - start_time, 2)
            }
        }

        # 添加数据库 ID 信息
        if task_db_id:
            response_data['task_db_id'] = task_db_id
        if step_db_id:
            response_data['step_db_id'] = step_db_id
        if decision_db_id:
            response_data['decision_db_id'] = decision_db_id

        print(f"\n{'=' * 60}")
        if final_success:
            print(f"[API] ✅ 决策 + 执行 + 验证成功（尝试 {retry_count + 1} 次）")
        else:
            print(f"[API] ❌ 决策 + 执行 + 验证失败（已重试 {max_retries} 次）")
        print(f"Thought: {thought[:100]}...")
        print(f"Action: {action}")
        if final_execution_result:
            exec_msg = final_execution_result.get('message', '')
            print(f"执行结果：{exec_msg[:100] if exec_msg else 'N/A'}...")
        if final_reflect_result:
            print(f"Reflect 状态：{final_reflect_result.get('status', '未知')}")
            print(f"Reflect 分析：{final_reflect_result.get('analysis', '')[:100]}...")
        if final_screenshot_url:
            print(f"截图 URL: {final_screenshot_url}")
        print(f"总耗时：{response_data['timing']['total_time']}s")
        print(f"{'=' * 60}\n")

        return jsonify(response_data), 200

    except Exception as e:
        error_msg = f"决策异常：{str(e)}"
        print(f"\n[API] ❌ {error_msg}")

        # 记录错误到数据库
        try:
            db.log_error(
                error_level='ERROR',
                error_type='decision_exception',
                error_message=str(e),
                stack_trace=None,
                context={
                    'task_id': task_id,
                    'step_no': step_no,
                    'prompt': prompt
                }
            )
        except Exception:
            pass

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

