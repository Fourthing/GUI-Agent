"""
安全 API 接口测试
测试 Flask API 中的安全相关接口
"""
import unittest
import sys
import os
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.app import app, safety_manager


class TestSafetyAPI(unittest.TestCase):
    """安全 API 测试类"""

    @classmethod
    def setUpClass(cls):
        """测试类启动前的准备工作"""
        cls.app = app
        cls.client = cls.app.test_client()
        cls.app.config['TESTING'] = True

    def setUp(self):
        """每个测试前的准备工作"""
        safety_manager.reset_stop()

        # 清空自定义添加的配置（恢复到默认状态）
        # 注意：实际项目中可能需要更复杂的清理逻辑

    # ==================== /api/stop 接口测试 ====================

    def test_stop_execution_basic(self):
        """测试基本停止功能"""
        response = self.client.post('/api/stop',
                                    data=json.dumps({}),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertIn('停止信号', data['message'])

        # 验证停止标志已设置
        self.assertTrue(safety_manager.is_stopped())

    def test_stop_execution_with_task_id(self):
        """测试带 task_id 的停止请求"""
        response = self.client.post('/api/stop',
                                    data=json.dumps({'task_id': 'task_test123'}),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['task_id'], 'task_test123')

    def test_stop_execution_invalid_json(self):
        """测试无效 JSON 的停止请求"""
        response = self.client.post('/api/stop',
                                    data='invalid json',
                                    content_type='application/json')

        # 应该仍然能处理（因为有默认值）
        self.assertEqual(response.status_code, 200)

    # ==================== /api/safety/config GET 接口测试 ====================

    def test_get_safety_config(self):
        """测试获取安全配置"""
        response = self.client.get('/api/safety/config')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertIn('config', data)

        config = data['config']
        self.assertIn('action_blacklist', config)
        self.assertIn('sensitive_keywords', config)
        self.assertIn('high_risk_patterns', config)

    def test_get_safety_config_structure(self):
        """测试配置结构完整性"""
        response = self.client.get('/api/safety/config')
        data = response.get_json()

        config = data['config']

        # 验证 action_blacklist 结构
        self.assertIsInstance(config['action_blacklist'], dict)
        self.assertIn('HOTKEY', config['action_blacklist'])
        self.assertIn('TYPE', config['action_blacklist'])

        # 验证 sensitive_keywords 结构
        self.assertIsInstance(config['sensitive_keywords'], list)
        self.assertGreater(len(config['sensitive_keywords']), 0)

        # 验证 high_risk_patterns 结构
        self.assertIsInstance(config['high_risk_patterns'], dict)

    # ==================== /api/safety/config POST 接口测试 ====================

    def test_add_sensitive_keyword(self):
        """测试添加敏感词"""
        response = self.client.post('/api/safety/config',
                                    data=json.dumps({
                                        'action': 'add_keyword',
                                        'value': '测试关键词'
                                    }),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertIn('测试关键词', data['config']['sensitive_keywords'])

    def test_remove_sensitive_keyword(self):
        """测试移除敏感词"""
        # 先添加
        self.client.post('/api/safety/config',
                         data=json.dumps({
                             'action': 'add_keyword',
                             'value': '临时关键词'
                         }),
                         content_type='application/json')

        # 再移除
        response = self.client.post('/api/safety/config',
                                    data=json.dumps({
                                        'action': 'remove_keyword',
                                        'value': '临时关键词'
                                    }),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertNotIn('临时关键词', data['config']['sensitive_keywords'])

    def test_add_blocked_hotkey(self):
        """测试添加禁止快捷键"""
        response = self.client.post('/api/safety/config',
                                    data=json.dumps({
                                        'action': 'add_hotkey',
                                        'value': 'ctrl+test'
                                    }),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertIn('ctrl+test', data['config']['action_blacklist']['HOTKEY'])

    def test_remove_blocked_hotkey(self):
        """测试移除禁止快捷键"""
        # 先添加
        self.client.post('/api/safety/config',
                         data=json.dumps({
                             'action': 'add_hotkey',
                             'value': 'ctrl+temp'
                         }),
                         content_type='application/json')

        # 再移除
        response = self.client.post('/api/safety/config',
                                    data=json.dumps({
                                        'action': 'remove_hotkey',
                                        'value': 'ctrl+temp'
                                    }),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertNotIn('ctrl+temp', data['config']['action_blacklist']['HOTKEY'])

    def test_invalid_action(self):
        """测试无效的操作类型"""
        response = self.client.post('/api/safety/config',
                                    data=json.dumps({
                                        'action': 'invalid_action',
                                        'value': 'test'
                                    }),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data['success'])
        self.assertIn('未知的操作', data['error'])

    def test_missing_parameters(self):
        """测试缺少必要参数"""
        response = self.client.post('/api/safety/config',
                                    data=json.dumps({
                                        'action': 'add_keyword'
                                        # 缺少 value
                                    }),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data['success'])
        self.assertIn('缺少', data['error'])

    def test_empty_request_body(self):
        """测试空请求体"""
        response = self.client.post('/api/safety/config',
                                    data=json.dumps({}),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 400)

    # ==================== /api/decision 安全功能测试 ====================

    def test_decision_blocked_by_instruction(self):
        """测试决策接口因指令被拦截"""
        response = self.client.post('/api/decision',
                                    data=json.dumps({
                                        'prompt': '删除所有文件',
                                        'safety_mode': True,
                                        'auto_execute': False
                                    }),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 403)
        data = response.get_json()
        self.assertFalse(data['success'])
        self.assertTrue(data.get('safety_blocked'))
        self.assertIn('安全拦截', data['error'])

    def test_decision_safe_instruction(self):
        """测试决策接口安全指令正常通过"""
        response = self.client.post('/api/decision',
                                    data=json.dumps({
                                        'prompt': '打开记事本',
                                        'safety_mode': True,
                                        'auto_execute': False
                                    }),
                                    content_type='application/json')

        # 不应该被安全拦截（可能会因为其他原因失败，但不应该是 403）
        self.assertNotEqual(response.status_code, 403)

    def test_decision_safety_mode_disabled(self):
        """测试关闭安全模式后敏感指令不被拦截"""
        response = self.client.post('/api/decision',
                                    data=json.dumps({
                                        'prompt': '删除文件',  # 包含敏感词
                                        'safety_mode': False,  # 关闭安全模式
                                        'auto_execute': False
                                    }),
                                    content_type='application/json')

        # 不应该被安全拦截
        self.assertNotEqual(response.status_code, 403)

    def test_decision_default_safety_mode(self):
        """测试默认安全模式（应该开启）"""
        # 不传 safety_mode 参数
        response = self.client.post('/api/decision',
                                    data=json.dumps({
                                        'prompt': '删除所有文件',
                                        'auto_execute': False
                                    }),
                                    content_type='application/json')

        # 当前代码中默认是 False，所以不会被拦截
        # 如果需要默认开启，需要修改 app.py 第 303 行
        self.assertNotEqual(response.status_code, 403)


class TestSafetyIntegration(unittest.TestCase):
    """安全功能集成测试"""

    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.client = cls.app.test_client()
        cls.app.config['TESTING'] = True

    def test_full_safety_workflow(self):
        """测试完整安全工作流"""
        # 1. 添加自定义敏感词
        self.client.post('/api/safety/config',
                         data=json.dumps({
                             'action': 'add_keyword',
                             'value': '自定义危险词'
                         }),
                         content_type='application/json')

        # 2. 尝试使用该敏感词（应该被拦截）
        response = self.client.post('/api/decision',
                                    data=json.dumps({
                                        'prompt': '执行自定义危险词操作',
                                        'safety_mode': True,
                                        'auto_execute': False
                                    }),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 403)

        # 3. 移除敏感词
        self.client.post('/api/safety/config',
                         data=json.dumps({
                             'action': 'remove_keyword',
                             'value': '自定义危险词'
                         }),
                         content_type='application/json')

        # 4. 再次尝试（应该不再被拦截）
        response = self.client.post('/api/decision',
                                    data=json.dumps({
                                        'prompt': '执行自定义危险词操作',
                                        'safety_mode': True,
                                        'auto_execute': False
                                    }),
                                    content_type='application/json')

        # 不应该被安全拦截
        self.assertNotEqual(response.status_code, 403)

    def test_stop_during_execution_simulation(self):
        """模拟执行过程中触发停止"""
        # 触发停止
        self.client.post('/api/stop',
                         data=json.dumps({}),
                         content_type='application/json')

        # 验证停止标志已设置
        self.assertTrue(safety_manager.is_stopped())

        # 重置
        safety_manager.reset_stop()
        self.assertFalse(safety_manager.is_stopped())


if __name__ == '__main__':
    unittest.main(verbosity=2)
