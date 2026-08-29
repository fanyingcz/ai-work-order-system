"""
规则引擎模块 - 包初始化文件

【模块职责】
负责根据输入的 subCategory、trigger_keywords 和可选的 trigger_location，
通过规则匹配输出对应的 problem、priority、required_cert 和 target_dept_semantic。

【核心功能】
1. 从 JSON 文件加载维修问题分类规则
2. 执行规则匹配，根据 subCategory + trigger_keywords + trigger_location
   输出对应的 problem、priority、required_cert 和 target_dept_semantic
3. 处理规则匹配不足或冲突情况

【模块结构】
├── models.py         # 数据模型定义（RuleInput, RuleOutput, StandardizedRule）
├── loader.py         # 规则加载器，从 JSON 文件加载规则
├── engine.py         # 规则引擎核心，执行规则匹配
└── __init__.py       # 模块导出声明

【对外接口】
- RuleInput: 规则输入数据模型（包含 subCategory、trigger_keywords、trigger_location）
- RuleOutput: 规则输出数据模型（包含 problem、priority、required_cert、target_dept_semantic）
- StandardizedRule: 标准化规则数据模型
- load_all_rules: 加载所有规则的函数
- RuleEngine: 规则引擎类，提供 match() 和 match_dict() 方法

【输出字段说明】
- problem: 匹配到的问题描述
- priority: 维修优先级，如"半小时到现场"、"2小时到现场"、"72小时内完成"等
- required_cert: 所需资质证书，如"电工证"、"管道工证"等
- target_dept_semantic: 目标维修部门，如"电力维修组"、"管道维修组"等

【状态标识】
- MATCHED: 规则匹配成功，返回唯一结果
- NO_MATCH: 没有匹配到任何规则
- MISSING: 匹配到多条规则，缺少 trigger_location 无法精确匹配
- CONFLICT: 三输入情况下仍匹配到多条规则，存在冲突

【数据依赖】
- data/rules/category.json: 维修问题分类规则，包含 subCategory、trigger_keywords、trigger_location
  到 problem、priority、required_cert、target_dept_semantic 的映射
"""

from .models import RuleInput, RuleOutput, StandardizedRule
from .loader import load_all_rules
from .engine import RuleEngine

__all__ = ['RuleInput', 'RuleOutput', 'StandardizedRule', 'load_all_rules', 'RuleEngine']
