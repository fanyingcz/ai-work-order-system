from typing import List, Optional, Dict, Any


class RuleInput:
    sub_category: str
    trigger_keywords: List[str]
    trigger_location: Optional[str]

    def __init__(self, sub_category: str, trigger_keywords: List[str],
                 trigger_location: Optional[str] = None):
        self.sub_category = sub_category
        self.trigger_keywords = trigger_keywords if trigger_keywords else []
        self.trigger_location = trigger_location


class RuleOutput:
    rule_id: str
    problem: str
    priority: str
    required_cert: List[str]  # changed to list
    target_dept_semantic: str
    status: str
    missing_fields: List[str]

    def __init__(self, rule_id: str = '', problem: str = '', priority: str = '',
                 required_cert=None, target_dept_semantic: str = '',
                 status: str = 'MATCHED', missing_fields: Optional[List[str]] = None):
        self.rule_id = rule_id
        self.problem = problem
        self.priority = priority
        self.required_cert = required_cert if required_cert else []
        self.target_dept_semantic = target_dept_semantic
        self.status = status
        self.missing_fields = missing_fields if missing_fields else []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "problem": self.problem,
            "priority": self.priority,
            "required_cert": self.required_cert,
            "target_dept_semantic": self.target_dept_semantic,
            "status": self.status
        }


class StandardizedRule:
    rule_id: str
    category: str
    sub_category: str
    problem: str
    priority: str
    required_cert: List[str]  # changed to list
    target_dept_semantic: str
    trigger_keywords: List[str]
    trigger_location: List[str]

    def __init__(self, rule_id: str, category: str, sub_category: str,
                 problem: str, priority: str, required_cert,
                 target_dept_semantic: str,
                 trigger_keywords: Optional[List[str]] = None,
                 trigger_location: Optional[List[str]] = None):
        self.rule_id = rule_id
        self.category = category
        self.sub_category = sub_category
        self.problem = problem
        self.priority = priority
        self.required_cert = required_cert if required_cert else []
        self.target_dept_semantic = target_dept_semantic
        self.trigger_keywords = trigger_keywords if trigger_keywords else []
        self.trigger_location = trigger_location if trigger_location else []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "sub_category": self.sub_category,
            "problem": self.problem,
            "priority": self.priority,
            "required_cert": self.required_cert,
            "target_dept_semantic": self.target_dept_semantic,
            "trigger_keywords": self.trigger_keywords,
            "trigger_location": self.trigger_location
        }