# -*- coding: utf-8 -*-

"""
数据库模块 - 处理文件收藏和任务记录的数据存储
Database module for file collection and task management
"""

import sqlite3
import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import threading

# 设置日志
logger = logging.getLogger(__name__)

# 数据库文件路径
DB_PATH = "data"
FILE_COLLECTION_DB = os.path.join(DB_PATH, "file_collections.db")
TASK_RECORDS_DB = os.path.join(DB_PATH, "task_records.db")

# 线程锁
db_lock = threading.RLock()

@dataclass
class FileRecord:
    """文件记录数据类"""
    id: Optional[int] = None
    file_path: str = ""
    file_name: str = ""
    file_type: str = ""
    upload_time: str = ""
    user_id: str = ""
    group_name: str = ""
    storage_path: str = ""

@dataclass
class TagRecord:
    """标签记录数据类"""
    id: Optional[int] = None
    file_id: int = 0
    tag_type: str = ""
    tag_value: str = ""
    confidence: float = 0.0

@dataclass
class TaskRecord:
    """任务记录数据类"""
    id: Optional[int] = None
    content: str = ""
    user_id: str = ""
    group_name: str = ""
    create_time: str = ""
    status: str = "pending"  # pending, completed, cancelled
    priority: int = 3  # 1-5
    urgency: int = 3   # 1-5
    completion_time: Optional[str] = None
    archived: bool = False
    details: str = ""  # 补充细节

