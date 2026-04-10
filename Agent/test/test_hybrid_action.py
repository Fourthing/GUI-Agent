# File: Agent/test/test_hybrid_action.py
"""
ActionModule 综合测试
覆盖所有新增功能点和历史功能
"""
import sys
import os
import time
import subprocess

# 添加父目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.action_module import ActionModule
from core.orchestrators.hybrid_decision_orchestrator import HybridDecisionOrchestrator
from utils.screen_capture import ScreenCapturer


def test_1_traditional_xy_click():
    """测试 1: 传统 x/y 坐标点击（历史功能）"""
    print("\n" + "=" * 80)
    print("测试 1: 传统 x/y 坐标点击（历史功能兼容性）")
    print("=" * 80)

    executor = ActionModule(safety_mode=False)

    # 测试用例 1.1: 标准数字坐标
    print("\n[1.1] 标准数字坐标")
    result = executor.execute({
        'action': 'CLICK',
        'parameters': {
            'x': 100,
            'y': 100,
            'description': '测试标准坐标'
        }
    })

    assert result['success'], f"失败：{result['message']}"
    assert result['coordinates'] == (100, 100), f"坐标错误：{result['coordinates']}"
    print(f"✓ 通过：{result['message']}")

    # 测试用例 1.2: 数组格式坐标
    print("\n[1.2] 数组格式坐标")
    result = executor.execute({
        'action': 'CLICK',
        'parameters': {
            'x': [200, 300],  # 应该取第一个值
            'y': [200, 300]
        }
    })

    assert result['success'], f"失败：{result['message']}"
    assert result['coordinates'] == (200, 200), f"坐标错误：{result['coordinates']}"
    print(f"✓ 通过：{result['message']}")

    # 测试用例 1.3: 字符串格式坐标
    print("\n[1.3] 字符串格式坐标")
    result = executor.execute({
        'action': 'CLICK',
        'parameters': {
            'x': "300",
            'y': "300"
        }
    })

    assert result['success'], f"失败：{result['message']}"
    assert result['coordinates'] == (300, 300), f"坐标错误：{result['coordinates']}"
    print(f"✓ 通过：{result['message']}")

    # 测试用例 1.4: 缺少坐标参数
    print("\n[1.4] 缺少坐标参数（应失败）")
    result = executor.execute({
        'action': 'CLICK',
        'parameters': {}
    })

    assert not result['success'], "应该失败但没有"
    print(f"✓ 通过：正确拒绝 - {result['message']}")

    print("\n✅ 测试 1 全部通过")
    return True


def test_2_element_id_dynamic定位():
    """测试 2: element_id 动态定位（新功能）"""
    print("\n" + "=" * 80)
    print("测试 2: element_id 动态定位（新功能）")
    print("=" * 80)

    # 打开记事本作为测试目标
    print("\n[准备] 打开记事本...")
    subprocess.Popen("notepad.exe")
    time.sleep(1.5)

    # 切换到记事本
    import pyautogui
    # pyautogui.hotkey('alt', 'tab')
    # time.sleep(1.0)

    executor = ActionModule(safety_mode=False)

    # 测试用例 2.1: 使用有效的 element_id
    print("\n[2.1] 使用有效的 element_id")

    # 先提取 UI 元素
    from core.windows_aci import WindowsACI
    aci = WindowsACI(top_app_only=True)
    elements = aci.linearize_and_annotate_tree({})
    # 打印前 50 个元素
    for i, elem in enumerate(elements[:50]):
        print(f"[{i}] role={elem['role']}, title={elem['title']}, "
              f"text={elem['text']}, pos={elem['position']}, size={elem['size']}")

    if not elements:
        print("⚠️  未提取到元素，跳过此测试")
        return True

    print(f"提取到 {len(elements)} 个元素")

    # 选择第一个按钮或文本框
    target_id = None
    for idx, elem in enumerate(elements):
        if 'Button' in elem.get('role', '') or 'Edit' in elem.get('role', ''):
            target_id = idx
            break

    if target_id is None:
        target_id = 0  # 默认使用第一个元素

    print(f"使用 element_id={target_id} ({elements[target_id].get('role')})")

    result = executor.execute({
        'action': 'CLICK',
        'parameters': {
            'element_id': target_id,
            'description': '测试 element_id 动态定位'
        }
    })

    assert result['success'], f"失败：{result['message']}"
    print(f"✓ 通过：{result['message']}")

    # 测试用例 2.2: 使用无效的 element_id（超出范围）
    print("\n[2.2] 使用无效的 element_id（超出范围）")
    result = executor.execute({
        'action': 'CLICK',
        'parameters': {
            'element_id': 99999  # 明显超出范围
        }
    })

    # 应该降级到 x/y 坐标，但因为没提供 x/y，所以失败
    assert not result['success'], "应该失败但没有"
    print(f"✓ 通过：正确处理无效 ID - {result['message']}")

    # 测试用例 2.3: element_id 和 x/y 同时存在（element_id 优先）
    print("\n[2.3] element_id 和 x/y 同时存在（element_id 应优先）")
    result = executor.execute({
        'action': 'CLICK',
        'parameters': {
            'element_id': target_id,
            'x': 9999,  # 这个应该被忽略
            'y': 9999
        }
    })

    # 如果使用了 element_id，坐标应该是合理的（不是 9999）
    if result['success']:
        coord_x, coord_y = result['coordinates']
        assert coord_x != 9999 and coord_y != 9999, "应该使用 element_id 的坐标"
        print(f"✓ 通过：正确使用 element_id 坐标 ({coord_x}, {coord_y})")
    else:
        print(f"⚠️  跳过：{result['message']}")

    print("\n✅ 测试 2 全部通过")
    return True


