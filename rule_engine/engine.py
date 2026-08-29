"""
规则引擎模块 - 规则引擎核心

【文件职责】
根据输入的 subCategory、trigger_keywords 和可选的 trigger_location，
通过关键词匹配和位置匹配，输出对应的 problem、priority、required_cert、target_dept_semantic。

【核心功能】
1. 加载 category.json 中的所有规则
2. 根据 subCategory 过滤规则
3. 根据 trigger_keywords 进行关键词模糊匹配（输入关键词命中规则任意关键词即匹配）
4. 如果提供了 trigger_location，再进行位置匹配
5. 根据匹配结果数量决定输出状态

【匹配逻辑】
- 二输入（subCategory + trigger_keywords）：匹配到唯一规则 → MATCHED；匹配到多条 → MISSING（缺 trigger_location）；匹配不到 → NO_MATCH
- 三输入（subCategory + trigger_keywords + trigger_location）：
  - 位置匹配到唯一规则 → MATCHED（精准匹配）
  - 位置匹配不到或匹配到多条 → 降级为二输入，取第一条 keyword_matched 结果作为保底输出（MATCHED）

【状态标识】
- MATCHED: 规则匹配成功（可能是精准匹配或降级保底匹配）
- NO_MATCH: 没有匹配到任何规则
- MISSING: 二输入情况下匹配到多条规则，缺少 trigger_location 无法精确匹配
- CONFLICT: 已废弃（三输入降级为保底机制，不再返回冲突）

【保底机制】
当三输入（含 trigger_location）无法确定唯一结果时，自动降级为二输入匹配结果，
取关键词匹配到的第一条规则作为保底输出。确保在有 trigger_keywords 匹配的情况下
始终能返回一个合理的结果。
"""

from typing import Optional, Dict, Any, List
from .loader import load_all_rules
from .models import RuleInput, RuleOutput


