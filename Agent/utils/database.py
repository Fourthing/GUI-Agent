from supabase import create_client, Client
from dotenv import load_dotenv
import os

load_dotenv()


class DatabaseClient:
    """Supabase 数据库客户端"""

    def __init__(self):
        self.url = os.getenv('SUPABASE_URL')
        self.key = os.getenv('SUPABASE_KEY')

        if not self.url or not self.key:
            raise ValueError("未找到 Supabase 配置环境变量")

        self.client: Client = create_client(self.url, self.key)

    # ========== Task Executions ==========
    def create_task(self, task_id: str, instruction: str, total_steps: int) -> dict:
        """创建任务记录"""
        result = self.client.table('task_executions').insert({
            'task_id': task_id,
            'user_instruction': instruction,
            'total_steps': total_steps,
            'status': 'running'
        }).execute()
        return result.data[0]

    def update_task_status(self, task_id: str, status: str,
                           completed_steps: int = None,
                           total_retries: int = None) -> dict:
        """更新任务状态"""
        update_data = {
            'status': status,
            'updated_at': 'now()'
        }

        if completed_steps is not None:
            update_data['completed_steps'] = completed_steps

        if total_retries is not None:
            update_data['total_retries'] = total_retries

        if status in ['success', 'failed', 'partial']:
            update_data['ended_at'] = 'now()'
            # 计算持续时间（需要应用端计算）

        result = self.client.table('task_executions').update(update_data).eq('task_id', task_id).execute()
        return result.data[0]

    # ========== Step Executions ==========
    def create_step(self, task_db_id: str, step_no: int,
                    instruction: str, expected_action: str = None) -> dict:
        """创建步骤记录"""
        result = self.client.table('step_executions').insert({
            'task_id': task_db_id,
            'step_no': step_no,
            'instruction': instruction,
            'expected_action': expected_action,
            'status': 'pending'
        }).execute()
        return result.data[0]

    def update_step_status(self, step_db_id: str, status: str,
                           retry_count: int = None) -> dict:
        """更新步骤状态"""
        update_data = {
            'status': status,
            'updated_at': 'now()'
        }

        if retry_count is not None:
            update_data['retry_count'] = retry_count

        result = self.client.table('step_executions').update(update_data).eq('id', step_db_id).execute()
        return result.data[0]

    # ========== Decisions ==========
    def create_decision(self, step_db_id: str, attempt_no: int,
                        thought: str = None, action_type: str = None,
                        parameters: dict = None, full_response: dict = None) -> dict:
        """创建决策记录"""
        result = self.client.table('decisions').insert({
            'step_id': step_db_id,
            'attempt_no': attempt_no,
            'thought': thought,
            'action_type': action_type,
            'parameters': parameters,
            'full_response': full_response
        }).execute()
        return result.data[0]

    def update_decision_result(self, decision_db_id: str,
                               execution_success: bool,
                               execution_message: str = None,
                               decision_time_ms: int = None,
                               screenshot_url: str = None) -> dict:
        """更新决策执行结果"""
        update_data = {
            'execution_success': execution_success,
            'execution_message': execution_message
        }

        if decision_time_ms is not None:
            update_data['decision_time_ms'] = decision_time_ms

        if screenshot_url is not None:
            update_data['screenshot_url'] = screenshot_url

        result = self.client.table('decisions').update(update_data).eq('id', decision_db_id).execute()
        return result.data[0]

    # ========== Reflect Verifications ==========
    def create_verification(self, decision_db_id: str,
                            status: str, success: bool, error_flag: bool,
                            confidence: float = None,
                            changes_detected: list = None,
                            analysis: str = None,
                            suggestion: str = None,
                            diagnosis: dict = None,
                            retry_recommendation: dict = None) -> dict:
        """创建验证记录"""
        result = self.client.table('reflect_verifications').insert({
            'decision_id': decision_db_id,
            'status': status,
            'success': success,
            'error_flag': error_flag,
            'confidence': confidence,
            'changes_detected': changes_detected,
            'analysis': analysis,
            'suggestion': suggestion,
            'diagnosis': diagnosis,
            'retry_recommendation': retry_recommendation
        }).execute()
        return result.data[0]

    # ========== Error Logs ==========
    def log_error(self, error_level: str, error_message: str,
                  error_type: str = None, stack_trace: str = None,
                  context: dict = None, task_db_id: str = None,
                  step_db_id: str = None, decision_db_id: str = None) -> dict:
        """记录错误日志"""
        result = self.client.table('error_logs').insert({
            'error_level': error_level,
            'error_type': error_type,
            'error_message': error_message,
            'stack_trace': stack_trace,
            'context': context,
            'task_id': task_db_id,
            'step_id': step_db_id,
            'decision_id': decision_db_id
        }).execute()
        return result.data[0]

    # ========== 查询方法 ==========
    def get_task_by_id(self, task_id: str) -> dict:
        """根据 task_id 获取任务"""
        result = self.client.table('task_executions').select('*').eq('task_id', task_id).execute()
        return result.data[0] if result.data else None

    def get_task_with_steps(self, task_db_id: str) -> dict:
        """获取任务及其所有步骤"""
        result = self.client.table('task_executions').select('''
            *,
            step_executions (
                *,
                decisions (
                    *,
                    reflect_verifications (*)
                )
            )
        ''').eq('id', task_db_id).execute()
        return result.data[0] if result.data else None

    def get_recent_tasks(self, limit: int = 10) -> list:
        """获取最近的任务"""
        result = self.client.table('task_executions').select('*').order('created_at', desc=True).limit(limit).execute()
        return result.data

    def get_failure_statistics(self, days: int = 7) -> dict:
        """获取失败统计信息"""
        from datetime import datetime, timedelta

        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        # 总任务数
        total = self.client.table('task_executions').select('id', count='exact').execute()

        # 失败任务数
        failed = self.client.table('task_executions').select('id', count='exact').eq('status', 'failed').lt(
            'created_at', cutoff_date).execute()

        # 按错误类型统计
        # （需要更复杂的查询，这里简化）

        return {
            'total_tasks': total.count,
            'failed_tasks': failed.count,
            'failure_rate': failed.count / total.count if total.count > 0 else 0
        }


# 创建全局实例
db = DatabaseClient()
