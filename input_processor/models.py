"""
用户输入处理模块 - 数据模型定义

【文件职责】
定义用户输入处理模块所需的所有数据模型，包括：
1. UserInput: 用户原始输入数据模型
2. ProcessedInput: 经过大模型处理后的输入数据模型
3. InputProcessingResult: 输入处理结果封装类
4. UserSession: 用户会话数据模型，管理多用户上下文

【核心设计：多用户会话管理】
- 每个用户拥有独立的 UserSession，通过 user_id 隔离
- 会话保存对话历史、当前步骤状态、已提取的 content 和 problem
- 支持超时清理：用户超过 15 分钟未响应则自动清除会话
- step 字段标识当前处理阶段：
  - 'initial': 初始状态，等待用户输入
  - 'awaiting_supplement': 等待用户补充缺失信息
  - 'completed': 信息已齐全，等待生成工单
- session_state 字段标识会话生命周期：
  - 'ACTIVE': 会话活跃中，正在处理用户输入
  - 'COMPLETED': 处理完成，数据已提取，等待存入数据库
  - 'PERSISTED': 数据已存入数据库，可安全删除

【设计说明】
- 数据模型采用面向对象设计，便于数据传递和类型检查
- ProcessedInput 包含处理后的核心信息（正式化文本、匹配的问题类型、地址）
- InputProcessingResult 统一封装处理状态和附加信息
- UserSession 管理多用户上下文，确保不同用户数据隔离
- 每个 UserSession 拥有独立的 threading.Lock，保证并发安全

【状态标识规范】
- SUCCESS: 处理成功
- ERROR: 处理错误（如大模型调用失败）
- MISS: 缺失必要信息
- PASS: 第一步完整性检查通过
"""

import threading
from typing import Optional, List, Dict
from datetime import datetime


