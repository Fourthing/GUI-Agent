# File: test/test_windows_aci.py
"""
测试 Windows ACI 模块
"""
from core.windows_aci import WindowsACI, UIElement
import pyautogui


def test_basic_extraction():
    """测试基础提取功能"""
    print("=" * 60)
    print("测试 1: 基础 UI 元素提取")
    print("=" * 60)

    aci = WindowsACI(top_app_only=True)

    # 准备一个空观测
    obs = {}

    # 提取 UI 树
    elements = aci.linearize_and_annotate_tree(obs)

    print(f"\n✓ 提取到 {len(elements)} 个元素\n")

    # 打印前 10 个元素
    for i, elem in enumerate(elements[:500]):
        print(f"[{i}] role={elem['role']}, title={elem['title']}, "
              f"text={elem['text']}, pos={elem['position']}, size={elem['size']}")

    # 获取第一个元素（PyCharm 窗口）
    window = elements[0]
    x, y = window['position']
    w, h = window['size']

    print(f"窗口位置：({x}, {y})")
    print(f"窗口尺寸：{w} x {h}")

    # 移动鼠标到窗口中心，肉眼验证
    center_x = x + w // 2
    center_y = y + h // 2

    pyautogui.moveTo(center_x, center_y, duration=1)  # ← 1秒内移动到中心
    print(f"鼠标已移动到 ({center_x}, {center_y})")

    return elements


def test_promote_extraction():
    """测试系统级提取"""
    print("\n" + "=" * 60)
    print("测试 2: 系统级 UI 元素提取")
    print("=" * 60)

    aci = WindowsACI(top_app_only=False)
    obs = {}

    elements = aci.linearize_and_annotate_tree(obs)

    print(f"\n✓ 提取到 {len(elements)} 个元素（包括桌面所有窗口）\n")

    # 按角色分组统计
    role_count = {}
    for elem in elements:
        role = elem['role']
        role_count[role] = role_count.get(role, 0) + 1

    print("角色分布:")
    for role, count in sorted(role_count.items(), key=lambda x: -x[1])[:10]:
        print(f"  {role}: {count} 个")

    return elements


def test_visualization():
    """可视化测试结果"""
    print("\n" + "=" * 60)
    print("测试 3: 可视化 UI 元素位置")
    print("=" * 60)

    # 截图
    screenshot = pyautogui.screenshot()
    screenshot.save("output/screenshot_test.png")
    print("✓ 已保存截图：output/screenshot_test.png")

    # 提取元素
    aci = WindowsACI(top_app_only=True)
    elements = aci.linearize_and_annotate_tree({})

    # 在图片上绘制边界框
    from PIL import Image, ImageDraw

    image = screenshot.copy()
    draw = ImageDraw.Draw(image)

    # 绘制前 20 个元素
    for i, elem in enumerate(elements[:20]):
        x, y = elem['position']
        w, h = elem['size']

        # 不同角色用不同颜色
        color = "red" if "Button" in elem['role'] else "green" if "Edit" in elem['role'] else "blue"

        # 绘制矩形
        draw.rectangle([x, y, x + w, y + h], outline=color, width=2)

        # 添加标签
        label = f"{i}:{elem['role'][:8]}"
        draw.text((x, y - 15), label, fill=color)

    # 保存
    image.save("output/screenshot_with_boxes.png")
    print("✓ 已保存标注图：output/screenshot_with_boxes.png")

    return image


if __name__ == "__main__":
    print("\n🚀 开始测试 Windows ACI 模块...\n")

    # 测试 1: 基础提取
    elements1 = test_basic_extraction()

    # 测试 2: 系统级提取
    elements2 = test_promote_extraction()

    # 测试 3: 可视化
    test_visualization()

    print("\n✅ 所有测试完成！")
    print("\n生成的文件:")
    print("  - output/screenshot_test.png (原始截图)")
    print("  - output/screenshot_with_boxes.png (标注后的截图)")
