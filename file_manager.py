# -*- coding: utf-8 -*-

"""
文件管理模块 - 处理文件收藏、标签生成和存储
File management module for file collection, tagging and storage
"""

import os
import json
import shutil
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import mimetypes
import hashlib

from config import *
from database import get_db_manager, FileRecord, TagRecord

logger = logging.getLogger(__name__)

class FileManager:
    """文件管理器"""

    def __init__(self):
        self.db_manager = get_db_manager()
        self.ensure_storage_directory()

    def ensure_storage_directory(self):
        """确保存储目录存在"""
        if not os.path.exists(FILE_COLLECTION_PATH):
            os.makedirs(FILE_COLLECTION_PATH)
            logger.info(f"创建文件收藏目录: {FILE_COLLECTION_PATH}")

        # 创建分类子目录
        categories = ["客户文档", "技术文档", "合同协议", "产品资料", "会议记录", "图片资料", "其他"]
        for category in categories:
            category_path = os.path.join(FILE_COLLECTION_PATH, category)
            if not os.path.exists(category_path):
                os.makedirs(category_path)

    def get_file_type(self, file_path: str) -> str:
        """获取文件类型"""
        _, ext = os.path.splitext(file_path.lower())

        if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
            return 'image'
        elif ext in ['.pdf']:
            return 'pdf'
        elif ext in ['.doc', '.docx']:
            return 'word'
        elif ext in ['.xls', '.xlsx']:
            return 'excel'
        elif ext in ['.ppt', '.pptx']:
            return 'powerpoint'
        elif ext in ['.txt']:
            return 'text'
        else:
            return 'other'

    def is_supported_file(self, file_path: str) -> bool:
        """Return True when the file extension is allowed.
        The config entry may be a list or a comma-separated string."""
        _, ext = os.path.splitext(file_path.lower())
        if not ext:
            return False

        raw_types = SUPPORTED_FILE_TYPES
        if isinstance(raw_types, str):
            cleaned = raw_types.replace('\n', ',').replace(';', ',')
            candidates = [item.strip() for item in cleaned.split(',') if item.strip()]
        elif isinstance(raw_types, (list, tuple, set)):
            candidates = list(raw_types)
        else:
            candidates = [str(raw_types)]

        normalized = set()
        for item in candidates:
            if not item:
                continue
            lowered = item.lower().strip()
            if not lowered:
                continue
            if not lowered.startswith('.'):
                lowered = '.' + lowered.lstrip('.')
            normalized.add(lowered)

        return ext in normalized

    def get_file_size_mb(self, file_path: str) -> float:
        """获取文件大小(MB)"""
        try:
            size_bytes = os.path.getsize(file_path)
            return size_bytes / (1024 * 1024)
        except Exception as e:
            logger.error(f"获取文件大小失败: {e}")
            return 0

    def generate_file_hash(self, file_path: str) -> str:
        """生成文件哈希值用于去重"""
        try:
            hash_obj = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except Exception as e:
            logger.error(f"生成文件哈希失败: {e}")
            return ""

    def analyze_file_with_llm(self, file_path: str, file_type: str) -> Dict:
        """使用LLM分析文件内容生成标签"""
        try:
            # 导入LLM调用函数（避免循环导入）
            from bot import call_auxiliary_api_with_retry

            # 根据文件类型准备不同的分析内容
            if file_type == 'image':
                # 对于图片，使用图片识别功能
                from bot import recognize_image_with_moonshot
                image_content = recognize_image_with_moonshot(file_path, is_emoji=False)
                if not image_content:
                    image_content = "无法识别图片内容"

                analysis_text = f"图片文件分析：\n文件名: {os.path.basename(file_path)}\n识别内容: {image_content}"

            elif file_type in ['text', 'pdf']:
                # 对于文档，读取部分内容
                try:
                    if file_type == 'text':
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read(2000)  # 读取前2000字符
                    else:
                        # PDF文件暂时只分析文件名
                        content = f"PDF文件: {os.path.basename(file_path)}"

                    analysis_text = f"文档内容分析：\n文件名: {os.path.basename(file_path)}\n内容摘要: {content}"

                except Exception as e:
                    logger.warning(f"读取文件内容失败: {e}")
                    analysis_text = f"文件分析：\n文件名: {os.path.basename(file_path)}\n类型: {file_type}"

            else:
                # 其他文件类型，只分析文件名
                analysis_text = f"文件分析：\n文件名: {os.path.basename(file_path)}\n类型: {file_type}"

            # 调用LLM分析
            prompt = FILE_ANALYSIS_PROMPT + f"\n\n分析内容：\n{analysis_text}"

            # 使用辅助API进行分析
            response = call_auxiliary_api_with_retry(prompt, "file_analysis", store_context=False)

            if response:
                try:
                    # 尝试解析JSON响应
                    if response.startswith('```json'):
                        response = response.replace('```json', '').replace('```', '').strip()
                    elif response.startswith('```'):
                        response = response.replace('```', '').strip()

                    analysis_result = json.loads(response)
                    logger.info(f"LLM文件分析成功: {os.path.basename(file_path)}")
                    return analysis_result

                except json.JSONDecodeError as e:
                    logger.warning(f"解析LLM响应失败: {e}, 响应内容: {response}")
                    # 返回默认分析结果
                    return self._get_default_analysis(file_path, file_type)

            else:
                logger.warning("LLM分析无响应，使用默认分析")
                return self._get_default_analysis(file_path, file_type)

        except Exception as e:
            logger.error(f"LLM文件分析失败: {e}")
            return self._get_default_analysis(file_path, file_type)

    def _get_default_analysis(self, file_path: str, file_type: str) -> Dict:
        """获取默认分析结果"""
        file_name = os.path.basename(file_path)

        # 基于文件名推断基本信息
        analysis = {
            "客户": "未知",
            "内容": f"{file_type}文件",
            "日期": datetime.now().strftime("%Y-%m-%d"),
            "类型": "其他",
            "关键词": [file_name.split('.')[0]],
            "重要性": "中"
        }

        # 简单的文件名分析
        if any(keyword in file_name for keyword in ["合同", "协议", "contract"]):
            analysis["类型"] = "合同协议"
            analysis["重要性"] = "高"
        elif any(keyword in file_name for keyword in ["技术", "方案", "设计", "技术"]):
            analysis["类型"] = "技术文档"
        elif any(keyword in file_name for keyword in ["会议", "记录", "纪要"]):
            analysis["类型"] = "会议记录"
        elif file_type == 'image':
            analysis["类型"] = "图片资料"

        return analysis

    def generate_storage_path(self, file_name: str, tags: Dict) -> str:
        """根据标签生成文件存储路径"""
        try:
            # 根据文件类型选择主目录
            file_type = tags.get("类型", "其他")

            # 映射到存储目录
            type_mapping = {
                "技术文档": "技术文档",
                "合同协议": "合同协议",
                "产品资料": "产品资料",
                "会议记录": "会议记录",
                "图片资料": "图片资料",
                "客户文档": "客户文档"
            }

            main_dir = type_mapping.get(file_type, "其他")

            # 如果有客户信息，创建客户子目录
            customer = tags.get("客户", "").strip()
            if customer and customer != "未知":
                # 清理客户名称中的特殊字符
                safe_customer = "".join(c for c in customer if c.isalnum() or c in "._-")
                if safe_customer:
                    storage_dir = os.path.join(FILE_COLLECTION_PATH, main_dir, safe_customer)
                else:
                    storage_dir = os.path.join(FILE_COLLECTION_PATH, main_dir)
            else:
                storage_dir = os.path.join(FILE_COLLECTION_PATH, main_dir)

            # 确保目录存在
            if not os.path.exists(storage_dir):
                os.makedirs(storage_dir)

            # 生成唯一文件名
            base_name, ext = os.path.splitext(file_name)
            storage_path = os.path.join(storage_dir, file_name)

            # 如果文件已存在，添加序号
            counter = 1
            while os.path.exists(storage_path):
                new_name = f"{base_name}_{counter}{ext}"
                storage_path = os.path.join(storage_dir, new_name)
                counter += 1

            return storage_path

        except Exception as e:
            logger.error(f"生成存储路径失败: {e}")
            # 返回默认路径
            return os.path.join(FILE_COLLECTION_PATH, "其他", file_name)

    def save_file_with_tags(self, source_path: str, user_id: str, group_name: str,
                           custom_tags: Dict = None) -> Tuple[bool, str, int]:
        """
        保存文件并生成标签

        返回: (成功标志, 消息, 文件ID)
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(source_path):
                return False, "文件不存在", -1

            file_name = os.path.basename(source_path)

            # 检查文件类型
            if not self.is_supported_file(source_path):
                return False, f"不支持的文件类型: {file_name}", -1

            # 检查文件大小
            file_size_mb = self.get_file_size_mb(source_path)
            if file_size_mb > MAX_FILE_SIZE_MB:
                return False, f"文件过大: {file_size_mb:.1f}MB (最大{MAX_FILE_SIZE_MB}MB)", -1

            # 获取文件类型
            file_type = self.get_file_type(source_path)

            # 生成文件哈希（用于去重检查）
            file_hash = self.generate_file_hash(source_path)

            # 使用自定义标签或LLM分析
            if custom_tags:
                analysis_result = custom_tags
                logger.info(f"使用自定义标签: {file_name}")
            else:
                logger.info(f"开始LLM分析文件: {file_name}")
                analysis_result = self.analyze_file_with_llm(source_path, file_type)

            # 生成存储路径
            storage_path = self.generate_storage_path(file_name, analysis_result)

            # 复制文件到存储位置
            try:
                shutil.copy2(source_path, storage_path)
                logger.info(f"文件复制成功: {source_path} -> {storage_path}")
            except Exception as e:
                logger.error(f"文件复制失败: {e}")
                return False, f"文件保存失败: {str(e)}", -1

            # 保存文件记录
            file_record = FileRecord(
                file_path=source_path,
                file_name=file_name,
                file_type=file_type,
                upload_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                user_id=user_id,
                group_name=group_name,
                storage_path=storage_path
            )

            file_id = self.db_manager.save_file_record(file_record)
            if file_id <= 0:
                # 如果数据库保存失败，删除已复制的文件
                try:
                    os.remove(storage_path)
                except:
                    pass
                return False, "数据库保存失败", -1

            # 保存标签
            tags = []
            for tag_type, tag_value in analysis_result.items():
                if tag_value and tag_value != "未知":
                    if isinstance(tag_value, list):
                        # 处理关键词列表
                        for keyword in tag_value:
                            if keyword and keyword.strip():
                                tags.append(TagRecord(
                                    file_id=file_id,
                                    tag_type=tag_type,
                                    tag_value=keyword.strip(),
                                    confidence=0.8
                                ))
                    else:
                        tags.append(TagRecord(
                            file_id=file_id,
                            tag_type=tag_type,
                            tag_value=str(tag_value),
                            confidence=0.9
                        ))

            if tags:
                self.db_manager.save_tags(file_id, tags)

            # 生成成功消息
            success_msg = self._generate_collection_message(analysis_result, storage_path)

            logger.info(f"文件收藏成功: {file_name}, ID: {file_id}")
            return True, success_msg, file_id

        except Exception as e:
            logger.error(f"保存文件失败: {e}")
            return False, f"处理文件时发生错误: {str(e)}", -1

    def _generate_collection_message(self, analysis: Dict, storage_path: str) -> str:
        """生成收藏成功的消息"""
        try:
            msg_parts = ["✅ 文件收藏成功！"]

            # 添加标签信息
            if analysis.get("客户") and analysis["客户"] != "未知":
                msg_parts.append(f"📝 客户: {analysis['客户']}")

            if analysis.get("类型") and analysis["类型"] != "未知":
                msg_parts.append(f"📁 类型: {analysis['类型']}")

            if analysis.get("内容") and analysis["内容"] != "未知":
                msg_parts.append(f"📄 内容: {analysis['内容']}")

            if analysis.get("重要性") and analysis["重要性"] != "未知":
                msg_parts.append(f"⭐ 重要性: {analysis['重要性']}")

            # 添加关键词
            keywords = analysis.get("关键词", [])
            if keywords and isinstance(keywords, list):
                valid_keywords = [kw for kw in keywords if kw and kw != "未知"]
                if valid_keywords:
                    msg_parts.append(f"🏷️ 标签: {', '.join(valid_keywords)}")

            # 添加存储路径
            relative_path = os.path.relpath(storage_path, FILE_COLLECTION_PATH)
            msg_parts.append(f"📂 路径: {relative_path}")

            msg_parts.append("\n如需修改标签，请继续描述调整要求。")

            return "\n".join(msg_parts)

        except Exception as e:
            logger.error(f"生成收藏消息失败: {e}")
            return "文件收藏成功！"

    def update_file_tags(self, file_id: int, new_tags: Dict) -> bool:
        """更新文件标签"""
        try:
            # 先删除旧标签
            # 这里简化处理，实际可以增加更精细的标签更新逻辑

            # 保存新标签
            tags = []
            for tag_type, tag_value in new_tags.items():
                if tag_value and tag_value != "未知":
                    if isinstance(tag_value, list):
                        for keyword in tag_value:
                            if keyword and keyword.strip():
                                tags.append(TagRecord(
                                    file_id=file_id,
                                    tag_type=tag_type,
                                    tag_value=keyword.strip(),
                                    confidence=0.8
                                ))
                    else:
                        tags.append(TagRecord(
                            file_id=file_id,
                            tag_type=tag_type,
                            tag_value=str(tag_value),
                            confidence=0.9
                        ))

            if tags:
                self.db_manager.save_tags(file_id, tags)
                logger.info(f"更新文件标签成功: 文件ID {file_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"更新文件标签失败: {e}")
            return False

    def get_file_info(self, file_id: int) -> Optional[Dict]:
        """获取文件详细信息"""
        try:
            # 这里需要扩展数据库方法来获取单个文件信息
            # 暂时返回None，后续可以完善
            return None
        except Exception as e:
            logger.error(f"获取文件信息失败: {e}")
            return None

    def delete_file(self, file_id: int) -> bool:
        """删除文件（同时删除存储文件和数据库记录）"""
        try:
            # 获取文件信息
            file_info = self.get_file_info(file_id)
            if not file_info:
                return False

            # 删除存储文件
            storage_path = file_info.get('storage_path')
            if storage_path and os.path.exists(storage_path):
                os.remove(storage_path)

            # 删除数据库记录（包括标签，由于外键约束会自动删除）
            # 这里需要扩展数据库方法

            logger.info(f"删除文件成功: ID {file_id}")
            return True

        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return False

# 全局文件管理器实例
file_manager = None

def get_file_manager() -> FileManager:
    """获取文件管理器实例（单例模式）"""
    global file_manager
    if file_manager is None:
        file_manager = FileManager()
    return file_manager

def process_file_collection_request(file_path: str, user_id: str, group_name: str,
                                  custom_request: str = None) -> Tuple[bool, str]:
    """
    处理文件收藏请求

    Args:
        file_path: 文件路径
        user_id: 用户ID
        group_name: 群组名称
        custom_request: 用户的自定义要求

    Returns:
        (是否成功, 响应消息)
    """
    try:
        if not ENABLE_FILE_COLLECTION:
            return False, "文件收藏功能未启用"

        fm = get_file_manager()

        # 如果有自定义要求，使用LLM解析
        custom_tags = None
        if custom_request:
            # 这里可以添加解析自定义要求的逻辑
            logger.info(f"用户自定义要求: {custom_request}")

        # 保存文件
        success, message, file_id = fm.save_file_with_tags(
            file_path, user_id, group_name, custom_tags
        )

        return success, message

    except Exception as e:
        logger.error(f"处理文件收藏请求失败: {e}")
        return False, f"处理文件时发生错误: {str(e)}"

if __name__ == "__main__":
    # 测试代码
    print("测试文件管理模块...")

    # 测试文件类型检测
    fm = FileManager()
    test_files = ["test.pdf", "demo.jpg", "doc.docx"]

    for file in test_files:
        file_type = fm.get_file_type(file)
        is_supported = fm.is_supported_file(file)
        print(f"{file}: 类型={file_type}, 支持={is_supported}")

    print("文件管理模块测试完成")