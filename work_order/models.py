"""Work order data models."""
from typing import Optional, List
from datetime import datetime


class WorkOrderItem:
    problem: str
    sub_category: str
    priority: str
    required_cert: List[str]
    target_dept_semantic: str

    def __init__(self, problem, sub_category, priority, required_cert, target_dept_semantic):
        self.problem = problem
        self.sub_category = sub_category
        self.priority = priority
        self.required_cert = required_cert if required_cert else []
        self.target_dept_semantic = target_dept_semantic

    def to_dict(self):
        return {"problem": self.problem, "sub_category": self.sub_category,
                "priority": self.priority, "required_cert": self.required_cert,
                "target_dept_semantic": self.target_dept_semantic}


class WorkOrder:
    order_no: str
    accept_time: datetime
    user_input: str
    sub_category: str
    problem: str
    property_company: str
    maintenance_unit: str
    priority: str
    target_dept_semantic: str
    worker_id: Optional[int]
    status: str
    address: Optional[str]
    reporter_name: Optional[str]
    reporter_phone: Optional[str]

    def __init__(self, order_no, accept_time, user_input, sub_category, problem,
                 property_company, maintenance_unit, priority, target_dept_semantic,
                 worker_id=None, status='PENDING', address=None,
                 reporter_name=None, reporter_phone=None):
        self.order_no = order_no
        self.accept_time = accept_time
        self.user_input = user_input
        self.sub_category = sub_category
        self.problem = problem
        self.property_company = property_company
        self.maintenance_unit = maintenance_unit
        self.priority = priority
        self.target_dept_semantic = target_dept_semantic
        self.worker_id = worker_id
        self.status = status
        self.address = address
        self.reporter_name = reporter_name
        self.reporter_phone = reporter_phone

    def to_dict(self):
        return {
            "order_no": self.order_no,
            "accept_time": self.accept_time.isoformat() if self.accept_time else None,
            "user_input": self.user_input,
            "sub_category": self.sub_category,
            "problem": self.problem,
            "property_company": self.property_company,
            "maintenance_unit": self.maintenance_unit,
            "priority": self.priority,
            "target_dept_semantic": self.target_dept_semantic,
            "worker_id": self.worker_id,
            "status": self.status,
            "address": self.address,
            "reporter_name": self.reporter_name,
            "reporter_phone": self.reporter_phone
        }

    def to_json(self):
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)