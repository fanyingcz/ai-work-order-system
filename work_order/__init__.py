"""
工单生成模块 - 包初始化文件

【模块职责】
负责根据各模块处理结果生成完整的维修工单，是整个报修流程的最终输出环节。

【核心功能】
1. 根据 problem 从 category.json 中获取对应的 subCategory
2. 生成唯一的维修单号（格式：WO + 年月日 + 6位序号）
3. 记录受理时间（程序当前时间）
4. 组装完整的工单数据，包括：
   - 维修单号、受理时间、报修概述、报修类型、报修项目
   - 物业公司、维修单位、优先级、所需资质证书、目标维修部门

【模块结构】
├── models.py      # 数据模型定义（WorkOrder, WorkOrderItem）
├── generator.py   # 工单生成逻辑（WorkOrderGenerator 类）
└── __init__.py    # 模块导出声明

【对外接口】
- WorkOrder: 工单数据模型
- WorkOrderItem: 工单明细项数据模型
- WorkOrderGenerator: 工单生成器，提供 generate() 和 generate_from_dict() 方法

【数据依赖】
- data/json/category.json: 维修问题分类规则，用于获取 problem 对应的 subCategory

【使用场景】
- 作为报修流程的第四步，接收各模块处理结果并生成工单
- 工单数据可存储到数据库或发送给维修调度系统
"""

from .models import WorkOrder, WorkOrderItem
from .generator import WorkOrderGenerator

__all__ = ['WorkOrder', 'WorkOrderItem', 'WorkOrderGenerator']