"""
安全管理器单元测试
测试 SafetyManager 的核心功能
"""
import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.safety_manager import SafetyManager


class TestSafetyManager(unittest.TestCase):
    """安全管理器测试类"""

    def setUp(self):
        """每个测试前的准备工作"""
        self.manager = SafetyManager()

    def tearDown(self):
        """每个测试后的清理工作"""
        self.manager.reset_stop()

    # ==================== 初始化测试 ====================

    def test_default_config_loaded(self):
        """测试默认配置加载"""
        self.assertIsNotNone(self.manager.action_blacklist)
        self.assertIsNotNone(self.manager.sensitive_keywords)
        self.assertIsNotNone(self.manager.high_risk_patterns)

        # 检查关键配置项是否存在
        self.assertIn('HOTKEY', self.manager.action_blacklist)
        self.assertIn('TYPE', self.manager.action_blacklist)
        self.assertGreater(len(self.manager.sensitive_keywords), 0)

    def test_stop_flag_initial_state(self):
        """测试停止标志初始状态"""
        self.assertFalse(self.manager.is_stopped())

    # ==================== 指令安全检查测试 ====================

    def test_safe_instruction(self):
        """测试安全指令"""
        result = self.manager.check_instruction("打开记事本")
        self.assertFalse(result['blocked'])
        self.assertEqual(result['reason'], '')

    def test_blocked_destructive_keyword(self):
        """测试破坏性敏感词拦截"""
        result = self.manager.check_instruction("删除所有文件")
        self.assertTrue(result['blocked'])
        self.assertIn('敏感词', result['reason'])

    def test_blocked_privacy_keyword(self):
        """测试隐私侵犯敏感词拦截"""
        result = self.manager.check_instruction("窃取密码")
        self.assertTrue(result['blocked'])
        self.assertIn('敏感词', result['reason'])

    def test_blocked_malicious_keyword(self):
        """测试恶意行为敏感词拦截"""
        result = self.manager.check_instruction("安装病毒")
        self.assertTrue(result['blocked'])
        self.assertIn('敏感词', result['reason'])

    def test_case_insensitive_check(self):
        """测试大小写不敏感"""
        result1 = self.manager.check_instruction("DELETE ALL FILES")
        result2 = self.manager.check_instruction("delete all files")

        self.assertTrue(result1['blocked'])
        self.assertTrue(result2['blocked'])

    # ==================== 动作安全检查测试 ====================

    def test_safe_action_click(self):
        """测试安全的点击操作"""
        result = self.manager.check_action('CLICK', {'x': 500, 'y': 300})
        self.assertFalse(result['blocked'])
        self.assertFalse(result['requires_confirmation'])

    def test_blocked_hotkey_ctrl_alt_delete(self):
        """测试禁止的组合键：Ctrl+Alt+Delete"""
        result = self.manager.check_action('HOTKEY', {
            'keys': ['ctrl', 'alt', 'delete']
        })
        self.assertTrue(result['blocked'])
        self.assertIn('禁止的组合键', result['reason'])

    def test_blocked_hotkey_ctrl_shift_esc(self):
        """测试禁止的组合键：Ctrl+Shift+Esc"""
        result = self.manager.check_action('HOTKEY', {
            'keys': ['ctrl', 'shift', 'esc']
        })
        self.assertTrue(result['blocked'])

    def test_blocked_type_command_rm_rf(self):
        """测试禁止的命令：rm -rf /"""
        result = self.manager.check_action('TYPE', {
            'text': 'rm -rf /'
        })
        self.assertTrue(result['blocked'])
        self.assertIn('禁止的命令', result['reason'])

    def test_blocked_type_command_format(self):
        """测试禁止的命令：format c:"""
        result = self.manager.check_action('TYPE', {
            'text': 'format c:'
        })
        self.assertTrue(result['blocked'])

    def test_requires_confirmation_win_r(self):
        """测试需要确认的组合键：Win+R"""
        result = self.manager.check_action('HOTKEY', {
            'keys': ['win', 'r']
        })
        self.assertFalse(result['blocked'])
        self.assertTrue(result['requires_confirmation'])
        self.assertIn('需要确认', result['reason'])

    def test_requires_confirmation_password_input(self):
        """测试需要确认的密码输入"""
        result = self.manager.check_action('TYPE', {
            'text': 'my_password_123'
        })
        self.assertFalse(result['blocked'])
        self.assertTrue(result['requires_confirmation'])

    def test_requires_confirmation_drag_to(self):
        """测试拖拽操作总是需要确认"""
        result = self.manager.check_action('DRAG_TO', {
            'startX': 100,
            'startY': 100,
            'endX': 200,
            'endY': 200
        })
        self.assertFalse(result['blocked'])
        self.assertTrue(result['requires_confirmation'])

    def test_risk_coordinates_click(self):
        """测试危险区域点击需要确认"""
        import pyautogui
        width, height = pyautogui.size()

        # 点击任务栏区域（底部）
        result = self.manager.check_action('CLICK', {
            'x': width // 2,
            'y': height - 25
        })

        # 如果屏幕尺寸获取成功，应该需要确认
        if self.manager.risk_coordinates:
            self.assertTrue(result['requires_confirmation'])
            self.assertIn('系统区域', result['reason'])

    def test_safe_coordinates_click(self):
        """测试安全区域点击无需确认"""
        result = self.manager.check_action('CLICK', {
            'x': 500,
            'y': 300
        })
        self.assertFalse(result['blocked'])
        self.assertFalse(result['requires_confirmation'])

    def test_unknown_action(self):
        """测试未知动作类型"""
        result = self.manager.check_action('UNKNOWN_ACTION', {})
        self.assertFalse(result['blocked'])
        self.assertFalse(result['requires_confirmation'])

    # ==================== 动态配置管理测试 ====================

    def test_add_sensitive_keyword(self):
        """测试动态添加敏感词"""
        initial_count = len(self.manager.sensitive_keywords)
        self.manager.add_sensitive_keyword('测试敏感词')

        self.assertEqual(len(self.manager.sensitive_keywords), initial_count + 1)
        self.assertIn('测试敏感词', self.manager.sensitive_keywords)

        # 验证新添加的敏感词生效
        result = self.manager.check_instruction('包含测试敏感词的指令')
        self.assertTrue(result['blocked'])

    def test_remove_sensitive_keyword(self):
        """测试移除敏感词"""
        self.manager.add_sensitive_keyword('临时敏感词')
        self.assertIn('临时敏感词', self.manager.sensitive_keywords)

        self.manager.remove_sensitive_keyword('临时敏感词')
        self.assertNotIn('临时敏感词', self.manager.sensitive_keywords)

    def test_add_blocked_hotkey(self):
        """测试动态添加禁止快捷键"""
        self.manager.add_blocked_hotkey('win+d')

        self.assertIn('win+d', self.manager.action_blacklist['HOTKEY'])

        # 验证新添加的快捷键被拦截
        result = self.manager.check_action('HOTKEY', {
            'keys': ['win', 'd']
        })
        self.assertTrue(result['blocked'])

    def test_remove_blocked_hotkey(self):
        """测试移除禁止快捷键"""
        self.manager.add_blocked_hotkey('win+x')
        self.assertIn('win+x', self.manager.action_blacklist['HOTKEY'])

        self.manager.remove_blocked_hotkey('win+x')
        self.assertNotIn('win+x', self.manager.action_blacklist['HOTKEY'])

    def test_duplicate_keyword_addition(self):
        """测试重复添加敏感词不会重复"""
        self.manager.add_sensitive_keyword('唯一敏感词')
        initial_count = len(self.manager.sensitive_keywords)

        self.manager.add_sensitive_keyword('唯一敏感词')  # 再次添加

        self.assertEqual(len(self.manager.sensitive_keywords), initial_count)

    # ==================== 停止控制测试 ====================

    def test_trigger_stop(self):
        """测试触发停止"""
        self.assertFalse(self.manager.is_stopped())

        self.manager.trigger_stop()
        self.assertTrue(self.manager.is_stopped())

    def test_reset_stop(self):
        """测试重置停止标志"""
        self.manager.trigger_stop()
        self.assertTrue(self.manager.is_stopped())

        self.manager.reset_stop()
        self.assertFalse(self.manager.is_stopped())

    # ==================== 配置文件测试 ====================

    def test_save_and_load_config(self):
        """测试保存和加载配置"""
        import json
        import tempfile

        # 添加自定义配置
        self.manager.add_sensitive_keyword('自定义敏感词')
        self.manager.add_blocked_hotkey('ctrl+w')

        # 保存到临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            self.manager.save_config(temp_path)

            # 验证文件存在且可读取
            self.assertTrue(os.path.exists(temp_path))

            with open(temp_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            self.assertIn('sensitive_keywords', config)
            self.assertIn('action_blacklist', config)
            self.assertIn('自定义敏感词', config['sensitive_keywords'])
            self.assertIn('ctrl+w', config['action_blacklist']['HOTKEY'])

        finally:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_load_nonexistent_config(self):
        """测试加载不存在的配置文件（应使用默认配置）"""
        manager = SafetyManager(config_path='/nonexistent/path.json')

        # 应该回退到默认配置
        self.assertIsNotNone(manager.action_blacklist)
        self.assertGreater(len(manager.sensitive_keywords), 0)

    def test_load_invalid_json_config(self):
        """测试加载无效的 JSON 文件"""
        import tempfile

        # 创建无效的 JSON 文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{ invalid json }')
            temp_path = f.name

        try:
            manager = SafetyManager(config_path=temp_path)

            # 应该回退到默认配置
            self.assertIsNotNone(manager.action_blacklist)

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    # ==================== 边界情况测试 ====================

    def test_empty_instruction(self):
        """测试空指令"""
        result = self.manager.check_instruction('')
        self.assertFalse(result['blocked'])

    def test_none_parameters(self):
        """测试 None 参数"""
        result = self.manager.check_action('CLICK', None)
        # 应该 gracefully 处理
        self.assertFalse(result['blocked'])

    def test_missing_keys_in_hotkey(self):
        """测试缺少 keys 参数的 HOTKEY 动作"""
        result = self.manager.check_action('HOTKEY', {})
        self.assertFalse(result['blocked'])

    def test_missing_text_in_type(self):
        """测试缺少 text 参数的 TYPE 动作"""
        result = self.manager.check_action('TYPE', {})
        self.assertFalse(result['blocked'])

    def test_missing_coordinates_in_click(self):
        """测试缺少坐标的 CLICK 动作"""
        result = self.manager.check_action('CLICK', {})
        self.assertFalse(result['blocked'])
        self.assertFalse(result['requires_confirmation'])


class TestSafetyManagerWithCustomConfig(unittest.TestCase):
    """使用自定义配置的测试类"""

    def test_custom_config_loading(self):
        """测试从自定义配置文件加载"""
        import json
        import tempfile

        custom_config = {
            'action_blacklist': {
                'HOTKEY': ['ctrl+c'],
                'TYPE': ['test_command']
            },
            'sensitive_keywords': ['自定义词1', '自定义词2'],
            'high_risk_patterns': {
                'HOTKEY': ['alt+f4']
            }
        }

        # 创建临时配置文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(custom_config, f)
            temp_path = f.name

        try:
            manager = SafetyManager(config_path=temp_path)

            # 验证自定义配置已加载
            self.assertIn('ctrl+c', manager.action_blacklist['HOTKEY'])
            self.assertIn('自定义词1', manager.sensitive_keywords)
            self.assertIn('alt+f4', manager.high_risk_patterns['HOTKEY'])

            # 验证自定义配置生效
            result = manager.check_instruction('包含自定义词1的指令')
            self.assertTrue(result['blocked'])

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)
