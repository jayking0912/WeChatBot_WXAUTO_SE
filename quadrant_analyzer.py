# -*- coding: utf-8 -*-

"""
四象限分析模块 - 生成任务优先级四象限图表
Quadrant analysis module for generating task priority quadrant charts
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.font_manager import FontProperties
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io

from config import *
from task_manager import get_task_manager

logger = logging.getLogger(__name__)

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']  # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

class QuadrantAnalyzer:
    """四象限分析器"""

    def __init__(self):
        self.task_manager = get_task_manager()
        self.colors = {
            'urgent_important': '#FF6B6B',      # 红色 - 紧急重要
            'not_urgent_important': '#4ECDC4',   # 青色 - 重要不紧急
            'urgent_not_important': '#FFE66D',   # 黄色 - 紧急不重要
            'not_urgent_not_important': '#95E1D3' # 绿色 - 不紧急不重要
        }

    def analyze_task_priority_urgency(self, tasks: List[Dict]) -> Dict:
        """分析任务的重要性和紧急度"""
        try:
            if not tasks:
                return {"task_analysis": [], "summary": "没有任务需要分析"}

            # 使用任务管理器的LLM分析功能
            analysis_result = self.task_manager.analyze_tasks_with_llm(tasks)

            logger.info(f"四象限分析完成: {len(tasks)} 个任务")
            return analysis_result

        except Exception as e:
            logger.error(f"任务优先级分析失败: {e}")
            return {"task_analysis": [], "summary": f"分析失败: {str(e)}"}

    def categorize_tasks_by_quadrant(self, task_analysis: List[Dict]) -> Dict[str, List[Dict]]:
        """将任务按四象限分类"""
        quadrants = {
            'urgent_important': [],      # 第一象限：重要且紧急
            'not_urgent_important': [],  # 第二象限：重要但不紧急
            'urgent_not_important': [],  # 第三象限：不重要但紧急
            'not_urgent_not_important': [] # 第四象限：不重要且不紧急
        }

        for task in task_analysis:
            priority = task.get('priority', 3)
            urgency = task.get('urgency', 3)

            if priority >= 4 and urgency >= 4:
                quadrants['urgent_important'].append(task)
            elif priority >= 4 and urgency < 4:
                quadrants['not_urgent_important'].append(task)
            elif priority < 4 and urgency >= 4:
                quadrants['urgent_not_important'].append(task)
            else:
                quadrants['not_urgent_not_important'].append(task)

        return quadrants

    def generate_quadrant_chart(self, task_analysis: List[Dict],
                              title: str = "任务优先级四象限图") -> str:
        """生成四象限图表，返回图片路径"""
        try:
            # 确保输出目录存在
            output_dir = "charts"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            chart_path = os.path.join(output_dir, f"quadrant_chart_{timestamp}.png")

            # 分类任务
            quadrants = self.categorize_tasks_by_quadrant(task_analysis)

            # 创建图表
            fig, ax = plt.subplots(figsize=(12, 10))

            # 设置坐标轴
            ax.set_xlim(0, 10)
            ax.set_ylim(0, 10)
            ax.set_xlabel('紧急度 (Urgency)', fontsize=14, fontweight='bold')
            ax.set_ylabel('重要性 (Importance)', fontsize=14, fontweight='bold')
            ax.set_title(title, fontsize=16, fontweight='bold', pad=20)

            # 绘制四象限分割线
            ax.axhline(y=5, color='black', linewidth=2, alpha=0.7)
            ax.axvline(x=5, color='black', linewidth=2, alpha=0.7)

            # 绘制四象限背景色
            quadrant_rects = [
                patches.Rectangle((5, 5), 5, 5, facecolor=self.colors['urgent_important'], alpha=0.3),
                patches.Rectangle((0, 5), 5, 5, facecolor=self.colors['not_urgent_important'], alpha=0.3),
                patches.Rectangle((5, 0), 5, 5, facecolor=self.colors['urgent_not_important'], alpha=0.3),
                patches.Rectangle((0, 0), 5, 5, facecolor=self.colors['not_urgent_not_important'], alpha=0.3)
            ]

            for rect in quadrant_rects:
                ax.add_patch(rect)

            # 添加象限标签
            quadrant_labels = [
                (7.5, 7.5, '重要紧急\n(立即行动)', self.colors['urgent_important']),
                (2.5, 7.5, '重要不紧急\n(计划执行)', self.colors['not_urgent_important']),
                (7.5, 2.5, '不重要紧急\n(委托他人)', self.colors['urgent_not_important']),
                (2.5, 2.5, '不重要不紧急\n(减少投入)', self.colors['not_urgent_not_important'])
            ]

            for x, y, label, color in quadrant_labels:
                ax.text(x, y, label, ha='center', va='center', fontsize=12,
                       fontweight='bold', bbox=dict(boxstyle="round,pad=0.3",
                       facecolor=color, alpha=0.8))

            # 绘制任务点
            for task in task_analysis:
                x = min(max(task.get('urgency', 3) * 2, 0.5), 9.5)  # 映射到0.5-9.5
                y = min(max(task.get('priority', 3) * 2, 0.5), 9.5)  # 映射到0.5-9.5

                # 根据象限选择颜色
                if x >= 5 and y >= 5:
                    color = self.colors['urgent_important']
                elif x < 5 and y >= 5:
                    color = self.colors['not_urgent_important']
                elif x >= 5 and y < 5:
                    color = self.colors['urgent_not_important']
                else:
                    color = self.colors['not_urgent_not_important']

                # 绘制任务点
                ax.scatter(x, y, c=color, s=100, alpha=0.8, edgecolors='black', linewidth=1)

                # 添加任务标号
                task_num = task.get('task_id', 1)
                ax.text(x, y, str(task_num), ha='center', va='center',
                       fontsize=10, fontweight='bold', color='white')

            # 设置网格
            ax.grid(True, alpha=0.3)
            ax.set_xticks(range(0, 11, 1))
            ax.set_yticks(range(0, 11, 1))

            # 调整布局并保存
            plt.tight_layout()
            plt.savefig(chart_path, dpi=300, bbox_inches='tight',
                       facecolor='white', edgecolor='none')
            plt.close()

            logger.info(f"四象限图表生成成功: {chart_path}")
            return chart_path

        except Exception as e:
            logger.error(f"生成四象限图表失败: {e}")
            return ""

    def create_task_summary_image(self, tasks: List[Dict], analysis: Dict,
                                chart_path: str) -> str:
        """创建包含任务列表和图表的综合图片"""
        try:
            if not chart_path or not os.path.exists(chart_path):
                logger.error("图表文件不存在")
                return ""

            # 确保输出目录存在
            output_dir = "charts"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_path = os.path.join(output_dir, f"task_summary_{timestamp}.png")

            # 创建一个更大的画布
            canvas_width = 1200
            canvas_height = 1600

            # 创建画布
            canvas = Image.new('RGB', (canvas_width, canvas_height), 'white')
            draw = ImageDraw.Draw(canvas)

            # 尝试加载中文字体
            try:
                title_font = ImageFont.truetype("simhei.ttf", 24)
                header_font = ImageFont.truetype("simhei.ttf", 18)
                content_font = ImageFont.truetype("simhei.ttf", 14)
            except:
                try:
                    title_font = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 24)
                    header_font = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 18)
                    content_font = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 14)
                except:
                    # 使用默认字体
                    title_font = ImageFont.load_default()
                    header_font = ImageFont.load_default()
                    content_font = ImageFont.load_default()

            # 绘制标题
            y_offset = 20
            draw.text((canvas_width//2, y_offset), "任务复盘报告",
                     font=title_font, fill='black', anchor="mt")
            y_offset += 50

            # 绘制日期
            current_date = datetime.now().strftime("%Y年%m月%d日")
            draw.text((canvas_width//2, y_offset), current_date,
                     font=header_font, fill='gray', anchor="mt")
            y_offset += 40

            # 绘制任务统计
            task_count = len(tasks)
            draw.text((50, y_offset), f"任务总数: {task_count}",
                     font=header_font, fill='black')
            y_offset += 30

            # 绘制四象限统计
            if 'task_analysis' in analysis:
                quadrants = self.categorize_tasks_by_quadrant(analysis['task_analysis'])

                quadrant_names = {
                    'urgent_important': '重要紧急',
                    'not_urgent_important': '重要不紧急',
                    'urgent_not_important': '不重要紧急',
                    'not_urgent_not_important': '不重要不紧急'
                }

                for quad_key, quad_name in quadrant_names.items():
                    count = len(quadrants[quad_key])
                    color = self.colors[quad_key]

                    # 绘制彩色方块
                    draw.rectangle([50, y_offset-2, 70, y_offset+18], fill=color)
                    draw.text((80, y_offset), f"{quad_name}: {count}个",
                             font=content_font, fill='black')
                    y_offset += 25

            y_offset += 20

            # 绘制任务列表
            draw.text((50, y_offset), "任务详情:", font=header_font, fill='black')
            y_offset += 30

            for i, task in enumerate(tasks[:15], 1):  # 最多显示15个任务
                task_text = f"{i}. {task['content'][:40]}"
                if len(task['content']) > 40:
                    task_text += "..."

                draw.text((70, y_offset), task_text, font=content_font, fill='black')
                y_offset += 20

            if len(tasks) > 15:
                draw.text((70, y_offset), f"... 还有 {len(tasks) - 15} 个任务",
                         font=content_font, fill='gray')
                y_offset += 30

            # 加载并插入四象限图表
            try:
                chart_img = Image.open(chart_path)
                # 调整图表大小
                chart_width = canvas_width - 100
                chart_height = int(chart_img.height * chart_width / chart_img.width)
                chart_img = chart_img.resize((chart_width, chart_height), Image.Resampling.LANCZOS)

                # 粘贴图表
                chart_y = min(y_offset + 20, canvas_height - chart_height - 20)
                canvas.paste(chart_img, (50, chart_y))

            except Exception as e:
                logger.warning(f"插入图表失败: {e}")

            # 保存综合图片
            canvas.save(summary_path, quality=95)

            logger.info(f"任务总结图片生成成功: {summary_path}")
            return summary_path

        except Exception as e:
            logger.error(f"创建任务总结图片失败: {e}")
            return ""

    def generate_daily_review_chart(self, group_name: str,
                                   review_date: str = None) -> Tuple[str, str, Dict]:
        """
        生成每日复盘图表

        Returns:
            (图表路径, 总结图片路径, 分析结果)
        """
        try:
            if not review_date:
                review_date = datetime.now().strftime("%Y-%m-%d")

            # 获取指定日期的任务
            tasks = self.task_manager.get_new_tasks_since_last_review(group_name)

            if not tasks:
                logger.info(f"没有找到需要复盘的任务: {group_name}")
                return "", "", {"task_analysis": [], "summary": "没有任务需要复盘"}

            # 分析任务
            analysis = self.analyze_task_priority_urgency(tasks)

            # 生成四象限图表
            chart_title = f"{group_name} - {review_date} 任务复盘"
            chart_path = self.generate_quadrant_chart(analysis.get('task_analysis', []), chart_title)

            # 生成综合总结图片
            summary_path = ""
            if chart_path:
                summary_path = self.create_task_summary_image(tasks, analysis, chart_path)

            # 保存复盘记录到数据库
            self._save_review_record(group_name, review_date, tasks, analysis)

            return chart_path, summary_path, analysis

        except Exception as e:
            logger.error(f"生成每日复盘图表失败: {e}")
            return "", "", {"task_analysis": [], "summary": f"生成失败: {str(e)}"}

    def _save_review_record(self, group_name: str, review_date: str,
                           tasks: List[Dict], analysis: Dict):
        """保存复盘记录到数据库"""
        try:
            task_count = len(tasks)
            completed_count = len([t for t in tasks if t['status'] == 'completed'])
            review_content = json.dumps(analysis, ensure_ascii=False)

            self.task_manager.db_manager.save_review_record(
                group_name, review_date, task_count, completed_count, review_content
            )

            logger.info(f"保存复盘记录成功: {group_name}, {review_date}")

        except Exception as e:
            logger.error(f"保存复盘记录失败: {e}")

    def format_analysis_text(self, analysis: Dict) -> str:
        """格式化分析结果为文本"""
        try:
            if not analysis.get('task_analysis'):
                return "没有任务需要分析"

            text_parts = ["📊 任务优先级分析结果：\n"]

            # 按象限分组
            quadrants = self.categorize_tasks_by_quadrant(analysis['task_analysis'])

            quadrant_names = {
                'urgent_important': '🔴 重要紧急 (立即行动)',
                'not_urgent_important': '🔵 重要不紧急 (计划执行)',
                'urgent_not_important': '🟡 不重要紧急 (委托他人)',
                'not_urgent_not_important': '🟢 不重要不紧急 (减少投入)'
            }

            for quad_key, quad_name in quadrant_names.items():
                tasks_in_quad = quadrants[quad_key]
                if tasks_in_quad:
                    text_parts.append(f"\n{quad_name} ({len(tasks_in_quad)}个):")
                    for task in tasks_in_quad:
                        content = task['content'][:30]
                        if len(task['content']) > 30:
                            content += "..."
                        text_parts.append(f"  • {content}")

            # 添加总结
            if analysis.get('summary'):
                text_parts.append(f"\n📝 分析总结：\n{analysis['summary']}")

            return "\n".join(text_parts)

        except Exception as e:
            logger.error(f"格式化分析文本失败: {e}")
            return "分析结果格式化失败"

# 全局四象限分析器实例
quadrant_analyzer = None

def get_quadrant_analyzer() -> QuadrantAnalyzer:
    """获取四象限分析器实例（单例模式）"""
    global quadrant_analyzer
    if quadrant_analyzer is None:
        quadrant_analyzer = QuadrantAnalyzer()
    return quadrant_analyzer

def generate_task_review_chart(group_name: str) -> Tuple[str, str, str]:
    """
    生成任务复盘图表

    Returns:
        (图表路径, 总结图片路径, 分析文本)
    """
    try:
        qa = get_quadrant_analyzer()
        chart_path, summary_path, analysis = qa.generate_daily_review_chart(group_name)
        analysis_text = qa.format_analysis_text(analysis)

        return chart_path, summary_path, analysis_text

    except Exception as e:
        logger.error(f"生成任务复盘图表失败: {e}")
        return "", "", f"生成失败: {str(e)}"

if __name__ == "__main__":
    # 测试代码
    print("测试四象限分析模块...")

    # 创建测试任务数据
    test_tasks = [
        {'id': 1, 'content': '完成紧急项目', 'status': 'pending', 'create_time': '2024-01-01 10:00:00'},
        {'id': 2, 'content': '学习新技术', 'status': 'pending', 'create_time': '2024-01-01 11:00:00'},
        {'id': 3, 'content': '回复邮件', 'status': 'completed', 'create_time': '2024-01-01 12:00:00'},
    ]

    qa = QuadrantAnalyzer()

    # 测试分析
    analysis = qa.analyze_task_priority_urgency(test_tasks)
    print(f"分析结果: {analysis}")

    # 测试图表生成
    if analysis.get('task_analysis'):
        chart_path = qa.generate_quadrant_chart(analysis['task_analysis'])
        print(f"图表路径: {chart_path}")

    print("四象限分析模块测试完成")