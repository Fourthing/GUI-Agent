"""
集成测试
测试安全模块与其他模块的协同工作
"""
import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.safety_manager import SafetyManager
from core.action_module import ActionModule


class TestSafetyActionIntegration(unittest.TestCase):
    """安全模块与动作模块集成测试"""

    def setUp(self):
        self.safety_manager = SafetyManager()
        self.action_module = ActionModule()

    def test_safe_action_execution(self):
        """测试安全动作可以正常执行"""
        # 检查动作安全性
        action = 'CLICK'
        parameters = {'x': 500, 'y': 300}

        safety_check = self.safety_manager.check_action(action, parameters)

        # 应该通过安全检查
        self.assertFalse(safety_check['blocked'])
        self.assertFalse(safety_check['requires_confirmation'])

    def test_blocked_action_not_executed(self):
        """测试被拦截的动作不会执行"""
        # 检查危险动作
        action = 'HOTKEY'
        parameters = {'keys': ['ctrl', 'alt', 'delete']}

        safety_check = self.safety_manager.check_action(action, parameters)

        # 应该被拦截
        self.assertTrue(safety_check['blocked'])

        # 在实际应用中，这里应该不会调用 action_module.execute()
        # 这个测试验证了安全检查的有效性

    def test_confirmation_required_workflow(self):
        """测试需要确认的工作流"""
        action = 'TYPE'
        parameters = {'text': 'my_password'}

        safety_check = self.safety_manager.check_action(action, parameters)

        # 应该需要确认
        self.assertFalse(safety_check['blocked'])
        self.assertTrue(safety_check['requires_confirmation'])

        # 模拟用户确认后执行
        # 在实际应用中，前端会弹窗让用户确认
        # 这里只是验证逻辑流程

    def test_instruction_and_action_combined_check(self):
        """测试指令和动作的组合检查"""
        instruction = "打开记事本"
        action = 'CLICK'
        parameters = {'x': 500, 'y': 300}

        # 1. 检查指令
        instruction_check = self.safety_manager.check_instruction(instruction)
        self.assertFalse(instruction_check['blocked'])

        # 2. 检查动作
        action_check = self.safety_manager.check_action(action, parameters)
        self.assertFalse(action_check['blocked'])

        # 3. 两者都通过，可以执行
        can_execute = not instruction_check['blocked'] and not action_check['blocked']
        self.assertTrue(can_execute)

    def test_blocked_instruction_prevents_execution(self):
        """测试被拦截的指令阻止执行"""
        instruction = "删除所有文件"
        action = 'TYPE'
        parameters = {'text': 'rm -rf /'}

        # 1. 检查指令（应该被拦截）
        instruction_check = self.safety_manager.check_instruction(instruction)
        self.assertTrue(instruction_check['blocked'])

        # 2. 即使动作本身可能没问题，但指令被拦截就不应该执行
        should_execute = not instruction_check['blocked']
        self.assertFalse(should_execute)


class TestSafetyConfigurationPersistence(unittest.TestCase):
    """安全配置持久化测试"""

    def test_config_modification_persists_across_checks(self):
        """测试配置修改在多次检查中保持有效"""
        manager = SafetyManager()

        # 添加敏感词
        manager.add_sensitive_keyword('持久化测试词')

        # 第一次检查
        result1 = manager.check_instruction('包含持久化测试词的指令')
        self.assertTrue(result1['blocked'])

        # 第二次检查（验证配置仍然有效）
        result2 = manager.check_instruction('另一个包含持久化测试词的句子')
        self.assertTrue(result2['blocked'])

        # 第三次检查
        result3 = manager.check_instruction('持久化测试词')
        self.assertTrue(result3['blocked'])

    def test_multiple_managers_independent(self):
        """测试多个管理器实例相互独立"""
        manager1 = SafetyManager()
        manager2 = SafetyManager()

        # 修改 manager1 的配置
        manager1.add_sensitive_keyword('仅manager1的词')

        # manager2 不应该受到影响
        result = manager2.check_instruction('包含仅manager1的词的指令')
        self.assertFalse(result['blocked'])


class TestSafetyEdgeCases(unittest.TestCase):
    """安全模块边界情况测试"""

    def setUp(self):
        self.manager = SafetyManager()

    def test_very_long_instruction(self):
        """测试超长指令"""
        long_instruction = "打开" * 1000 + "记事本"
        result = self.manager.check_instruction(long_instruction)

        # 不应该崩溃
        self.assertIsInstance(result, dict)
        self.assertIn('blocked', result)

    def test_special_characters_in_instruction(self):
        """测试特殊字符"""
        special_instruction = "打开@#$%^&*()记事本"
        result = self.manager.check_instruction(special_instruction)

        # 不应该崩溃
        self.assertIsInstance(result, dict)

    def test_unicode_characters(self):
        """测试 Unicode 字符"""
        unicode_instruction = "打开📝记事本"
        result = self.manager.check_instruction(unicode_instruction)

        # 不应该崩溃
        self.assertIsInstance(result, dict)

    def test_empty_action_name(self):
        """测试空动作名称"""
        result = self.manager.check_action('', {})

        # 不应该崩溃
        self.assertIsInstance(result, dict)
        self.assertFalse(result['blocked'])

    def test_none_action_name(self):
        """测试 None 动作名称"""
        with self.assertRaises(AttributeError):
            # None.upper() 会抛出 AttributeError
            self.manager.check_action(None, {})

    def test_very_large_coordinates(self):
        """测试超大坐标值"""
        result = self.manager.check_action('CLICK', {
            'x': 999999,
            'y': 999999
        })

        # 不应该崩溃
        self.assertIsInstance(result, dict)

    def test_negative_coordinates(self):
        """测试负数坐标"""
        result = self.manager.check_action('CLICK', {
            'x': -100,
            'y': -100
        })

        # 不应该崩溃
        self.assertIsInstance(result, dict)


if __name__ == '__main__':
    unittest.main(verbosity=2)
