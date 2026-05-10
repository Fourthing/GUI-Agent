# File: test_click_accuracy.py
import pyautogui
import time

print("=" * 60)
print("点击精度测试工具")
print("=" * 60)

# 1. 显示当前屏幕分辨率
screen_width, screen_height = pyautogui.size()
print(f"\n屏幕分辨率：{screen_width} x {screen_height}")

# 2. 测试点击（会在屏幕上画十字标记）
print("\n即将在屏幕中心画十字标记...")
time.sleep(2)

center_x = screen_width // 2
center_y = screen_height // 2

# 画十字
pyautogui.moveTo(center_x, center_y, duration=0.5)
print(f"鼠标已移动到中心：({center_x}, {center_y})")

# 3. 让你肉眼观察是否准确
input("\n按 Enter 键继续测试...")

# 4. 测试一系列坐标点
test_points = [
    (0, 0, "左上角"),
    (screen_width - 1, 0, "右上角"),
    (0, screen_height - 1, "左下角"),
    (screen_width - 1, screen_height - 1, "右下角"),
    (center_x, center_y, "中心点"),
]

for x, y, desc in test_points:
    print(f"\n测试：{desc} ({x}, {y})")
    pyautogui.moveTo(x, y, duration=0.3)
    time.sleep(1)
    response = input("是否准确？(y/n): ")

    if response.lower() == 'n':
        actual_x = int(input("实际 X 坐标应该是："))
        actual_y = int(input("实际 Y 坐标应该是："))
        print(f"→ 发现偏移：X 差{actual_x - x}, Y 差{actual_y - y}")
