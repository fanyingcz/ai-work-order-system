"""
用户输入处理模块 - 核心处理逻辑

【文件职责】
实现用户输入的核心处理逻辑，包括：
1. 多用户会话管理（SessionManager），支持超时自动清理和并发安全
2. 第一步：加载 subcategories，选取语义最相关的两个subCategory
3. 提取 content（规范化表述）、address（地址）、location（问题发生位置）
4. 第二步：根据选出的subCategory，取对应trigger_keywords和trigger_location
5. 让大模型选出最匹配的trigger_keyword和可选的trigger_location
6. 返回统一处理结果

【处理流程】
用户输入 → 第一步（subCategory选取 + 信息提取）
  → 若信息缺失 → 提示补充
  → 若信息齐全 → 保存 content, prechoice[2], address, location
  → 第二步（trigger_keyword + trigger_location匹配）
  → 返回完整结果

【输出字段】
- content: 规范化后的用户表述
- prechoice_subcategories: 2个最相关subCategory
- address: 用户输入的地址（可选）
- location: 问题发生的位置（如承重墙、楼梯，可选）
- trigger_keyword: 匹配到的trigger_keyword
- trigger_location: 匹配到的trigger_location（可选）
"""

import json
import os
import random
import threading
import time
import re
from typing import Optional, List, Dict, Tuple
from openai import OpenAI
from .models import UserInput, ProcessedInput, InputProcessingResult, UserSession
from .prompt_manager import PromptManager
from db import get_db


class SessionManager:
    """
    用户会话管理器

    负责管理所有用户的会话，包括：
    1. 创建和获取用户会话
    2. 超时会话的自动清理
    3. 手动删除会话

    Attributes:
        _sessions (Dict[str, UserSession]): 所有用户会话的字典
        _lock (threading.Lock): 线程锁，保证并发安全
        _cleanup_interval (int): 清理线程运行间隔（秒），默认 60 秒
        _timeout_seconds (int): 会话超时阈值（秒），默认 900 秒（15 分钟）
    """

    def __init__(self, timeout_seconds: int = 900, cleanup_interval: int = 60):
        """
        初始化会话管理器

        Args:
            timeout_seconds: 会话超时阈值，默认 900 秒（15 分钟）
            cleanup_interval: 清理线程运行间隔，默认 60 秒
        """
        self._sessions: Dict[str, UserSession] = {}
        self._lock = threading.Lock()
        self._timeout_seconds = timeout_seconds
        self._cleanup_interval = cleanup_interval
        self._start_cleanup_thread()

    def _start_cleanup_thread(self):
        """启动后台清理线程，定期检查并清理超时会话"""
        def cleanup_loop():
            while True:
                time.sleep(self._cleanup_interval)
                self._cleanup_timeout_sessions()

        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()

    def _cleanup_timeout_sessions(self):
        """清理所有超时的会话"""
        with self._lock:
            timeout_users = [
                uid for uid, session in self._sessions.items()
                if session.is_timeout(self._timeout_seconds)
            ]
            for uid in timeout_users:
                del self._sessions[uid]
            if timeout_users:
                print(f"[SessionManager] 已清理超时会话: {timeout_users}")

    def get_or_create_session(self, user_id: str) -> UserSession:
        """
        获取或创建用户会话

        Args:
            user_id: 用户唯一标识

        Returns:
            UserSession: 用户会话对象
        """
        with self._lock:
            if user_id not in self._sessions:
                self._sessions[user_id] = UserSession(user_id)
            return self._sessions[user_id]

    def get_session(self, user_id: str) -> Optional[UserSession]:
        """
        获取用户会话，如果不存在或已超时则返回 None

        Args:
            user_id: 用户唯一标识

        Returns:
            Optional[UserSession]: 用户会话对象，不存在或超时返回 None
        """
        with self._lock:
            session = self._sessions.get(user_id)
            if session is None:
                return None
            if session.is_timeout(self._timeout_seconds):
                del self._sessions[user_id]
                return None
            return session

    def delete_session(self, user_id: str):
        """
        删除用户会话

        Args:
            user_id: 用户唯一标识
        """
        with self._lock:
            if user_id in self._sessions:
                del self._sessions[user_id]

    def get_active_session_count(self) -> int:
        """获取当前活跃会话数量"""
        with self._lock:
            return len(self._sessions)

    def get_all_sessions_info(self) -> List[dict]:
        """获取所有会话的信息列表（用于监控）"""
        with self._lock:
            return [session.to_dict() for session in self._sessions.values()]


