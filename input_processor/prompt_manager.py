"""
提示词管理器 - 从 JSON 文件加载和管理提示词配置

【文件职责】
1. 从 data/rules/prompts.json 加载提示词配置
2. 提供读取 Step1 和 Step2 各部分提示词的方法
3. 提供修改/更新 JSON 配置的方法（持久化回文件）
4. 支持热重载，无需重启服务即可更新提示词

【使用方法】
```python
from input_processor.prompt_manager import PromptManager

pm = PromptManager()

# 读取配置
step1_parts = pm.get_step1_parts()
step2_parts = pm.get_step2_parts()

# 修改某条规则
pm.update_step2_rule(0, "新的分类规则文本")
pm.add_step2_rule("新的分类规则文本")
pm.remove_step2_rule(2)

# 重新加载（修改 JSON 文件后无需重启）
pm.reload()
```
"""

import json
import os
import threading
from typing import List, Dict, Optional, Any


class PromptManager:
    """
    提示词管理器

    负责加载、缓存和修改 prompts.json 配置。
    所有读操作直接从内存缓存读取，写操作会持久化到文件。

    Attributes:
        prompts_path (str): prompts.json 文件路径
        _data (dict): 内存中的配置数据
        _lock (threading.Lock): 线程锁
    """

    def __init__(self, prompts_path: str = "data/rules/prompts.json"):
        """
        初始化提示词管理器

        Args:
            prompts_path: prompts.json 文件路径，默认为 data/rules/prompts.json
        """
        self.prompts_path = prompts_path
        self._lock = threading.Lock()
        self._data: dict = {}
        self._load()

    # ==================== 加载与重载 ====================

    def _load(self):
        """从 JSON 文件加载配置到内存"""
        if not os.path.exists(self.prompts_path):
            raise FileNotFoundError(f"提示词配置文件不存在: {self.prompts_path}")

        with open(self.prompts_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self._validate(data)
        self._data = data

    def reload(self):
        """
        重新加载提示词配置（热重载）

        无需重启服务即可使修改后的 JSON 文件生效。
        """
        with self._lock:
            self._load()
        print(f"[PromptManager] 已重新加载提示词配置 (version={self._data.get('version', 'unknown')})")

    def _validate(self, data: dict):
        """
        校验配置结构完整性

        Args:
            data: 配置字典

        Raises:
            ValueError: 结构不合法时抛出
        """
        required_top = ['version', 'step1', 'step2']
        for key in required_top:
            if key not in data:
                raise ValueError(f"提示词配置文件缺少顶层字段: {key}")

        step1_required = ['system_role', 'thinking_steps', 'tasks', 'notes']
        for key in step1_required:
            if key not in data['step1']:
                raise ValueError(f"提示词配置文件 step1 缺少字段: {key}")

        step2_required = ['system_role', 'classification_rules', 'requirements']
        for key in step2_required:
            if key not in data['step2']:
                raise ValueError(f"提示词配置文件 step2 缺少字段: {key}")

    def _save(self):
        """将内存中的配置持久化到 JSON 文件"""
        with open(self.prompts_path, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        print(f"[PromptManager] 提示词配置已保存到 {self.prompts_path}")

    # ==================== Step1 读取方法 ====================

    def get_step1_system_role(self) -> str:
        """获取 Step1 系统角色定义"""
        return self._data['step1']['system_role']

    def get_step1_thinking_steps(self) -> List[str]:
        """获取 Step1 思考步骤列表"""
        return list(self._data['step1']['thinking_steps'])

    def get_step1_tasks(self) -> dict:
        """获取 Step1 任务定义 (task1-task4)"""
        return dict(self._data['step1']['tasks'])

    def get_step1_notes(self) -> List[str]:
        """获取 Step1 注意事项列表"""
        return list(self._data['step1']['notes'])

    def get_step1_parts(self) -> dict:
        """
        获取构建 Step1 prompt 所需的全部部件

        Returns:
            dict: 包含 system_role, thinking_steps, tasks, notes 的字典
        """
        with self._lock:
            return {
                'system_role': self._data['step1']['system_role'],
                'thinking_steps': list(self._data['step1']['thinking_steps']),
                'tasks': dict(self._data['step1']['tasks']),
                'notes': list(self._data['step1']['notes']),
            }

    # ==================== Step2 读取方法 ====================

    def get_step2_system_role(self) -> str:
        """获取 Step2 系统角色定义"""
        return self._data['step2']['system_role']

    def get_step2_classification_rules(self) -> List[str]:
        """获取 Step2 分类规则列表"""
        return list(self._data['step2']['classification_rules'])

    def get_step2_requirements(self) -> List[str]:
        """获取 Step2 要求列表"""
        return list(self._data['step2']['requirements'])

    def get_step2_location_prompt(self) -> str:
        """
        获取 Step2 的 location 选择提示模板（含 {location} 占位符）

        使用时需要用 .format(location=xxx) 填充。
        """
        return self._data['step2'].get('location_selection_prompt', '')

    def get_step2_location_requirements(self) -> List[str]:
        """获取 Step2 location 选择要求列表"""
        loc_reqs = self._data['step2'].get('location_requirements', [])
        return list(loc_reqs)

    def get_step2_thinking_step1_desc(self) -> str:
        """获取 Step2 第一个思考步骤的描述"""
        return self._data['step2'].get('thinking_step1_description', '')

    def get_step2_thinking_step2_desc(self) -> str:
        """获取 Step2 第二个思考步骤的描述"""
        return self._data['step2'].get('thinking_step2_description', '')

    def get_step2_parts(self) -> dict:
        """
        获取构建 Step2 prompt 所需的全部部件

        Returns:
            dict: 包含所有 step2 配置字段的字典
        """
        with self._lock:
            step2 = self._data['step2']
            return {
                'system_role': step2['system_role'],
                'thinking_step1_description': step2.get('thinking_step1_description', ''),
                'thinking_step2_description': step2.get('thinking_step2_description', ''),
                'classification_rules': list(step2['classification_rules']),
                'requirements': list(step2['requirements']),
                'location_selection_prompt': step2.get('location_selection_prompt', ''),
                'location_requirements': list(step2.get('location_requirements', [])),
            }

    # ==================== 修改方法 ====================

    def update_step1_system_role(self, text: str):
        """更新 Step1 系统角色"""
        with self._lock:
            self._data['step1']['system_role'] = text
            self._save()

    def update_step1_thinking_steps(self, steps: List[str]):
        """替换 Step1 思考步骤列表"""
        with self._lock:
            self._data['step1']['thinking_steps'] = steps
            self._save()

    def update_step1_task(self, task_key: str, text: str):
        """
        更新 Step1 的某个任务描述

        Args:
            task_key: 任务键名 (task1, task2, task3, task4)
            text: 新的任务描述
        """
        with self._lock:
            if task_key not in self._data['step1']['tasks']:
                raise KeyError(f"无效的任务键: {task_key}，可用: task1-task4")
            self._data['step1']['tasks'][task_key] = text
            self._save()

    def update_step1_notes(self, notes: List[str]):
        """替换 Step1 注意事项列表"""
        with self._lock:
            self._data['step1']['notes'] = notes
            self._save()

    def update_step2_system_role(self, text: str):
        """更新 Step2 系统角色"""
        with self._lock:
            self._data['step2']['system_role'] = text
            self._save()

    def update_step2_classification_rules(self, rules: List[str]):
        """替换 Step2 全部分类规则"""
        with self._lock:
            self._data['step2']['classification_rules'] = rules
            self._save()

    def add_step2_rule(self, rule: str):
        """在 Step2 分类规则末尾追加一条规则"""
        with self._lock:
            self._data['step2']['classification_rules'].append(rule)
            self._save()
        print(f"[PromptManager] 已添加 Step2 规则: {rule[:50]}...")

    def update_step2_rule(self, index: int, rule: str):
        """
        修改 Step2 的某一条分类规则

        Args:
            index: 规则索引（0-based）
            rule: 新的规则文本
        """
        with self._lock:
            rules = self._data['step2']['classification_rules']
            if index < 0 or index >= len(rules):
                raise IndexError(f"规则索引 {index} 超出范围 [0, {len(rules) - 1}]")
            rules[index] = rule
            self._save()
        print(f"[PromptManager] 已更新 Step2 规则索引 {index}")

    def remove_step2_rule(self, index: int):
        """
        删除 Step2 的某一条分类规则

        Args:
            index: 规则索引（0-based）
        """
        with self._lock:
            rules = self._data['step2']['classification_rules']
            if index < 0 or index >= len(rules):
                raise IndexError(f"规则索引 {index} 超出范围 [0, {len(rules) - 1}]")
            removed = rules.pop(index)
            self._save()
        print(f"[PromptManager] 已删除 Step2 规则: {removed[:50]}...")

    def update_step2_requirements(self, reqs: List[str]):
        """替换 Step2 要求列表"""
        with self._lock:
            self._data['step2']['requirements'] = reqs
            self._save()

    def update_step2_location_prompt(self, template: str):
        """
        更新 Step2 的 location 选择提示模板

        Args:
            template: 模板字符串，可用 {location} 作为占位符
        """
        with self._lock:
            self._data['step2']['location_selection_prompt'] = template
            self._save()

    def update_step2_location_requirements(self, reqs: List[str]):
        """替换 Step2 location 选择要求列表"""
        with self._lock:
            self._data['step2']['location_requirements'] = reqs
            self._save()

    # ==================== 通用方法 ====================

    def get_version(self) -> str:
        """获取配置文件版本号"""
        return self._data.get('version', '0.0.0')

    def get_raw_data(self) -> dict:
        """获取完整的原始配置数据（只读副本）"""
        with self._lock:
            return json.loads(json.dumps(self._data, ensure_ascii=False))

    def export_dump(self, filepath: str):
        """
        导出当前配置到指定文件

        Args:
            filepath: 导出目标文件路径
        """
        with self._lock:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        print(f"[PromptManager] 配置已导出到 {filepath}")


# 全局单例（可选，方便跨模块共享）
_prompt_manager_instance: Optional[PromptManager] = None


def get_prompt_manager(prompts_path: str = "data/rules/prompts.json") -> PromptManager:
    """
    获取全局 PromptManager 单例

    Args:
        prompts_path: prompts.json 文件路径

    Returns:
        PromptManager 实例
    """
    global _prompt_manager_instance
    if _prompt_manager_instance is None:
        _prompt_manager_instance = PromptManager(prompts_path)
    return _prompt_manager_instance