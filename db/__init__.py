"""
数据库模块

负责 MySQL 数据库连接、建表、工单 CRUD 操作。
数据库: AI_Work_Order
表名: work_orders
"""

from .database import WorkOrderDB, get_db

__all__ = ['WorkOrderDB', 'get_db']