class InputProcessor:
    """
    用户输入处理器（新逻辑）

    负责接收用户的原始输入，经过两步处理：
    第一步：加载 subcategories，选取最相关的两个subCategory
           提取 content（规范化表述）、address（地址）、location（位置）
    第二步：根据选出的subCategory，从category取trigger_keywords和trigger_location
           让大模型选出最匹配的trigger_keyword和可选的trigger_location

    Attributes:
        rules_dir (str): 数据文件目录
        subcategories (List[dict]): subcategories 内容
        session_manager (SessionManager): 用户会话管理器
        _client (OpenAI): DeepSeek API 客户端
    """

    def __init__(self, rules_dir: str = "data/rules"):
        """
        初始化输入处理器

        Args:
            rules_dir: 规则文件所在目录，默认为 "data/rules"
        """
        self.rules_dir = rules_dir
        self.subcategories = self._load_subcategories()
        self.category_rules = self._load_category_rules()
        self.session_manager = SessionManager()

        # 初始化提示词管理器
        self.prompt_manager = PromptManager(os.path.join(self.rules_dir, 'prompts.json'))

        # 初始化 DeepSeek 客户端
        api_key = os.environ.get('ds_apikey')
        if not api_key:
            print("[警告] 环境变量 ds_apikey 未设置，请设置 DeepSeek API Key")
            print("[提示] 可通过 set ds_apikey=your_key_here 设置")
        self._client = OpenAI(
            api_key=api_key or '',
            base_url="https://api.deepseek.com/v1",
            timeout=120.0
        )

    # ==================== 数据加载 ====================

    def _load_subcategories(self) -> List[dict]:
        """
        从数据库加载所有 subCategory 及其 description，DB 不可用时回退到 JSON 文件

        Returns:
            List[dict]: 每个元素包含 id, subCategory, description
        """
        try:
            db = get_db()
            if db.rules_data_exists():
                db_results = db.get_all_subcategories()
                if db_results:
                    return [
                        {
                            'id': row.get('id'),
                            'subCategory': row.get('sub_category'),
                            'description': row.get('description', '')
                        }
                        for row in db_results
                    ]
        except Exception as e:
            print(f"[InputProcessor] 从数据库加载 subcategories 失败，回退到 JSON: {e}")

        # JSON 回退
        sub_file = os.path.join(self.rules_dir, 'subcategories.json')
        if not os.path.exists(sub_file):
            raise FileNotFoundError(f"subcategories.json 文件不存在: {sub_file}")

        with open(sub_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_category_rules(self) -> List[dict]:
        """
        从数据库加载所有规则，DB 不可用时回退到 category.json

        Returns:
            List[dict]: 每个元素包含完整规则字段
        """
        try:
            db = get_db()
            if db.rules_data_exists():
                db_results = db.get_all_categories()
                if db_results:
                    return [
                        {
                            'id': row.get('rule_id'),
                            'category': row.get('category'),
                            'subCategory': row.get('sub_category'),
                            'problem': row.get('problem'),
                            'priority': row.get('priority'),
                            'required_cert': row.get('required_cert'),
                            'target_dept_semantic': row.get('target_dept_semantic'),
                            'description': row.get('description'),
                            'trigger_keywords': row.get('trigger_keywords', []),
                            'trigger_location': row.get('trigger_location', [])
                        }
                        for row in db_results
                    ]
        except Exception as e:
            print(f"[InputProcessor] 从数据库加载 categories 失败，回退到 JSON: {e}")

        # JSON 回退
        category_file = os.path.join(self.rules_dir, 'category.json')
        if not os.path.exists(category_file):
            raise FileNotFoundError(f"category.json 文件不存在: {category_file}")

        with open(category_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _get_trigger_data_for_subcategories(self, subcategories: List[str]) -> Dict[str, dict]:
        """
        根据选出的subCategory列表，获取对应的所有trigger_keywords和trigger_location

        Args:
            subcategories: subCategory名称列表，如 ["险", "电"]

        Returns:
            dict: {
                "subCategory1": {
                    "trigger_keywords": [list of keywords],
                    "trigger_locations": [list of locations]
                },
                ...
            }
        """
        # 直接使用内存中的 self.category_rules（已在 __init__ 中加载），
        # 避免并发 DB 查询导致的线程安全/协议错误问题
        result = {}
        sub_set = set(subcategories)
        for rule in self.category_rules:
            sub = rule.get('subCategory', '')
            if sub in sub_set:
                if sub not in result:
                    result[sub] = {
                        'trigger_keywords': [],
                        'trigger_locations': []
                    }
                result[sub]['trigger_keywords'].extend(rule.get('trigger_keywords', []))
                result[sub]['trigger_locations'].extend(rule.get('trigger_location', []))
        return result

    # ==================== DeepSeek API 调用 ====================

    def _call_deepseek(self, messages: List[Dict[str, str]], max_retries: int = 3, **kwargs) -> str:
        """
        调用 DeepSeek 模型，包含重试和空白响应处理机制

        Args:
            messages: 对话消息列表
            max_retries: 最大重试次数
            **kwargs: 额外参数，如 max_tokens（默认 2048）

        Returns:
            str: 模型返回的文本内容

        Raises:
            Exception: 调用失败且超过最大重试次数时抛出
        """
        last_error = None
        _max_tokens = kwargs.get('max_tokens', 2048)

        for attempt in range(max_retries):
            try:
                response = self._client.chat.completions.create(
                    model="deepseek-v4-flash",
                    messages=messages,
                    temperature=0.1,
                    max_tokens=_max_tokens,
                    stream=False
                )

                content = response.choices[0].message.content

                if content is None or content.strip() == "":
                    last_error = "DeepSeek 返回了空白响应（content 为空或 None）"
                    is_last = (attempt == max_retries - 1)
                    wait_time = 5 * (2 ** attempt) + random.uniform(0, 2)
                    if is_last:
                        print(f"[DeepSeek] 第 {attempt + 1} 次调用返回空白（最后一次重试），等待 {wait_time:.1f} 秒")
                        time.sleep(wait_time)
                    else:
                        print(f"[DeepSeek] 第 {attempt + 1} 次调用返回空白，{wait_time:.1f}秒后重试")
                        time.sleep(wait_time)
                    continue

                return content.strip()

            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"[DeepSeek] 第 {attempt + 1} 次调用失败（{error_type}），{wait_time}秒后重试: {e}")
                    time.sleep(wait_time)
                else:
                    print(f"[DeepSeek] 第 {attempt + 1} 次调用失败（{error_type}），已达最大重试次数: {e}")
                continue

        raise Exception(f"DeepSeek 调用失败（已重试 {max_retries} 次）: {last_error}")

    # ==================== Prompt 构建 ====================

    def _build_step1_prompt(self) -> str:
        """
        构建第一步 Prompt：subCategory 选取 + 信息提取

        从 prompts.json 加载"如何选择"的指导内容（思考步骤、任务描述、注意事项），
        严格输出格式由程序代码控制（因解析逻辑依赖固定格式）。

        Returns:
            str: 完整的第一步 prompt
        """
        pm = self.prompt_manager
        parts = pm.get_step1_parts()

        # 构建 subCategory 列表文本
        sub_list_text = ""
        for item in self.subcategories:
            sub_list_text += f"- {item['subCategory']}：{item['description']}\n"

        # 从 JSON 读取思考步骤
        thinking_lines = "\n".join(
            f"{i + 1}. {step}" for i, step in enumerate(parts['thinking_steps'])
        )

        # 从 JSON 读取任务描述（动态遍历，支持任意数量 task）
        tasks = dict(parts['tasks'])
        # task2 是需要插入 subCategory 列表的特殊任务，单独处理
        task2_text = tasks.pop('task2', '')
        # 其余任务按排序动态生成
        sorted_task_keys = sorted(tasks.keys(), key=lambda k: int(k.replace('task', '')))
        task_lines = []
        for tk in sorted_task_keys:
            task_num = int(tk.replace('task', ''))
            task_lines.append(f"【任务{task_num}】{tasks[tk]}")
        task_section = "\n".join(task_lines)

        # 从 JSON 读取注意事项
        notes_lines = "\n".join(
            f"{i + 1}. {note}" for i, note in enumerate(parts['notes'])
        )

        # 组装完整 prompt（输出格式仍由代码硬控制，因解析逻辑依赖固定格式）
        # task2 插入 subCategory 列表后
        return (
            f"{parts['system_role']}\n\n"
            f"【思考步骤】\n"
            f"{thinking_lines}\n\n"
            f"{task_section}\n\n"
            f"{sub_list_text}\n"
            f"【任务2补充】{task2_text}\n\n"
            "输出格式（严格按以下格式，每行一项）：\n"
            "【content】：规范化后的用户表述\n"
            "【prechoice】：[\"subCategory1\", \"subCategory2\"]\n"
            "【address】：用户输入的地址（如果没有则填写\"无\"）\n"
            "【location】：问题发生的位置（如\"承重墙\"、\"楼梯\"、\"天花板\"，如果没有则填写\"无\"）\n"
            "【reporter_name】：报修人姓名（如果没有则填写\"无\"）\n"
            "【reporter_phone】：报修人联系电话（如果没有则填写\"无\"）\n\n"
            f"注意：\n"
            f"{notes_lines}"
        )

    def _build_step2_prompt(self, content: str, trigger_data: Dict[str, dict], has_location: bool,
                            location: str = "") -> str:
        """
        构建第二步 Prompt：trigger_keyword + trigger_location 匹配

        从 prompts.json 加载分类规则、要求等指导内容，
        严格输出格式由程序代码控制。

        Args:
            content: 规范化后的用户表述
            trigger_data: 选出的subCategory对应的trigger_keywords和trigger_locations
            has_location: 是否已提取到 location

        Returns:
            str: 第二步 prompt
        """
        pm = self.prompt_manager
        parts = pm.get_step2_parts()

        # 构建 keywords 列表文本
        all_keywords_text = ""
        for sub, data in trigger_data.items():
            keywords = list(set(data.get('trigger_keywords', [])))
            all_keywords_text += f"\n【{sub}】的 trigger_keywords：\n"
            for kw in keywords:
                all_keywords_text += f"  - {kw}\n"

        # 从 JSON 读取分类规则
        rules_text = "\n".join(parts['classification_rules'])

        # 从 JSON 读取要求
        reqs_lines = "\n".join(
            f"{i + 1}. {req}" for i, req in enumerate(parts['requirements'])
        )

        # 组装主 prompt（输出格式仍由代码硬控制）
        prompt = (
            f"{parts['system_role']}\n\n"
            f"用户问题描述（content）：{content}\n\n"
            f"可供选择的 trigger_keywords 列表（按 subCategory 分组）：{all_keywords_text}\n\n"
            f"【思考步骤】\n"
            f"第1步：{parts['thinking_step1_description']}\n"
            f"{rules_text}\n"
            f"第2步：{parts['thinking_step2_description']}\n\n"
            f"要求：\n"
            f"{reqs_lines}\n\n"
            "输出格式：\n"
            "【trigger_keyword】：选出的 trigger_keyword"
        )

        if has_location:
            all_locations_text = ""
            for sub, data in trigger_data.items():
                locs = list(set(data.get('trigger_locations', [])))
                all_locations_text += f"\n【{sub}】的 trigger_location：\n"
                for loc in locs:
                    all_locations_text += f"  - {loc}\n"

            loc_prompt_template = parts.get('location_selection_prompt', '')
            loc_prompt = loc_prompt_template.format(location=location)

            loc_req_lines = "\n".join(parts.get('location_requirements', []))

            prompt += (
                f"\n\n{loc_prompt}\n\n"
                f"可供选择的 trigger_location 列表：{all_locations_text}\n\n"
                f"{loc_req_lines}"
            )

        return prompt

    # ==================== 结果解析 ====================

    def _parse_step1_result(self, result: str) -> dict:
        """
        解析第一步 DeepSeek 返回的结果

        从格式化输出中提取 content, prechoice, address, location,
        reporter_name, reporter_phone。

        Args:
            result: DeepSeek 返回的原始结果文本

        Returns:
            dict: {
                "content": str,
                "prechoice": List[str] or None,
                "address": str or None,
                "location": str or None,
                "reporter_name": str or None,
                "reporter_phone": str or None,
                "status": "PASS" / "MISS" / "ERROR"
            }
        """
        parsed = {
            "content": "",
            "prechoice": None,
            "address": None,
            "location": None,
            "reporter_name": None,
            "reporter_phone": None,
            "status": "ERROR",
            "message_to_user": ""
        }

        content_match = re.search(r'【content】[：:]?\s*(.*?)(?=\n\n|\n【prechoice】|\n【address】|\n【location】|\n【reporter_name】|\n*$)', result, re.DOTALL)
        if content_match:
            parsed["content"] = content_match.group(1).strip()

        prechoice_match = re.search(r'【prechoice】[：:]?\s*(\[.*?\])', result, re.DOTALL)
        if prechoice_match:
            try:
                prechoice_str = prechoice_match.group(1).strip()
                parsed["prechoice"] = json.loads(prechoice_str)
                if not isinstance(parsed["prechoice"], list) or len(parsed["prechoice"]) != 2:
                    parsed["prechoice"] = None
            except (json.JSONDecodeError, Exception):
                arr_match = re.findall(r'"([^"]+)"', prechoice_match.group(1))
                if len(arr_match) == 2:
                    parsed["prechoice"] = arr_match

        address_match = re.search(r'【address】[：:]?\s*(.*?)(?=\n\n|\n【location】|\n【reporter_name】|\n*$)', result, re.DOTALL)
        if address_match:
            addr = address_match.group(1).strip()
            if addr and addr != "无":
                parsed["address"] = addr

        location_match = re.search(r'【location】[：:]?\s*(.*?)(?=\n\n|\n【reporter_name】|\n*$)', result, re.DOTALL)
        if location_match:
            loc = location_match.group(1).strip()
            if loc and loc != "无":
                parsed["location"] = loc

        reporter_name_match = re.search(r'【reporter_name】[：:]?\s*(.*?)(?=\n\n|\n【reporter_phone】|\n*$)', result, re.DOTALL)
        if reporter_name_match:
            name = reporter_name_match.group(1).strip()
            if name and name != "无":
                parsed["reporter_name"] = name

        reporter_phone_match = re.search(r'【reporter_phone】[：:]?\s*(.*?)(?=\n*$)', result, re.DOTALL)
        if reporter_phone_match:
            phone = reporter_phone_match.group(1).strip()
            if phone and phone != "无":
                parsed["reporter_phone"] = phone

        if not parsed["content"]:
            parsed["status"] = "ERROR"
            parsed["message_to_user"] = "系统处理异常，请稍后重试"
        elif not parsed["prechoice"]:
            parsed["status"] = "ERROR"
            parsed["message_to_user"] = "系统处理异常，无法匹配问题类型"
        elif not parsed["address"]:
            parsed["status"] = "MISS"
            parsed["message_to_user"] = "请提供您的详细地址（如路名、门牌号、小区名等）"
        elif len(parsed["prechoice"]) < 2:
            parsed["status"] = "ERROR"
            parsed["message_to_user"] = "系统处理异常，请重新描述您的问题"
        else:
            parsed["status"] = "PASS"

        if not parsed["content"]:
            lines = result.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('【content】') or line.startswith('content') or line.startswith('【content'):
                    val = re.sub(r'^【?content】?[：:]?\s*', '', line).strip()
                    if val:
                        parsed["content"] = val
                        break

        return parsed

    def _parse_step2_result(self, result: str, has_location: bool) -> dict:
        """
        解析第二步 DeepSeek 返回的结果

        Args:
            result: DeepSeek 返回的原始结果文本
            has_location: 是否期望包含 trigger_location

        Returns:
            dict: {
                "trigger_keyword": str or None,
                "trigger_location": str or None,
                "status": "SUCCESS" / "NO_MATCH" / "ERROR"
            }
        """
        parsed = {
            "trigger_keyword": None,
            "trigger_location": None,
            "status": "ERROR"
        }

        kw_match = re.search(r'【trigger_keyword】[：:]?\s*(.*?)(?=\n\n|\n【trigger_location】|\n*$)', result, re.DOTALL)
        if kw_match:
            parsed["trigger_keyword"] = kw_match.group(1).strip()

        if has_location:
            loc_match = re.search(r'【trigger_location】[：:]?\s*(.*?)(?=\n*$)', result, re.DOTALL)
            if loc_match:
                parsed["trigger_location"] = loc_match.group(1).strip()

        if parsed["trigger_keyword"]:
            parsed["status"] = "SUCCESS"
        else:
            lines = result.strip().split('\n')
            for line in lines:
                line = line.strip()
                if 'trigger_keyword' in line:
                    val = re.sub(r'^【?trigger_keyword】?[：:]?\s*', '', line).strip()
                    if val:
                        parsed["trigger_keyword"] = val
                        parsed["status"] = "SUCCESS"
                if has_location and 'trigger_location' in line:
                    val = re.sub(r'^【?trigger_location】?[：:]?\s*', '', line).strip()
                    if val:
                        parsed["trigger_location"] = val

        if not parsed["trigger_keyword"]:
            parsed["status"] = "NO_MATCH"

        return parsed

    # ==================== 输入预处理 ====================

    def _is_unclassifiable(self, user_input: str) -> bool:
        """
        检测用户输入是否为纯催办/取消报修等不可分类的描述。
        这类输入没有实质性的维修内容，无法进行有意义的分类。

        Args:
            user_input: 用户原始输入

        Returns:
            bool: True 表示不可分类，应交由人工处理
        """
        import re
        patterns = [
            r'^催报修\s*\d+',
            r'^催单.*\d+',
            r'^取消.*\d+',
            r'^居民取消.*\d*',
            r'.*取消报修.*\d*',
            r'^崔保修\s*\d*',
            r'^\d+\s*催报修',
            r'^\d+\s*崔保修',
            r'^[A-Za-z\d]+\s*催报修',
        ]
        for p in patterns:
            if re.match(p, user_input.strip()):
                return True
        return False

    # ==================== 核心处理方法 ====================

    def _step1_select_subcategories(self, user_id: str, user_input: str) -> dict:
        """
        第一步：选取 subCategory + 提取信息

        使用 DeepSeek 模型，加载 subcategories 中的全部 subCategory，
        选取最相关的两个，同时提取 content、address、location、
        reporter_name、reporter_phone。

        Args:
            user_id: 用户唯一标识
            user_input: 用户的输入文本

        Returns:
            dict: {
                "status": "PASS" / "MISS" / "ERROR",
                "content": 规范化表述,
                "prechoice": [sub1, sub2],
                "address": 地址 or None,
                "location": 位置 or None,
                "reporter_name": 报修人姓名 or None,
                "reporter_phone": 报修人电话 or None,
                "message_to_user": 返回给用户的消息
            }
        """
        try:
            session = self.session_manager.get_or_create_session(user_id)

            session.add_message("user", user_input)

            system_prompt = self._build_step1_prompt()
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            messages.extend(session.get_history())

            result = self._call_deepseek(messages, max_tokens=2048)

            parsed = self._parse_step1_result(result)

            if parsed["status"] == "ERROR":
                session.add_message("assistant", f"【处理异常】")
                return {
                    "status": "ERROR",
                    "content": None,
                    "prechoice": None,
                    "address": None,
                    "location": None,
                    "reporter_name": None,
                    "reporter_phone": None,
                    "message_to_user": parsed.get("message_to_user", "系统处理异常，请稍后重试")
                }

            if parsed["status"] == "MISS":
                # 保存已提取的信息到 session，供多轮对话后续使用
                content = parsed["content"]
                prechoice = parsed["prechoice"]
                location = parsed.get("location")
                reporter_name = parsed.get("reporter_name")
                reporter_phone = parsed.get("reporter_phone")
                
                if content:
                    session.set_content(content)
                if prechoice:
                    session.set_prechoice_subcategories(prechoice)
                if location:
                    session.set_location(location)
                if reporter_name:
                    session.set_reporter_name(reporter_name)
                if reporter_phone:
                    session.set_reporter_phone(reporter_phone)
                
                session.set_step('awaiting_supplement')
                session.add_message("assistant", f"系统要求补充地址")
                return {
                    "status": "MISS",
                    "content": content,
                    "prechoice": prechoice,
                    "address": None,
                    "location": location,
                    "reporter_name": reporter_name,
                    "reporter_phone": reporter_phone,
                    "message_to_user": parsed.get("message_to_user", "请补充您的地址信息")
                }

            content = parsed["content"]
            prechoice = parsed["prechoice"]
            address = parsed["address"]
            location = parsed.get("location")
            reporter_name = parsed.get("reporter_name")
            reporter_phone = parsed.get("reporter_phone")

            session.set_content(content)
            session.set_prechoice_subcategories(prechoice)
            session.set_address(address)
            if location:
                session.set_location(location)
            if reporter_name:
                session.set_reporter_name(reporter_name)
            if reporter_phone:
                session.set_reporter_phone(reporter_phone)
            session.set_step('completed')
            session.add_message("assistant", f"信息已齐全: {content}")
            session.clear_history()

            return {
                "status": "PASS",
                "content": content,
                "prechoice": prechoice,
                "address": address,
                "location": location,
                "reporter_name": reporter_name,
                "reporter_phone": reporter_phone,
                "message_to_user": "信息已收齐，正在匹配维修规则"
            }

        except Exception as e:
            print(f"[InputProcessor] Step1 处理异常 (user={user_id}): {e}")
            return {
                "status": "ERROR",
                "content": None,
                "prechoice": None,
                "address": None,
                "location": None,
                "reporter_name": None,
                "reporter_phone": None,
                "message_to_user": f"系统处理异常: {str(e)}"
            }

    def _step2_match_keywords(self, user_id: str, content: str,
                               prechoice: List[str],
                               location: Optional[str]) -> dict:
        """
        第二步：匹配 trigger_keyword 和可选的 trigger_location

        根据选出的subCategory，从数据源获取对应的 trigger_keywords 和
        trigger_location，让大模型选出最匹配的一个。

        Args:
            user_id: 用户唯一标识
            content: 规范化后的用户表述
            prechoice: 选出的2个subCategory
            location: 问题发生位置（可选）

        Returns:
            dict: {
                "status": "SUCCESS" / "NO_MATCH" / "ERROR",
                "trigger_keyword": str or None,
                "trigger_location": str or None,
                "message": 提示消息
            }
        """
        try:
            trigger_data = self._get_trigger_data_for_subcategories(prechoice)

            if not trigger_data:
                return {
                    "status": "NO_MATCH",
                    "trigger_keyword": None,
                    "trigger_location": None,
                    "message": "未能获取到匹配的trigger数据"
                }

            has_location = bool(location)

            prompt = self._build_step2_prompt(content, trigger_data, has_location,
                                              location=location or "")
            messages = [{"role": "user", "content": prompt}]

            result = self._call_deepseek(messages, max_tokens=2048)

            parsed = self._parse_step2_result(result, has_location)

            if parsed["status"] != "SUCCESS":
                return {
                    "status": "NO_MATCH",
                    "trigger_keyword": None,
                    "trigger_location": None,
                    "message": "无法匹配到合适的维修关键词"
                }

            session = self.session_manager.get_session(user_id)
            if session:
                session.set_trigger_keyword(parsed["trigger_keyword"])
                if parsed.get("trigger_location"):
                    session.set_trigger_location(parsed["trigger_location"])
                session.set_session_state('COMPLETED')

            return {
                "status": "SUCCESS",
                "trigger_keyword": parsed["trigger_keyword"],
                "trigger_location": parsed.get("trigger_location"),
                "message": "关键词匹配成功"
            }

        except Exception as e:
            print(f"[InputProcessor] Step2 处理异常: {e}")
            return {
                "status": "ERROR",
                "trigger_keyword": None,
                "trigger_location": None,
                "message": f"关键词匹配失败: {str(e)}"
            }

    # ==================== 对外接口 ====================

    def process_user_input(self, user_id: str, user_input: str) -> dict:
        """
        处理用户输入（对外主接口）

        完整流程：
        1. 第一步：选取 subCategory + 提取 content/address/location/reporter
        2. 如果第一步 PASS → 自动执行第二步 trigger_keyword 匹配
        3. 返回完整处理结果

        Args:
            user_id: 用户唯一标识
            user_input: 用户的输入文本

        Returns:
            dict: {
                "status": "SUCCESS" / "MISS" / "ERROR",
                "content": str or None,
                "prechoice_subcategories": List[str] or None,
                "address": str or None,
                "location": str or None,
                "trigger_keyword": str or None,
                "trigger_location": str or None,
                "reporter_name": str or None,
                "reporter_phone": str or None,
                "message_to_user": str,
                "need_more_input": bool
            }
        """
        if self._is_unclassifiable(user_input):
            return {
                "status": "UNCLASSIFIABLE",
                "content": user_input.strip(),
                "prechoice_subcategories": None,
                "address": None,
                "location": None,
                "trigger_keyword": None,
                "trigger_location": None,
                "reporter_name": None,
                "reporter_phone": None,
                "message_to_user": "该报修为催办或取消请求，无法自动分类，请转人工处理",
                "need_more_input": False
            }

        step1_result = self._step1_select_subcategories(user_id, user_input)

        if step1_result["status"] != "PASS":
            return {
                "status": step1_result["status"],
                "content": step1_result.get("content"),
                "prechoice_subcategories": step1_result.get("prechoice"),
                "address": step1_result.get("address"),
                "location": step1_result.get("location"),
                "trigger_keyword": None,
                "trigger_location": None,
                "reporter_name": step1_result.get("reporter_name"),
                "reporter_phone": step1_result.get("reporter_phone"),
                "message_to_user": step1_result["message_to_user"],
                "need_more_input": (step1_result["status"] == "MISS")
            }

        content = step1_result["content"]
        prechoice = step1_result["prechoice"]
        address = step1_result["address"]
        location = step1_result.get("location")
        reporter_name = step1_result.get("reporter_name")
        reporter_phone = step1_result.get("reporter_phone")

        step2_result = self._step2_match_keywords(user_id, content, prechoice, location)

        if step2_result["status"] != "SUCCESS":
            self.session_manager.delete_session(user_id)
            return {
                "status": step2_result["status"],
                "content": content,
                "prechoice_subcategories": prechoice,
                "address": address,
                "location": location,
                "trigger_keyword": None,
                "trigger_location": None,
                "reporter_name": reporter_name,
                "reporter_phone": reporter_phone,
                "message_to_user": step2_result["message"],
                "need_more_input": False
            }

        return {
            "status": "SUCCESS",
            "content": content,
            "prechoice_subcategories": prechoice,
            "address": address,
            "location": location,
            "trigger_keyword": step2_result["trigger_keyword"],
            "trigger_location": step2_result.get("trigger_location"),
            "reporter_name": reporter_name,
            "reporter_phone": reporter_phone,
            "message_to_user": "工单信息已准备就绪",
            "need_more_input": False
        }

    def check_session_status(self, user_id: str) -> dict:
        """
        检查用户会话状态

        Args:
            user_id: 用户唯一标识

        Returns:
            dict: 会话状态信息
        """
        session = self.session_manager.get_session(user_id)
        if session is None:
            return {
                "has_session": False,
                "step": None,
                "session_state": None,
                "message": "没有活跃的会话，请重新提交报修信息"
            }

        session_state = session.get_session_state()
        step = session.get_step()

        message = ""
        if session_state == 'COMPLETED':
            message = "工单信息已提取完成，等待存入数据库"
        elif step == 'awaiting_supplement':
            message = "请补充缺失的信息"
        else:
            message = "处理中"

        return {
            "has_session": True,
            "step": step,
            "session_state": session_state,
            "content": session.get_content(),
            "address": session.get_address(),
            "prechoice_subcategories": session.get_prechoice_subcategories(),
            "location": session.get_location(),
            "trigger_keyword": session.get_trigger_keyword(),
            "trigger_location": session.get_trigger_location(),
            "message": message
        }

    def cancel_session(self, user_id: str):
        """
        取消用户会话

        Args:
            user_id: 用户唯一标识
        """
        self.session_manager.delete_session(user_id)

    def confirm_persisted(self, user_id: str) -> bool:
        """
        确认工单数据已存入数据库，删除会话

        Args:
            user_id: 用户唯一标识

        Returns:
            bool: 删除成功返回 True
        """
        session = self.session_manager.get_session(user_id)
        if session is None:
            return False

        session_state = session.get_session_state()
        if session_state != 'COMPLETED':
            print(f"[InputProcessor] 会话状态不是 COMPLETED，当前状态: {session_state}")
            return False

        session.set_session_state('PERSISTED')
        self.session_manager.delete_session(user_id)
        print(f"[InputProcessor] 会话 {user_id} 已确认持久化并删除")
        return True

    def get_completed_session_data(self, user_id: str) -> Optional[dict]:
        """
        获取已完成会话的提取数据

        Args:
            user_id: 用户唯一标识

        Returns:
            Optional[dict]: 包含所有提取数据的字典
        """
        session = self.session_manager.get_session(user_id)
        if session is None:
            return None

        session_state = session.get_session_state()
        if session_state != 'COMPLETED':
            return None

        return {
            "content": session.get_content(),
            "address": session.get_address(),
            "prechoice_subcategories": session.get_prechoice_subcategories(),
            "location": session.get_location(),
            "trigger_keyword": session.get_trigger_keyword(),
            "trigger_location": session.get_trigger_location(),
            "user_id": user_id
        }

    # ==================== 批量处理模式（JSON 文件） ====================

    def process_json_inputs(self, json_file_path: str) -> List[dict]:
        """
        从 JSON 文件批量处理用户输入（测试用）

        Args:
            json_file_path: JSON 文件路径

        Returns:
            List[dict]: 每个输入的处理结果列表
        """
        if not os.path.exists(json_file_path):
            raise FileNotFoundError(f"JSON 文件不存在: {json_file_path}")

        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        results = []

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    uid = item.get('user_id', 'batch_user')
                    user_input = item.get('input', item.get('user_input', ''))
                else:
                    uid = 'batch_user'
                    user_input = str(item)

                result = self.process_user_input(uid, user_input)
                results.append(result)

        return results


def process_user_input_wrapper(processor: InputProcessor, user_id: str, user_input: str) -> InputProcessingResult:
    """
    兼容旧接口的包装函数

    将新的 dict 返回格式转换为旧的 InputProcessingResult 对象格式。

    Args:
        processor: InputProcessor 实例
        user_id: 用户标识
        user_input: 用户输入

    Returns:
        InputProcessingResult: 旧接口兼容的处理结果
    """
    result = processor.process_user_input(user_id, user_input)

    if result["status"] == "ERROR":
        return InputProcessingResult(
            processed_input=ProcessedInput(status='ERROR'),
            error_message=result.get("message_to_user", "处理失败")
        )
    elif result["status"] == "MISS" or result["status"] == "NO_MATCH":
        return InputProcessingResult(
            processed_input=ProcessedInput(
                formalized_text=result.get("content", ""),
                address=result.get("address"),
                prechoice_subcategories=result.get("prechoice_subcategories"),
                location=result.get("location"),
                status='MISS'
            ),
            missing_info=result.get("message_to_user", "信息不完整")
        )
    else:
        return InputProcessingResult(
            processed_input=ProcessedInput(
                formalized_text=result.get("content", ""),
                address=result.get("address"),
                prechoice_subcategories=result.get("prechoice_subcategories"),
                location=result.get("location"),
                trigger_keyword=result.get("trigger_keyword"),
                trigger_location=result.get("trigger_location"),
                status='SUCCESS'
            )
        )