class RuleEngine:
    """
    规则引擎类

    负责加载规则、执行匹配逻辑，返回匹配结果。

    Attributes:
        rules_dir (str): 规则文件所在目录
        _rules (List[StandardizedRule]): 已加载的规则列表
        _rules_loaded (bool): 规则是否已加载
    """

    def __init__(self, rules_dir: str = "data/rules"):
        self.rules_dir = rules_dir
        self._rules = []
        self._rules_loaded = False

    def init(self):
        """初始化规则引擎，加载规则数据"""
        self._rules = load_all_rules(self.rules_dir)
        self._rules_loaded = True
        print(f"[RuleEngine] 已加载 {len(self._rules)} 条规则")

    def reload(self):
        """重新加载规则"""
        self._rules_loaded = False
        self.init()

    def _keyword_match(self, input_keywords: List[str], rule_keywords: List[str]) -> bool:
        """
        判断输入关键词是否命中规则的任意关键词

        输入关键词必须与规则关键词完全相等（大小写不敏感），
        不支持子串匹配，确保"灯不亮"和"楼道灯不亮"作为两个独立条件。

        Args:
            input_keywords: 用户输入的关键词列表
            rule_keywords: 规则定义的关键词列表

        Returns:
            bool: 匹配成功返回 True
        """
        for ik in input_keywords:
            ik_lower = ik.strip().lower()
            if not ik_lower:
                continue
            for rk in rule_keywords:
                rk_lower = rk.strip().lower()
                # 输入关键词与规则关键词完全相等（大小写不敏感）
                if ik_lower == rk_lower:
                    return True
        return False

    def _location_match(self, input_location: str, rule_locations: List[str]) -> bool:
        """
        判断输入位置与规则位置是否匹配

        Args:
            input_location: 用户输入的位置
            rule_locations: 规则定义的位置列表

        Returns:
            bool: 匹配成功返回 True
        """
        il_lower = input_location.strip().lower()
        if not il_lower:
            return False
        for rl in rule_locations:
            rl_lower = rl.strip().lower()
            if il_lower in rl_lower or rl_lower in il_lower:
                return True
        return False

    def match(self, input_data: RuleInput) -> Optional[RuleOutput]:
        """
        执行规则匹配

        根据输入的 subCategory、trigger_keywords 和可选的 trigger_location
        从规则列表中找出匹配的规则。

        匹配流程：
        1. 按 subCategory 精确过滤规则
        2. 按 trigger_keywords 模糊匹配
        3. 如果有 trigger_location，进一步按位置匹配
        4. 根据匹配结果数量决定输出

        Args:
            input_data: 规则输入数据

        Returns:
            RuleOutput: 规则输出结果，失败返回 None
        """
        if not self._rules_loaded:
            self.init()

        if not input_data.sub_category or not input_data.trigger_keywords:
            return RuleOutput(
                status='NO_MATCH',
                missing_fields=['sub_category', 'trigger_keywords']
            )

        # Step 1: 按 subCategory 精确过滤
        category_matched = [
            r for r in self._rules
            if r.sub_category == input_data.sub_category
        ]

        if not category_matched:
            return RuleOutput(
                status='NO_MATCH',
                missing_fields=[]
            )

        # Step 2: 按 trigger_keywords 模糊匹配
        keyword_matched = [
            r for r in category_matched
            if self._keyword_match(input_data.trigger_keywords, r.trigger_keywords)
        ]

        if not keyword_matched:
            return RuleOutput(
                status='NO_MATCH',
                missing_fields=[]
            )

        # Step 3: 根据是否提供 trigger_location 进行分支处理
        if input_data.trigger_location:
            # 三输入模式：进一步按位置匹配
            location_matched = [
                r for r in keyword_matched
                if self._location_match(input_data.trigger_location, r.trigger_location)
            ]

            if len(location_matched) == 1:
                # 三输入精准匹配到唯一结果
                result = location_matched[0]
                return RuleOutput(
                    rule_id=result.rule_id,
                    problem=result.problem,
                    priority=result.priority,
                    required_cert=result.required_cert,
                    target_dept_semantic=result.target_dept_semantic,
                    status='MATCHED'
                )
            else:
                # 三输入位置匹配不到（最常见的降级场景）：
                # 用户提供了 trigger_location，但不在任何规则的 location 列表中。
                # 此时降级为二输入匹配，取 keyword_matched 第一条作为保底输出，
                # 确保在有关键词匹配的情况下始终能返回合理结果。
                result = keyword_matched[0]
                return RuleOutput(
                    rule_id=result.rule_id,
                    problem=result.problem,
                    priority=result.priority,
                    required_cert=result.required_cert,
                    target_dept_semantic=result.target_dept_semantic,
                    status='MATCHED'
                )
        else:
            # 二输入模式：只有 subCategory + trigger_keywords
            if len(keyword_matched) == 1:
                result = keyword_matched[0]
                return RuleOutput(
                    rule_id=result.rule_id,
                    problem=result.problem,
                    priority=result.priority,
                    required_cert=result.required_cert,
                    target_dept_semantic=result.target_dept_semantic,
                    status='MATCHED'
                )
            elif len(keyword_matched) > 1:
                # 多条匹配 → MISSING，需要 trigger_location 来精确匹配
                return RuleOutput(
                    status='MISSING',
                    missing_fields=['trigger_location']
                )
            else:
                return RuleOutput(
                    status='NO_MATCH',
                    missing_fields=[]
                )

    def match_dict(self, sub_category: str,
                   trigger_keywords: List[str],
                   trigger_location: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        字典接口的规则匹配方法

        Args:
            sub_category: 维修子类别
            trigger_keywords: 触发关键词列表
            trigger_location: 触发位置（可选）

        Returns:
            Optional[Dict[str, Any]]: 匹配结果的字典表示
        """
        input_data = RuleInput(
            sub_category=sub_category,
            trigger_keywords=trigger_keywords,
            trigger_location=trigger_location
        )
        result = self.match(input_data)
        return result.to_dict() if result else None