class DatabaseManager:
    """数据库管理器"""

    def __init__(self):
        self.ensure_db_directory()
        self.init_databases()

    def ensure_db_directory(self):
        """确保数据库目录存在"""
        if not os.path.exists(DB_PATH):
            os.makedirs(DB_PATH)
            logger.info(f"创建数据库目录: {DB_PATH}")

    def init_databases(self):
        """初始化数据库表"""
        with db_lock:
            self._init_file_collection_db()
            self._init_task_records_db()

    def _init_file_collection_db(self):
        """初始化文件收藏数据库"""
        conn = sqlite3.connect(FILE_COLLECTION_DB)
        try:
            cursor = conn.cursor()

            # 创建文件表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                upload_time TEXT NOT NULL,
                user_id TEXT NOT NULL,
                group_name TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # 创建标签表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                tag_type TEXT NOT NULL,
                tag_value TEXT NOT NULL,
                confidence REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
            )
            ''')

            # 创建索引以提高查询性能
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_user_id ON files (user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_group_name ON files (group_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_file_type ON files (file_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tags_file_id ON tags (file_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tags_type_value ON tags (tag_type, tag_value)')

            conn.commit()
            logger.info("文件收藏数据库初始化完成")

        except Exception as e:
            logger.error(f"初始化文件收藏数据库失败: {e}")
            conn.rollback()
        finally:
            conn.close()

    def _init_task_records_db(self):
        """初始化任务记录数据库"""
        conn = sqlite3.connect(TASK_RECORDS_DB)
        try:
            cursor = conn.cursor()

            # 创建任务表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                user_id TEXT NOT NULL,
                group_name TEXT NOT NULL,
                create_time TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 3,
                urgency INTEGER DEFAULT 3,
                completion_time TEXT,
                archived BOOLEAN DEFAULT 0,
                details TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # 创建复盘记录表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name TEXT NOT NULL,
                review_date TEXT NOT NULL,
                task_count INTEGER DEFAULT 0,
                completed_count INTEGER DEFAULT 0,
                review_content TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks (user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_group_name ON tasks (group_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_create_time ON tasks (create_time)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_reviews_group_date ON reviews (group_name, review_date)')

            conn.commit()
            logger.info("任务记录数据库初始化完成")

        except Exception as e:
            logger.error(f"初始化任务记录数据库失败: {e}")
            conn.rollback()
        finally:
            conn.close()

    # 文件收藏相关方法
    def save_file_record(self, file_record: FileRecord) -> int:
        """保存文件记录，返回文件ID"""
        with db_lock:
            conn = sqlite3.connect(FILE_COLLECTION_DB)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                INSERT INTO files (file_path, file_name, file_type, upload_time,
                                 user_id, group_name, storage_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (file_record.file_path, file_record.file_name, file_record.file_type,
                     file_record.upload_time, file_record.user_id, file_record.group_name,
                     file_record.storage_path))

                file_id = cursor.lastrowid
                conn.commit()
                logger.info(f"保存文件记录成功: {file_record.file_name}, ID: {file_id}")
                return file_id

            except Exception as e:
                logger.error(f"保存文件记录失败: {e}")
                conn.rollback()
                return -1
            finally:
                conn.close()

    def save_tags(self, file_id: int, tags: List[TagRecord]) -> bool:
        """保存标签记录"""
        with db_lock:
            conn = sqlite3.connect(FILE_COLLECTION_DB)
            try:
                cursor = conn.cursor()
                for tag in tags:
                    cursor.execute('''
                    INSERT INTO tags (file_id, tag_type, tag_value, confidence)
                    VALUES (?, ?, ?, ?)
                    ''', (file_id, tag.tag_type, tag.tag_value, tag.confidence))

                conn.commit()
                logger.info(f"保存标签成功: 文件ID {file_id}, {len(tags)} 个标签")
                return True

            except Exception as e:
                logger.error(f"保存标签失败: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()

    def search_files(self, query: str, user_id: str = None) -> List[Dict]:
        """搜索文件"""
        with db_lock:
            conn = sqlite3.connect(FILE_COLLECTION_DB)
            try:
                cursor = conn.cursor()

                # 构建搜索SQL
                base_sql = '''
                SELECT DISTINCT f.id, f.file_name, f.file_type, f.upload_time,
                       f.user_id, f.group_name, f.storage_path
                FROM files f
                LEFT JOIN tags t ON f.id = t.file_id
                WHERE (f.file_name LIKE ? OR t.tag_value LIKE ?)
                '''

                params = [f'%{query}%', f'%{query}%']

                if user_id:
                    base_sql += ' AND f.user_id = ?'
                    params.append(user_id)

                base_sql += ' ORDER BY f.upload_time DESC'

                cursor.execute(base_sql, params)
                results = cursor.fetchall()

                # 转换为字典格式
                files = []
                for row in results:
                    files.append({
                        'id': row[0],
                        'file_name': row[1],
                        'file_type': row[2],
                        'upload_time': row[3],
                        'user_id': row[4],
                        'group_name': row[5],
                        'storage_path': row[6]
                    })

                logger.info(f"搜索文件完成: 查询'{query}', 找到{len(files)}个结果")
                return files

            except Exception as e:
                logger.error(f"搜索文件失败: {e}")
                return []
            finally:
                conn.close()

    def get_file_tags(self, file_id: int) -> List[Dict]:
        """获取文件标签"""
        with db_lock:
            conn = sqlite3.connect(FILE_COLLECTION_DB)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                SELECT tag_type, tag_value, confidence
                FROM tags
                WHERE file_id = ?
                ORDER BY tag_type, confidence DESC
                ''', (file_id,))

                results = cursor.fetchall()
                tags = []
                for row in results:
                    tags.append({
                        'type': row[0],
                        'value': row[1],
                        'confidence': row[2]
                    })

                return tags

            except Exception as e:
                logger.error(f"获取文件标签失败: {e}")
                return []
            finally:
                conn.close()

    # 任务记录相关方法
    def save_task(self, task: TaskRecord) -> int:
        """保存任务记录，返回任务ID"""
        with db_lock:
            conn = sqlite3.connect(TASK_RECORDS_DB)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                INSERT INTO tasks (content, user_id, group_name, create_time, status,
                                 priority, urgency, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (task.content, task.user_id, task.group_name, task.create_time,
                     task.status, task.priority, task.urgency, task.details))

                task_id = cursor.lastrowid
                conn.commit()
                logger.info(f"保存任务成功: {task.content[:50]}..., ID: {task_id}")
                return task_id

            except Exception as e:
                logger.error(f"保存任务失败: {e}")
                conn.rollback()
                return -1
            finally:
                conn.close()

    def update_task_status(self, task_id: int, status: str, completion_time: str = None) -> bool:
        """更新任务状态"""
        with db_lock:
            conn = sqlite3.connect(TASK_RECORDS_DB)
            try:
                cursor = conn.cursor()
                if completion_time:
                    cursor.execute('''
                    UPDATE tasks
                    SET status = ?, completion_time = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    ''', (status, completion_time, task_id))
                else:
                    cursor.execute('''
                    UPDATE tasks
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    ''', (status, task_id))

                conn.commit()
                logger.info(f"更新任务状态成功: ID {task_id}, 状态: {status}")
                return True

            except Exception as e:
                logger.error(f"更新任务状态失败: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()

    def update_task_priority_urgency(self, task_id: int, priority: int, urgency: int) -> bool:
        """更新任务的优先级和紧急度"""
        with db_lock:
            conn = sqlite3.connect(TASK_RECORDS_DB)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                UPDATE tasks
                SET priority = ?, urgency = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''', (priority, urgency, task_id))

                conn.commit()
                logger.info(f"更新任务优先级成功: ID {task_id}, 优先级: {priority}, 紧急度: {urgency}")
                return True

            except Exception as e:
                logger.error(f"更新任务优先级失败: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()

    def get_tasks_by_group(self, group_name: str, status: str = None,
                          include_archived: bool = False) -> List[Dict]:
        """获取群组任务"""
        with db_lock:
            conn = sqlite3.connect(TASK_RECORDS_DB)
            try:
                cursor = conn.cursor()

                sql = 'SELECT * FROM tasks WHERE group_name = ?'
                params = [group_name]

                if status:
                    sql += ' AND status = ?'
                    params.append(status)

                if not include_archived:
                    sql += ' AND archived = 0'

                sql += ' ORDER BY create_time DESC'

                cursor.execute(sql, params)
                results = cursor.fetchall()

                # 获取列名
                columns = [description[0] for description in cursor.description]

                # 转换为字典格式
                tasks = []
                for row in results:
                    task_dict = dict(zip(columns, row))
                    tasks.append(task_dict)

                return tasks

            except Exception as e:
                logger.error(f"获取群组任务失败: {e}")
                return []
            finally:
                conn.close()

    def search_tasks_by_content(self, query: str, group_name: str = None) -> List[Dict]:
        """根据内容搜索任务"""
        with db_lock:
            conn = sqlite3.connect(TASK_RECORDS_DB)
            try:
                cursor = conn.cursor()

                sql = 'SELECT * FROM tasks WHERE content LIKE ?'
                params = [f'%{query}%']

                if group_name:
                    sql += ' AND group_name = ?'
                    params.append(group_name)

                sql += ' ORDER BY create_time DESC'

                cursor.execute(sql, params)
                results = cursor.fetchall()

                # 获取列名
                columns = [description[0] for description in cursor.description]

                # 转换为字典格式
                tasks = []
                for row in results:
                    task_dict = dict(zip(columns, row))
                    tasks.append(task_dict)

                return tasks

            except Exception as e:
                logger.error(f"搜索任务失败: {e}")
                return []
            finally:
                conn.close()

    def archive_completed_tasks(self, group_name: str = None) -> int:
        """归档已完成任务，返回归档数量"""
        with db_lock:
            conn = sqlite3.connect(TASK_RECORDS_DB)
            try:
                cursor = conn.cursor()

                sql = "UPDATE tasks SET archived = 1 WHERE status IN ('completed', 'cancelled')"
                params = []

                if group_name:
                    sql += " AND group_name = ?"
                    params.append(group_name)

                cursor.execute(sql, params)
                archived_count = cursor.rowcount
                conn.commit()

                logger.info(f"归档任务完成: {archived_count} 个任务")
                return archived_count

            except Exception as e:
                logger.error(f"归档任务失败: {e}")
                conn.rollback()
                return 0
            finally:
                conn.close()

    def save_review_record(self, group_name: str, review_date: str,
                          task_count: int, completed_count: int,
                          review_content: str = "") -> bool:
        """保存复盘记录"""
        with db_lock:
            conn = sqlite3.connect(TASK_RECORDS_DB)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                INSERT INTO reviews (group_name, review_date, task_count,
                                   completed_count, review_content)
                VALUES (?, ?, ?, ?, ?)
                ''', (group_name, review_date, task_count, completed_count, review_content))

                conn.commit()
                logger.info(f"保存复盘记录成功: {group_name}, {review_date}")
                return True

            except Exception as e:
                logger.error(f"保存复盘记录失败: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()

# 全局数据库管理器实例
db_manager = None

def get_db_manager() -> DatabaseManager:
    """获取数据库管理器实例（单例模式）"""
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager

def init_database():
    """初始化数据库（在程序启动时调用）"""
    get_db_manager()
    logger.info("数据库模块初始化完成")

if __name__ == "__main__":
    # 测试代码
    print("测试数据库模块...")
    init_database()

    # 测试文件记录
    file_record = FileRecord(
        file_path="/test/file.pdf",
        file_name="test.pdf",
        file_type="document",
        upload_time="2024-01-01 10:00:00",
        user_id="test_user",
        group_name="test_group",
        storage_path="/storage/test.pdf"
    )

    dm = get_db_manager()
    file_id = dm.save_file_record(file_record)
    print(f"保存文件记录: ID = {file_id}")

    # 测试标签
    tags = [
        TagRecord(file_id=file_id, tag_type="客户", tag_value="测试客户", confidence=0.9),
        TagRecord(file_id=file_id, tag_type="类型", tag_value="技术文档", confidence=0.8)
    ]
    dm.save_tags(file_id, tags)

    # 测试搜索
    results = dm.search_files("测试")
    print(f"搜索结果: {len(results)} 个文件")

    print("数据库模块测试完成")