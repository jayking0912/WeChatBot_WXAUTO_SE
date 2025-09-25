# -*- coding: utf-8 -*-

"""
任务管理模块 - 处理任务识别、记录和状态管理
Task management module for task identification, recording and status management
"""

import re
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from config import *
from database import get_db_manager, TaskRecord

logger = logging.getLogger(__name__)

@dataclass
class TaskStatus:
    """任务状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class TaskManager:
    """任务管理器"""

    def __init__(self):
        self.db_manager = get_db_manager()
        self.task_keywords = [
            "要做", "需要", "记得", "别忘了", "提醒", "任务", "计划", "安排",
            "明天", "后天", "下周", "下月", "待办", "todo", "TODO"
        ]

    def is_task_record_group(self, group_name: str) -> bool:
        """判断是否为任务记录群"""
        if not ENABLE_TASK_MANAGEMENT:
            return False

        return group_name in TASK_RECORD_GROUPS

    def extract_task_from_message(self, message: str, user_id: str, group_name: str) -> List[TaskRecord]:
        """从消息中提取任务信息"""
        try:
            if not self.is_task_record_group(group_name):
                return []

            # 检查是否包含任务关键词
            has_task_keywords = any(keyword in message for keyword in self.task_keywords)

            # 检查是否包含时间相关词汇
            time_patterns = [
                r'明天|后天|今天|今日',
                r'下周|下月|下年',
                r'\d+[天月周年]后',
                r'\d{1,2}[月日号]',
                r'\d{4}年\d{1,2}月\d{1,2}日'
            ]
            has_time_reference = any(re.search(pattern, message) for pattern in time_patterns)

            # 如果包含任务关键词或时间引用，认为可能是任务
            if has_task_keywords or has_time_reference or len(message) > 10:
                task_record = TaskRecord(
                    content=message.strip(),
                    user_id=user_id,
                    group_name=group_name,
                    create_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    status=TaskStatus.PENDING,
                    priority=3,  # 默认优先级
                    urgency=3,   # 默认紧急度
                    details=""
                )

                return [task_record]

            return []

        except Exception as e:
            logger.error(f"提取任务失败: {e}")
            return []

    def save_task_to_db(self, task: TaskRecord) -> int:
        """保存任务到数据库"""
        try:
            task_id = self.db_manager.save_task(task)
            if task_id > 0:
                logger.info(f"保存任务成功: {task.content[:50]}..., ID: {task_id}")
            return task_id
        except Exception as e:
            logger.error(f"保存任务到数据库失败: {e}")
            return -1

    def parse_task_completion(self, message: str, user_id: str, group_name: str) -> List[Tuple[int, str]]:
        """解析任务完成/取消消息，返回[(task_id, status)]"""
        try:
            if not self.is_task_record_group(group_name):
                return []

            # 检查完成关键词
            completion_patterns = [
                (TaskStatus.COMPLETED, ["完成", "搞定", "做完", "弄好", "ok", "OK", "done", "DONE"]),
                (TaskStatus.CANCELLED, ["取消", "不做", "放弃", "cancel", "CANCEL"])
            ]

            results = []

            for status, keywords in completion_patterns:
                for keyword in keywords:
                    if keyword in message:
                        # 尝试从消息中提取任务ID或内容
                        # 这里简化处理，获取最近的待处理任务
                        recent_tasks = self.get_recent_pending_tasks(user_id, group_name, limit=5)

                        if recent_tasks:
                            # 如果消息中包含具体内容，尝试匹配
                            for task in recent_tasks:
                                # 简单的内容匹配
                                if len(message) > 10:
                                    # 计算相似度（简化版）
                                    if self._calculate_similarity(task['content'], message) > 0.3:
                                        results.append((task['id'], status))
                                        break
                            else:
                                # 如果没有匹配到，默认完成最新的任务
                                results.append((recent_tasks[0]['id'], status))

                        break  # 找到一个关键词就不再继续

            return results

        except Exception as e:
            logger.error(f"解析任务完成失败: {e}")
            return []

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度（简化版）"""
        try:
            # 简单的字符重叠率计算
            set1 = set(text1)
            set2 = set(text2)
            intersection = len(set1 & set2)
            union = len(set1 | set2)
            return intersection / union if union > 0 else 0
        except:
            return 0

    def update_task_status(self, task_id: int, status: str) -> bool:
        """更新任务状态"""
        try:
            completion_time = None
            if status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
                completion_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            success = self.db_manager.update_task_status(task_id, status, completion_time)
            if success:
                logger.info(f"更新任务状态成功: ID {task_id}, 状态: {status}")
            return success
        except Exception as e:
            logger.error(f"更新任务状态失败: {e}")
            return False

    def get_recent_pending_tasks(self, user_id: str, group_name: str, limit: int = 10) -> List[Dict]:
        """获取最近的待处理任务"""
        try:
            tasks = self.db_manager.get_tasks_by_group(group_name, status=TaskStatus.PENDING)
            # 过滤当前用户的任务
            user_tasks = [task for task in tasks if task['user_id'] == user_id]
            return user_tasks[:limit]
        except Exception as e:
            logger.error(f"获取待处理任务失败: {e}")
            return []

    def get_tasks_by_group(self, group_name: str, status: str = None,
                          include_archived: bool = False) -> List[Dict]:
        """获取群组任务"""
        try:
            return self.db_manager.get_tasks_by_group(group_name, status, include_archived)
        except Exception as e:
            logger.error(f"获取群组任务失败: {e}")
            return []

    def search_tasks_by_content(self, query: str, group_name: str = None) -> List[Dict]:
        """根据内容搜索任务"""
        try:
            return self.db_manager.search_tasks_by_content(query, group_name)
        except Exception as e:
            logger.error(f"搜索任务失败: {e}")
            return []

    def archive_completed_tasks(self, group_name: str = None) -> int:
        """归档已完成任务"""
        try:
            if AUTO_ARCHIVE_COMPLETED_TASKS:
                return self.db_manager.archive_completed_tasks(group_name)
            return 0
        except Exception as e:
            logger.error(f"归档任务失败: {e}")
            return 0

    def get_new_tasks_since_last_review(self, group_name: str,
                                       last_review_date: str = None) -> List[Dict]:
        """获取上次复盘以来的新任务"""
        try:
            if not last_review_date:
                # 如果没有上次复盘日期，获取24小时内的任务
                yesterday = datetime.now() - timedelta(days=1)
                last_review_date = yesterday.strftime("%Y-%m-%d %H:%M:%S")

            all_tasks = self.get_tasks_by_group(group_name, include_archived=True)

            # 过滤出指定时间之后的任务
            new_tasks = []
            for task in all_tasks:
                if task['create_time'] > last_review_date:
                    new_tasks.append(task)

            return new_tasks

        except Exception as e:
            logger.error(f"获取新任务失败: {e}")
            return []

    def analyze_tasks_with_llm(self, tasks: List[Dict]) -> Dict:
        """使用LLM分析任务的重要性和紧急度"""
        try:
            if not tasks:
                return {"task_analysis": [], "summary": "没有任务需要分析"}

            # 导入LLM调用函数（避免循环导入）
            from bot import call_auxiliary_api_with_retry

            # 构建任务列表字符串
            tasks_text = []
            for i, task in enumerate(tasks, 1):
                tasks_text.append(f"{i}. {task['content']} (创建时间: {task['create_time']})")

            tasks_str = "\n".join(tasks_text)

            # 使用任务分析提示词
            prompt = TASK_ANALYSIS_PROMPT.format(tasks=tasks_str)

            # 调用LLM分析
            response = call_auxiliary_api_with_retry(prompt, "task_analysis", store_context=False)

            if response:
                try:
                    # 尝试解析JSON响应
                    if response.startswith('```json'):
                        response = response.replace('```json', '').replace('```', '').strip()
                    elif response.startswith('```'):
                        response = response.replace('```', '').strip()

                    analysis_result = json.loads(response)

                    # 更新数据库中的任务优先级和紧急度
                    for task_analysis in analysis_result.get("task_analysis", []):
                        task_id = tasks[task_analysis["task_id"] - 1]["id"]  # 转换为实际ID
                        self._update_task_priority_urgency(
                            task_id,
                            task_analysis.get("priority", 3),
                            task_analysis.get("urgency", 3)
                        )

                    logger.info(f"LLM任务分析成功: {len(tasks)} 个任务")
                    return analysis_result

                except json.JSONDecodeError as e:
                    logger.warning(f"解析LLM响应失败: {e}")
                    return self._get_default_task_analysis(tasks)

            else:
                logger.warning("LLM分析无响应，使用默认分析")
                return self._get_default_task_analysis(tasks)

        except Exception as e:
            logger.error(f"LLM任务分析失败: {e}")
            return self._get_default_task_analysis(tasks)

    def _update_task_priority_urgency(self, task_id: int, priority: int, urgency: int):
        """更新任务的优先级和紧急度"""
        try:
            success = self.db_manager.update_task_priority_urgency(task_id, priority, urgency)
            if success:
                logger.info(f"任务 {task_id} 优先级更新成功: 优先级: {priority}, 紧急度: {urgency}")
            else:
                logger.error(f"任务 {task_id} 优先级更新失败")
        except Exception as e:
            logger.error(f"更新任务优先级失败: {e}")

    def _get_default_task_analysis(self, tasks: List[Dict]) -> Dict:
        """获取默认任务分析结果"""
        task_analysis = []
        for i, task in enumerate(tasks):
            # 基于任务内容的简单分析
            priority = 3
            urgency = 3

            content = task['content'].lower()

            # 简单的关键词判断
            if any(word in content for word in ["重要", "紧急", "急", "马上", "立即"]):
                priority = 4
                urgency = 4
            elif any(word in content for word in ["简单", "小事", "随便"]):
                priority = 2
                urgency = 2

            # 根据优先级和紧急度分类
            if priority >= 4 and urgency >= 4:
                quadrant = "重要紧急"
            elif priority >= 4 and urgency < 4:
                quadrant = "重要不紧急"
            elif priority < 4 and urgency >= 4:
                quadrant = "不重要紧急"
            else:
                quadrant = "不重要不紧急"

            task_analysis.append({
                "task_id": i + 1,
                "content": task['content'],
                "priority": priority,
                "urgency": urgency,
                "quadrant": quadrant
            })

        return {
            "task_analysis": task_analysis,
            "summary": f"分析了 {len(tasks)} 个任务，使用默认规则进行分类"
        }

    def format_tasks_summary(self, tasks: List[Dict], include_details: bool = True) -> str:
        """格式化任务摘要"""
        try:
            if not tasks:
                return "📝 暂无任务记录"

            summary_parts = [f"📝 任务总数: {len(tasks)}"]

            # 按状态统计
            status_count = {}
            for task in tasks:
                status = task['status']
                status_count[status] = status_count.get(status, 0) + 1

            status_mapping = {
                TaskStatus.PENDING: "待处理",
                TaskStatus.IN_PROGRESS: "进行中",
                TaskStatus.COMPLETED: "已完成",
                TaskStatus.CANCELLED: "已取消"
            }

            for status, count in status_count.items():
                status_name = status_mapping.get(status, status)
                summary_parts.append(f"  • {status_name}: {count}")

            if include_details:
                summary_parts.append("\n📋 任务详情:")
                for i, task in enumerate(tasks[:10], 1):  # 最多显示10个
                    status_icon = {
                        TaskStatus.PENDING: "⏳",
                        TaskStatus.IN_PROGRESS: "🔄",
                        TaskStatus.COMPLETED: "✅",
                        TaskStatus.CANCELLED: "❌"
                    }.get(task['status'], "❓")

                    task_line = f"{i}. {status_icon} {task['content'][:50]}"
                    if len(task['content']) > 50:
                        task_line += "..."

                    summary_parts.append(task_line)

                if len(tasks) > 10:
                    summary_parts.append(f"... 还有 {len(tasks) - 10} 个任务")

            return "\n".join(summary_parts)

        except Exception as e:
            logger.error(f"格式化任务摘要失败: {e}")
            return "任务摘要生成失败"

