"""
安全管理器 - 统一的安全控制模块
整合操作黑名单、敏感词识别、手动终止等功能

设计理念：
1. 配置化：黑名单和敏感词库从配置文件加载，支持动态更新
2. 简洁性：只提供必要的检查接口，避免过度设计
3. 可扩展：支持运行时添加/删除规则
"""
import json
import os
from typing import Dict, List, Optional
from pathlib import Path


class SafetyManager:
    """安全管理器"""

    def __init__(self, config_path: str = None):
        """
        初始化安全管理器

        Args:
            config_path: 配置文件路径（可选，默认使用内置配置）
        """
        # 全局停止标志
        self.stop_flag = False

        # 加载配置
        if config_path and os.path.exists(config_path):
            self.config = self._load_config_from_file(config_path)
        else:
            self.config = self._get_default_config()

        # 初始化规则库（可动态修改）
        self.action_blacklist = self.config.get('action_blacklist', {})
        self.sensitive_keywords = self.config.get('sensitive_keywords', [])
        self.high_risk_patterns = self.config.get('high_risk_patterns', {})

        # 危险坐标区域（动态计算）
        self.risk_coordinates = self._calculate_risk_coordinates()

    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'action_blacklist': {
                'HOTKEY': [
                    'ctrl+alt+delete',
                    'ctrl+shift+esc',
                ],
                'TYPE': [
                    'rm -rf /',
                    'format c:',
                    'del /f /s /q',
                    'shutdown -s -t 0',
                ]
            },
            'sensitive_keywords': [
                # 破坏性操作
                '删除所有文件', '格式化硬盘', '清空回收站',
                'delete all files', 'format disk',

                # 隐私侵犯
                '窃取密码', '记录键盘', '监控屏幕',
                'steal password', 'keylogger',

                # 恶意行为
                '病毒', '木马', '勒索软件',
                'virus', 'trojan', 'ransomware'
            ],
            'high_risk_patterns': {
                'HOTKEY': ['win+r', 'alt+f4'],
                'TYPE': ['password', 'token', 'secret'],
                'DRAG_TO': {'always_confirm': True}
            }
        }

    def _load_config_from_file(self, config_path: str) -> Dict:
        """从文件加载配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[SafetyManager] ⚠️  配置文件加载失败：{e}，使用默认配置")
            return self._get_default_config()

    def _calculate_risk_coordinates(self) -> List[tuple]:
        """
        计算危险坐标区域

        Returns:
            [(x1, y1, x2, y2), ...] 格式的坐标列表
        """
        try:
            import pyautogui
            width, height = pyautogui.size()

            return [
                # 任务栏区域（底部 50 像素）
                (0, height - 50, width, height),
                # 系统托盘（右下角 200x50）
                (width - 200, height - 50, width, height),
                # 窗口关闭按钮（右上角）
                (width - 50, 0, width, 50),
            ]
        except:
            # 如果无法获取屏幕尺寸，返回空列表
            return []

    # ==================== 配置管理接口 ====================

    def add_blocked_hotkey(self, hotkey: str):
        """动态添加禁止的快捷键"""
        if 'HOTKEY' not in self.action_blacklist:
            self.action_blacklist['HOTKEY'] = []

        if hotkey.lower() not in self.action_blacklist['HOTKEY']:
            self.action_blacklist['HOTKEY'].append(hotkey.lower())
            print(f"[SafetyManager] ✓ 已添加禁止快捷键：{hotkey}")

    def remove_blocked_hotkey(self, hotkey: str):
        """移除禁止的快捷键"""
        if 'HOTKEY' in self.action_blacklist:
            hotkey_lower = hotkey.lower()
            if hotkey_lower in self.action_blacklist['HOTKEY']:
                self.action_blacklist['HOTKEY'].remove(hotkey_lower)
                print(f"[SafetyManager] ✓ 已移除禁止快捷键：{hotkey}")

    def add_sensitive_keyword(self, keyword: str):
        """动态添加敏感词"""
        if keyword not in self.sensitive_keywords:
            self.sensitive_keywords.append(keyword)
            print(f"[SafetyManager] ✓ 已添加敏感词：{keyword}")

    def remove_sensitive_keyword(self, keyword: str):
        """移除敏感词"""
        if keyword in self.sensitive_keywords:
            self.sensitive_keywords.remove(keyword)
            print(f"[SafetyManager] ✓ 已移除敏感词：{keyword}")

    def save_config(self, config_path: str):
        """保存当前配置到文件"""
        try:
            config_data = {
                'action_blacklist': self.action_blacklist,
                'sensitive_keywords': self.sensitive_keywords,
                'high_risk_patterns': self.high_risk_patterns
            }

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)

            print(f"[SafetyManager] ✓ 配置已保存到：{config_path}")
        except Exception as e:
            print(f"[SafetyManager] ❌ 配置保存失败：{e}")

    # ==================== 核心检查接口 ====================

    def check_instruction(self, instruction: str) -> Dict:
        """
        检查用户指令的安全性（入口层检查）

        Args:
            instruction: 用户指令

        Returns:
            {
                'blocked': bool,      # 是否被拦截
                'reason': str         # 拦截原因（如果未被拦截则为空）
            }
        """
        # 检查敏感词
        for keyword in self.sensitive_keywords:
            if keyword.lower() in instruction.lower():
                return {
                    'blocked': True,
                    'reason': f'检测到敏感词："{keyword}"'
                }

        return {
            'blocked': False,
            'reason': ''
        }

    def check_action(self, action: str, parameters: Dict) -> Dict:
        """
        检查动作的安全性（执行前检查）

        Args:
            action: 动作类型（CLICK, TYPE, HOTKEY 等）
            parameters: 动作参数

        Returns:
            {
                'blocked': bool,              # 是否被拦截
                'requires_confirmation': bool, # 是否需要用户确认
                'reason': str                 # 原因说明
            }
        """
        action_upper = action.upper()

        # 1. 检查黑名单
        if action_upper in self.action_blacklist:
            blacklisted_items = self.action_blacklist[action_upper]

            if action_upper == 'HOTKEY':
                keys = parameters.get('keys', [])
                keys_str = '+'.join(keys).lower()

                for banned in blacklisted_items:
                    if banned in keys_str:
                        return {
                            'blocked': True,
                            'requires_confirmation': False,
                            'reason': f'禁止的组合键：{banned}'
                        }

            elif action_upper == 'TYPE':
                text = parameters.get('text', '').lower()

                for banned in blacklisted_items:
                    if banned in text:
                        return {
                            'blocked': True,
                            'requires_confirmation': False,
                            'reason': f'禁止的命令：{banned}'
                        }

        # 2. 检查高风险操作（需要确认）
        if action_upper in self.high_risk_patterns:
            risk_rule = self.high_risk_patterns[action_upper]

            # 总是需要确认的操作
            if isinstance(risk_rule, dict) and risk_rule.get('always_confirm'):
                return {
                    'blocked': False,
                    'requires_confirmation': True,
                    'reason': f'{action} 操作需要用户确认'
                }

            # 模式匹配
            if isinstance(risk_rule, list):
                if action_upper == 'HOTKEY':
                    keys_str = '+'.join(parameters.get('keys', [])).lower()
                    if any(pattern in keys_str for pattern in risk_rule):
                        return {
                            'blocked': False,
                            'requires_confirmation': True,
                            'reason': f'组合键 {keys_str} 需要确认'
                        }

                elif action_upper == 'TYPE':
                    text = parameters.get('text', '').lower()
                    if any(pattern in text for pattern in risk_rule):
                        return {
                            'blocked': False,
                            'requires_confirmation': True,
                            'reason': '输入内容包含敏感信息，需要确认'
                        }

        # 3. 检查危险坐标区域
        if action_upper in ['CLICK', 'DOUBLE_CLICK', 'RIGHT_CLICK']:
            x = parameters.get('x')
            y = parameters.get('y')

            if x is not None and y is not None and self.risk_coordinates:
                for x1, y1, x2, y2 in self.risk_coordinates:
                    if x1 <= x <= x2 and y1 <= y <= y2:
                        return {
                            'blocked': False,
                            'requires_confirmation': True,
                            'reason': f'点击位置 ({x}, {y}) 在系统区域，建议确认'
                        }

        # 默认：安全且无需确认
        return {
            'blocked': False,
            'requires_confirmation': False,
            'reason': ''
        }

    # ==================== 停止控制接口 ====================

    def trigger_stop(self):
        """触发停止（用于外部调用）"""
        self.stop_flag = True
        print("[SafetyManager] ⚠️  已触发停止标志")

    def reset_stop(self):
        """重置停止标志"""
        self.stop_flag = False

    def is_stopped(self) -> bool:
        """检查是否已停止"""
        return self.stop_flag
