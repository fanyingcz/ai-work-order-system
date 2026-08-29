"""
用户输入处理模块 - 包初始化文件

【模块职责】
负责接收用户的原始输入，通过 DeepSeek 大模型两步处理：
1. 第一步：判断用户输入是否包含"问题描述 + 地址"，若缺失则要求补充
2. 第二步：将正式化表述与 category.json 中的 problem 字段进行匹配

【核心功能】
1. 多用户会话管理，每个用户独立上下文，互不干扰
2. 每个会话拥有独立的线程锁，保证并发安全
3. 15 分钟超时自动清理不活跃会话
4. 支持交互式补充信息（多轮对话）
5. 支持从 JSON 文件批量处理
6. 提取地址信息供后续模块使用
7. 会话生命周期管理：ACTIVE → COMPLETED → PERSISTED

【模块结构】
├── models.py         # 数据模型定义（UserInput, ProcessedInput, InputProcessingResult, UserSession）
├── processor.py      # 核心处理逻辑（SessionManager, InputProcessor 类）
├── prompt_manager.py # 提示词管理器（PromptManager），从 JSON 加载/修改提示词
└── __init__.py       # 模块导出声明

【对外接口】
- UserSession: 用户会话数据模型
- UserInput: 用户输入数据模型
- ProcessedInput: 处理后的输入数据模型
- InputProcessingResult: 输入处理结果封装类
- SessionManager: 用户会话管理器
- InputProcessor: 用户输入处理器，提供以下方法：
  - process_user_input(user_id, user_input): 处理用户输入
  - check_session_status(user_id): 检查会话状态
  - cancel_session(user_id): 取消会话
  - confirm_persisted(user_id): 确认数据已持久化，删除会话
  - get_completed_session_data(user_id): 获取已完成会话的数据
"""

from .models import UserInput, ProcessedInput, InputProcessingResult, UserSession
from .processor import InputProcessor, SessionManager, process_user_input_wrapper
from .prompt_manager import PromptManager, get_prompt_manager

__all__ = [
    'UserInput', 'ProcessedInput', 'InputProcessingResult', 'UserSession',
    'InputProcessor', 'SessionManager', 'process_user_input_wrapper',
    'PromptManager', 'get_prompt_manager'
]
