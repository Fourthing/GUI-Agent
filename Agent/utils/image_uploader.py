import requests
import os
from dotenv import load_dotenv

load_dotenv()


def upload_to_picgo(image_path):
    """
    上传图片到 picgo 图床并返回 URL

    Args:
        image_path: 本地图片路径

    Returns:
        str: 图片 URL，失败返回 None
    """
    api_key = os.getenv('PICGO_API_KEY')

    if not api_key:
        print("错误：未找到 PICGO_API_KEY 环境变量")
        print("请设置环境变量：set PICGO_API_KEY=your_api_key_here")
        return None

    api_url = "https://www.picgo.net/api/1/upload"

    try:
        with open(image_path, "rb") as image_file:
            files = {"source": image_file}
            headers = {"X-API-Key": api_key}

            response = requests.post(api_url, files=files, headers=headers)

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    image_url = result["image"]["url"]
                    print(f"上传成功！图片 URL: {image_url}")
                    return image_url
                else:
                    print(f"上传失败：{result.get('status_txt', '未知错误')}")
                    return None
            else:
                print(f"HTTP 错误：{response.status_code}")
                return None

    except Exception as e:
        print(f"上传出错：{str(e)}")
        return None


def get_image_url(image_input):
    """
    处理图片输入，返回可用的 URL

    Args:
        image_input: URL 或本地文件路径

    Returns:
        str: 图片 URL，失败返回 None
    """
    if image_input.startswith(('http://', 'https://')):
        print("检测到网络图片 URL")
        return image_input
    else:
        if not os.path.exists(image_input):
            print(f"错误：文件不存在 - {image_input}")
            return None

        print("检测到本地图片文件，正在上传到图床...")
        uploaded_url = upload_to_picgo(image_input)

        if uploaded_url:
            return uploaded_url
        else:
            print("上传失败，请检查 API 密钥或网络连接")
            return None