class UserSession:
    """
    用户会话数据模型

    用于管理单个用户的完整对话上下文，确保多用户场景下数据隔离。
    每个会话拥有独立的线程锁，保证并发安全。

    Attributes:
        user_id (str): 用户唯一标识
        history (List[Dict[str, str]]): 对话历史消息列表
        last_active_time (datetime): 最后活动时间，用于超时检测
        content (Optional[str]): 规范化后的用户表述
        problem (Optional[str]): 匹配到的 problem 字段值（废弃，保留兼容）
        address (Optional[str]): 从输入中提取的地址信息
        prechoice_subcategories (Optional[List[str]]): 大模型选取的2个subCategory
        location (Optional[str]): 问题发生的位置（如承重墙、楼梯）
        trigger_keyword (Optional[str]): 匹配到的 trigger_keyword
        trigger_location (Optional[str]): 匹配到的 trigger_location
        reporter_name (Optional[str]): 报修人姓名（多轮对话中持久化）
        reporter_phone (Optional[str]): 报修人联系电话（多轮对话中持久化）
        step (str): 当前处理阶段
        session_state (str): 会话生命周期状态
        created_time (datetime): 会话创建时间
        _lock (threading.Lock): 线程锁
    """
    user_id: str
    history: List[Dict[str, str]]
    last_active_time: datetime
    content: Optional[str]
    problem: Optional[str]
    address: Optional[str]
    prechoice_subcategories: Optional[List[str]]
    location: Optional[str]
    trigger_keyword: Optional[str]
    trigger_location: Optional[str]
    reporter_name: Optional[str]
    reporter_phone: Optional[str]
    step: str
    session_state: str
    created_time: datetime
    _lock: threading.Lock

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.history = []
        self.last_active_time = datetime.now()
        self.content = None
        self.problem = None
        self.address = None
        self.prechoice_subcategories = None
        self.location = None
        self.trigger_keyword = None
        self.trigger_location = None
        self.reporter_name = None
        self.reporter_phone = None
        self.step = 'initial'
        self.session_state = 'ACTIVE'
        self.created_time = datetime.now()
        self._lock = threading.Lock()

    def is_timeout(self, timeout_seconds: int = 900) -> bool:
        """
        判断会话是否超时

        Args:
            timeout_seconds: 超时阈值，默认 900 秒（15 分钟）

        Returns:
            bool: 超时返回 True，否则返回 False
        """
        elapsed = (datetime.now() - self.last_active_time).total_seconds()
        return elapsed > timeout_seconds

    def update_activity(self):
        """更新最后活动时间为当前时间"""
        with self._lock:
            self.last_active_time = datetime.now()

    def add_message(self, role: str, content: str):
        """
        添加消息到对话历史

        Args:
            role: 角色，'user' 或 'assistant'
            content: 消息内容
        """
        with self._lock:
            self.history.append({"role": role, "content": content})
            self.last_active_time = datetime.now()

    def clear_history(self):
        """清空对话历史（释放内存），保留已提取的关键信息"""
        with self._lock:
            self.history = []
            self.last_active_time = datetime.now()

    def get_history(self) -> List[Dict[str, str]]:
        """获取对话历史的副本，避免外部直接修改"""
        with self._lock:
            return list(self.history)

    def set_content(self, content: str):
        """设置规范化后的用户表述"""
        with self._lock:
            self.content = content
            self.last_active_time = datetime.now()

    def get_content(self) -> Optional[str]:
        """获取规范化后的用户表述"""
        with self._lock:
            return self.content

    def set_problem(self, problem: str):
        """设置匹配到的问题类型（保留兼容）"""
        with self._lock:
            self.problem = problem
            self.last_active_time = datetime.now()

    def get_problem(self) -> Optional[str]:
        """获取匹配到的问题类型"""
        with self._lock:
            return self.problem

    def set_address(self, address: str):
        """设置提取的地址信息"""
        with self._lock:
            self.address = address
            self.last_active_time = datetime.now()

    def get_address(self) -> Optional[str]:
        """获取提取的地址信息"""
        with self._lock:
            return self.address

    def set_prechoice_subcategories(self, subcategories: List[str]):
        """设置大模型选取的2个subCategory"""
        with self._lock:
            self.prechoice_subcategories = subcategories
            self.last_active_time = datetime.now()

    def get_prechoice_subcategories(self) -> Optional[List[str]]:
        """获取大模型选取的2个subCategory"""
        with self._lock:
            return self.prechoice_subcategories

    def set_location(self, location: str):
        """设置问题发生的位置"""
        with self._lock:
            self.location = location
            self.last_active_time = datetime.now()

    def get_location(self) -> Optional[str]:
        """获取问题发生的位置"""
        with self._lock:
            return self.location

    def set_trigger_keyword(self, keyword: str):
        """设置匹配到的 trigger_keyword"""
        with self._lock:
            self.trigger_keyword = keyword
            self.last_active_time = datetime.now()

    def get_trigger_keyword(self) -> Optional[str]:
        """获取匹配到的 trigger_keyword"""
        with self._lock:
            return self.trigger_keyword

    def set_trigger_location(self, location: str):
        """设置匹配到的 trigger_location"""
        with self._lock:
            self.trigger_location = location
            self.last_active_time = datetime.now()

    def get_trigger_location(self) -> Optional[str]:
        """获取匹配到的 trigger_location"""
        with self._lock:
            return self.trigger_location

    def set_reporter_name(self, name: str):
        """设置报修人姓名"""
        with self._lock:
            self.reporter_name = name
            self.last_active_time = datetime.now()

    def get_reporter_name(self) -> Optional[str]:
        """获取报修人姓名"""
        with self._lock:
            return self.reporter_name

    def set_reporter_phone(self, phone: str):
        """设置报修人联系电话"""
        with self._lock:
            self.reporter_phone = phone
            self.last_active_time = datetime.now()

    def get_reporter_phone(self) -> Optional[str]:
        """获取报修人联系电话"""
        with self._lock:
            return self.reporter_phone

    def set_step(self, step: str):
        """设置当前处理阶段"""
        with self._lock:
            self.step = step
            self.last_active_time = datetime.now()

    def get_step(self) -> str:
        """获取当前处理阶段"""
        with self._lock:
            return self.step

    def set_session_state(self, state: str):
        """设置会话生命周期状态"""
        with self._lock:
            self.session_state = state

    def get_session_state(self) -> str:
        """获取会话生命周期状态"""
        with self._lock:
            return self.session_state

    def to_dict(self) -> dict:
        """将会话信息转换为字典"""
        with self._lock:
            return {
                "user_id": self.user_id,
                "step": self.step,
                "session_state": self.session_state,
                "content": self.content,
                "problem": self.problem,
                "address": self.address,
                "prechoice_subcategories": self.prechoice_subcategories,
                "location": self.location,
                "trigger_keyword": self.trigger_keyword,
                "trigger_location": self.trigger_location,
                "reporter_name": self.reporter_name,
                "reporter_phone": self.reporter_phone,
                "last_active_time": self.last_active_time.isoformat(),
                "created_time": self.created_time.isoformat(),
                "history_length": len(self.history)
            }