# 全局任务管理器实例
task_manager = None

def get_task_manager() -> TaskManager:
    """获取任务管理器实例（单例模式）"""
    global task_manager
    if task_manager is None:
        task_manager = TaskManager()
    return task_manager

def process_task_message(message: str, user_id: str, group_name: str) -> Tuple[bool, str, List[int]]:
    """
    处理任务相关消息

    Returns:
        (是否为任务消息, 响应消息, 任务ID列表)
    """
    try:
        if not ENABLE_TASK_MANAGEMENT:
            return False, "", []

        tm = get_task_manager()

        # 检查是否为任务记录群
        if not tm.is_task_record_group(group_name):
            return False, "", []

        # 检查是否为任务完成消息
        completion_results = tm.parse_task_completion(message, user_id, group_name)
        if completion_results:
            updated_tasks = []
            for task_id, status in completion_results:
                if tm.update_task_status(task_id, status):
                    updated_tasks.append(task_id)

            if updated_tasks:
                status_text = "完成" if status == TaskStatus.COMPLETED else "取消"
                return True, f"✅ 已{status_text} {len(updated_tasks)} 个任务", updated_tasks

        # 尝试提取新任务
        new_tasks = tm.extract_task_from_message(message, user_id, group_name)
        if new_tasks:
            saved_task_ids = []
            for task in new_tasks:
                task_id = tm.save_task_to_db(task)
                if task_id > 0:
                    saved_task_ids.append(task_id)

            if saved_task_ids:
                return True, f"📝 已记录 {len(saved_task_ids)} 个新任务", saved_task_ids

        return False, "", []

    except Exception as e:
        logger.error(f"处理任务消息失败: {e}")
        return False, f"处理任务时发生错误: {str(e)}", []

def get_task_summary(group_name: str, status: str = None) -> str:
    """获取任务摘要"""
    try:
        tm = get_task_manager()
        tasks = tm.get_tasks_by_group(group_name, status)
        return tm.format_tasks_summary(tasks)
    except Exception as e:
        logger.error(f"获取任务摘要失败: {e}")
        return "获取任务摘要失败"

if __name__ == "__main__":
    # 测试代码
    print("测试任务管理模块...")

    tm = TaskManager()

    # 测试任务提取
    test_messages = [
        "明天要完成项目报告",
        "记得下周开会",
        "需要联系客户确认需求",
        "这个任务完成了",
        "普通聊天消息"
    ]

    for msg in test_messages:
        tasks = tm.extract_task_from_message(msg, "test_user", "任务记录群")
        print(f"消息: {msg} -> 任务数: {len(tasks)}")

    print("任务管理模块测试完成")