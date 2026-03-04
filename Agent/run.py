"""
GUI-Agent 主入口
用法:
    python run.py          - 启动 API 服务（默认）
    python run.py test     - 直接测试模式
"""
import sys
import os

# 添加 Agent 目录到 Python 路径
agent_path = os.path.dirname(os.path.abspath(__file__))
if agent_path not in sys.path:
    sys.path.insert(0, agent_path)


def run_api_server():
    """启动 API 服务"""
    from api.app import app

    print("=" * 60)
    print("🚀 GUI-Agent API 服务启动")
    print("=" * 60)
    print("接口地址：http://localhost:5000/api/decision")
    print("健康检查：http://localhost:5000/api/health")
    print("按 Ctrl+C 停止服务\n")

    app.run(host='0.0.0.0', port=5000, debug=True)


def run_direct_test():
    """直接测试模式"""
    from core.orchestrators.decision_orchestrator import DecisionOrchestrator
    from utils.image_uploader import get_image_url

    print("=" * 60)
    print("🧪 GUI-Agent 直接测试模式")
    print("=" * 60)

    image_input = input("\n请输入图片 URL 或本地文件路径：")
    user_text = input("请输入您的指令：")

    image_url = get_image_url(image_input)
    if not image_url:
        print("❌ 无法获取有效的图片 URL")
        return

    orchestrator = DecisionOrchestrator()
    result = orchestrator.decide(image_url, user_text)

    print("\n" + "=" * 60)
    print("📊 决策结果")
    print("=" * 60)

    if result['success']:
        print(f"✅ Thought: {result['thought']}")
        print(f"🎯 Action: {result['action']}")
        print(f"📋 Parameters: {result['parameters']}")
    else:
        print(f"❌ 失败：{result['error']}")

    print("=" * 60)


def main():
    """根据命令行参数决定运行模式"""
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        run_direct_test()
    else:
        run_api_server()


if __name__ == "__main__":
    main()