class UserInput:
    """
    用户输入数据模型

    用于封装用户的原始输入信息，包含用户描述的问题和地址信息。

    Attributes:
        raw_input (str): 用户的原始输入文本
        address (Optional[str]): 从用户输入中提取的地址信息，可为空
    """
    raw_input: str
    address: Optional[str]

    def __init__(self, raw_input: str, address: Optional[str] = None):
        self.raw_input = raw_input
        self.address = address


class ProcessedInput:
    """
    处理后的输入数据模型

    用于封装经过大模型正式化处理后的用户输入信息。

    Attributes:
        formalized_text (str): 正式化后的用户问题表述
        problem (Optional[str]): 匹配到的 problem 字段值（保留兼容）
        address (Optional[str]): 提取的完整地址信息
        prechoice_subcategories (Optional[List[str]]): 选取的2个subCategory
        location (Optional[str]): 问题发生位置
        trigger_keyword (Optional[str]): 匹配的trigger_keyword
        trigger_location (Optional[str]): 匹配的trigger_location
        status (str): 处理状态，SUCCESS / ERROR / MISS
    """
    formalized_text: str
    problem: Optional[str]
    address: Optional[str]
    prechoice_subcategories: Optional[List[str]]
    location: Optional[str]
    trigger_keyword: Optional[str]
    trigger_location: Optional[str]
    status: str

    def __init__(self, formalized_text: str = '', problem: Optional[str] = None,
                 address: Optional[str] = None, status: str = 'SUCCESS',
                 prechoice_subcategories: Optional[List[str]] = None,
                 location: Optional[str] = None,
                 trigger_keyword: Optional[str] = None,
                 trigger_location: Optional[str] = None):
        self.formalized_text = formalized_text
        self.problem = problem
        self.address = address
        self.status = status
        self.prechoice_subcategories = prechoice_subcategories
        self.location = location
        self.trigger_keyword = trigger_keyword
        self.trigger_location = trigger_location

    def to_dict(self) -> dict:
        """
        将处理结果转换为字典格式

        Returns:
            dict: 包含各字段的字典
        """
        return {
            "formalized_text": self.formalized_text,
            "problem": self.problem,
            "address": self.address,
            "status": self.status,
            "prechoice_subcategories": self.prechoice_subcategories,
            "location": self.location,
            "trigger_keyword": self.trigger_keyword,
            "trigger_location": self.trigger_location
        }


class InputProcessingResult:
    """
    输入处理结果封装类

    用于统一封装输入处理的结果，包含处理后的输入数据和相关元信息。

    Attributes:
        processed_input (ProcessedInput): 处理后的输入数据
        error_message (Optional[str]): 错误信息
        missing_info (Optional[str]): 缺失信息描述
    """
    processed_input: ProcessedInput
    error_message: Optional[str]
    missing_info: Optional[str]

    def __init__(self, processed_input: ProcessedInput,
                 error_message: Optional[str] = None,
                 missing_info: Optional[str] = None):
        self.processed_input = processed_input
        self.error_message = error_message
        self.missing_info = missing_info

    def is_success(self) -> bool:
        """判断处理是否成功"""
        return self.processed_input.status == 'SUCCESS'

    def is_error(self) -> bool:
        """判断是否发生错误"""
        return self.processed_input.status == 'ERROR'

    def is_missing(self) -> bool:
        """判断是否缺失信息"""
        return self.processed_input.status == 'MISS'