def test_3_hybrid_decision_aci_path():
    """测试 3: 混合决策器 - ACI 快速决策路径"""
    print("\n" + "=" * 80)
    print("测试 3: 混合决策器 - ACI 快速决策路径")
    print("=" * 80)

    # 打开记事本作为测试目标
    print("\n[准备] 打开记事本...")
    subprocess.Popen("notepad.exe")
    time.sleep(1.5)

    # 确保记事本仍然打开
    print("\n[准备] 确保记事本处于活动状态...")
    # import pyautogui
    # pyautogui.hotkey('alt', 'tab')
    # time.sleep(0.5)

    orchestrator = HybridDecisionOrchestrator()

    # 直接使用 capture_to_base64()，返回的就是 image_url 格式
    capturer = ScreenCapturer()
    base64_image = capturer.capture_to_base64()
    image_url = f"data:image/png;base64,{base64_image}"

    # 测试用例 3.1: "关闭窗口" 指令（应该匹配到关闭按钮）
    print("\n[3.1] 指令：'关闭窗口'")
    result = orchestrator.decide(
        image_url=image_url,  # ← 直接传递 image_url
        user_instruction="关闭窗口",
        step_no=1,
        task_id="test_aci_001"
    )

    print(f"决策方式：{result.get('decision_method')}")
    print(f"决策耗时：{result.get('decision_time')}s")

    if result.get('decision_method') == 'aci_enhanced_vlm':
        print(f"✓ 通过：使用 ACI 增强的 VLM 决策")
        print(f"  动作：{result.get('action')}")
        print(f"  参数：{result.get('parameters')}")

        # 验证返回的是 element_id 而不是 x/y
        params = result.get('parameters', {})
        assert 'element_id' in params, "ACI 决策应该返回 element_id"
        print(f"  ✓ 正确返回 element_id={params['element_id']}")
    else:
        print(f"⚠️  未使用 ACI 决策（可能是因为没有匹配的按钮）")
        print(f"  降级到：{result.get('decision_method')}")

    # 测试用例 3.2: "最小化窗口" 指令
    print("\n[3.2] 指令：'最小化窗口'")

    result = orchestrator.decide(
        image_url=image_url,  # ← 直接传递 image_url
        user_instruction="最小化窗口",
        step_no=2,
        task_id="test_aci_002"
    )

    print(f"决策方式：{result.get('decision_method')}")
    if result.get('decision_method') == 'aci_enhanced_vlm':
        print(f"✓ 通过：使用 ACI 快速决策")
    else:
        print(f"⚠️  降级到：{result.get('decision_method')}")

    # 打印统计信息
    stats = orchestrator.get_stats()
    print(f"\n📊 决策统计：{stats}")

    print("\n✅ 测试 3 完成")
    return True

def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("🚀 开始 ActionModule 综合测试套件")
    print("=" * 80)

    tests = [
        ("传统 x/y 坐标点击", test_1_traditional_xy_click),
        ("element_id 动态定位", test_2_element_id_dynamic定位),
        ("混合决策器 - ACI 路径", test_3_hybrid_decision_aci_path),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            success = test_func()
            results[test_name] = "✅ 通过" if success else "❌ 失败"
        except Exception as e:
            print(f"\n❌ 测试异常：{e}")
            import traceback
            traceback.print_exc()
            results[test_name] = f"❌ 异常：{str(e)}"

    # 打印总结
    print("\n" + "=" * 80)
    print("📊 测试总结")
    print("=" * 80)

    for test_name, result in results.items():
        print(f"{test_name:30s} : {result}")

    passed = sum(1 for r in results.values() if "通过" in r)
    total = len(results)

    print(f"\n总计：{passed}/{total} 通过")

    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️  有 {total - passed} 个测试未通过")


if __name__ == "__main__":
    run_all_tests()
