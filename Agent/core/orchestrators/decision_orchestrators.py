import requests
import json
from openai import OpenAI
import os


def upload_to_picgo(image_path):
    """
    上传图片到picgo图床并返回URL
    """
    # picgo API配置
    api_url = "https://www.picgo.net/api/1/upload"
    api_key = "chv_S9hsj_91e5c6e5c540df2ae395579a0a2dd0c7429e149686d7b9ccf62b0613acb36aa9_ff8d5eac0dd88077f66bed43504b4e20880b26d4286df73ad8a873ebaeae94a7"  # 你需要在这里填入自己的API密钥

    if api_key == "YOUR_PICGO_API_KEY":
        print("警告: 请先设置picgo API密钥")
        return None

    try:
        with open(image_path, "rb") as image_file:
            files = {"source": image_file}
            headers = {"X-API-Key": api_key}

            response = requests.post(api_url, files=files, headers=headers)

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    # 从响应中提取图片URL
                    image_url = result["image"]["url"]
                    print(f"上传成功! 图片URL: {image_url}")
                    return image_url
                else:
                    print(f"上传失败: {result.get('status_txt', '未知错误')}")
                    return None
            else:
                print(f"HTTP错误: {response.status_code}")
                return None

    except Exception as e:
        print(f"上传出错: {str(e)}")
        return None


def get_image_url(image_input):
    """
    处理图片输入，返回可用的URL
    """
    # 判断是URL还是本地文件
    if image_input.startswith(('http://', 'https://')):
        print("检测到网络图片URL")
        return image_input
    else:
        # 本地文件路径
        if not os.path.exists(image_input):
            print(f"错误: 文件不存在 - {image_input}")
            return None

        print("检测到本地图片文件，正在上传到图床...")
        uploaded_url = upload_to_picgo(image_input)

        if uploaded_url:
            return uploaded_url
        else:
            print("上传失败，请检查API密钥或网络连接")
            return None


# 获取用户输入
image_input = input("请输入图片URL或本地文件路径: ")
user_text = input("请输入您的指令: ")

# 获取处理后的图片URL
image_url = get_image_url(image_input)
if not image_url:
    print("无法获取有效的图片URL")
    exit(1)

# 构建消息列表
messages = [
    {
        "role": "system",
        "content": '''## 1. 核心角色 (Core Role)
你是一个顶级的AI视觉操作代理。你的任务是分析电脑屏幕截图，理解用户的指令，然后将任务分解为单一、精确的GUI原子操作。

## 2. [CRITICAL] JSON Schema & 绝对规则
你的输出**必须**是一个严格符合以下规则的JSON对象。
- **[R1] 严格的JSON**: 回复必须是且只能是一个JSON对象，禁止添加额外文本。
- **[R2] thought结构**: "在这里描述思考过程。例如：用户想打开浏览器，我看到了Chrome图标，所以下一步是点击它。"
- **[R3] Action值**: 必须为大写字符串（如 "CLICK", "TYPE"）。
- **[R4] parameters结构**: 必须与工具集中的模板完全一致。

## 3. 工具集 (Available Actions)
### CLICK
- **功能**: 单击屏幕。
- **Parameters模板**: {"x": <integer>, "y": <integer>, "description": "<string, optional>"}

### TYPE
- **功能**: 输入文本。
- **Parameters模板**: {"text": "<string>", "needs_enter": <boolean>}

### SCROLL
- **功能**: 滚动窗口。
- **Parameters模板**: {"direction": "<'up' or 'down'>", "amount": "<'small', 'medium', or 'large'>"}

### KEY_PRESS
- **功能**: 按下功能键。
- **Parameters模板**: {"key": "<string: e.g., 'enter', 'esc'>"}

### FINISH
- **功能**: 任务成功完成。
- **Parameters模板**: {"message": "<string: 总结完成情况>"}

### FAILE
- **功能**: 任务无法完成。
- **Parameters模板**: {"reason": "<string: 清晰解释失败原因>"}

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

client = OpenAI(
    base_url='https://api-inference.modelscope.cn/v1',
    api_key='ms-086b0baa-9eff-4184-b58d-266d71777359',  # ModelScope Token
)

completion = client.chat.completions.create(
    model='iic/GUI-Owl-7B',  # ModelScope Model-Id, required
    messages=messages
)

print(completion.choices[0].message.content)
