import json, os
from datetime import datetime
from typing import Optional, Dict, Any, List
from .models import WorkOrder
from db import get_db


class WorkOrderGenerator:
    def __init__(self, json_dir: str = "data/rules"):
        self.json_dir = os.path.abspath(json_dir)
        self.problem_subcategory_map = self._load_problem_subcategory_map()
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # 确保序号表存在
        try:
            get_db().create_sequence_table()
        except Exception as e:
            print(f"[Gen] 创建序号表失败 (可能已存在): {e}")

    def _load_problem_subcategory_map(self) -> Dict[str, str]:
        try:
            db = get_db()
            if db.rules_data_exists():
                r = db.get_problem_subcategory_map()
                if r: print(f"[Gen] loaded {len(r)} mappings from DB"); return r
        except Exception as e: print(f"[Gen] DB err: {e}")
        with open(os.path.join(self.json_dir, 'category.json'), encoding='utf-8') as f:
            rules = json.load(f)
        return {r.get('problem',''): r.get('subCategory','') for r in rules if r.get('problem')}

    def _generate_order_no(self) -> str:
        seq = get_db().get_next_order_sequence()
        return f"WO{datetime.now().strftime('%Y%m%d')}{seq:06d}"

    def _get_sub_category(self, problem: str) -> str:
        return self.problem_subcategory_map.get(problem, '')

    def generate(self, user_input, problem, priority, target_dept_semantic,
                 property_company, maintenance_unit, worker_id=None, address=None,
                 reporter_name=None, reporter_phone=None):
        if not problem: raise ValueError("problem required")
        if not priority: raise ValueError("priority required")
        if not property_company: property_company = 'miss'
        if not maintenance_unit: maintenance_unit = 'miss'
        return WorkOrder(
            order_no=self._generate_order_no(), accept_time=datetime.now(),
            user_input=user_input, sub_category=self._get_sub_category(problem),
            problem=problem, property_company=property_company,
            maintenance_unit=maintenance_unit, priority=priority,
            target_dept_semantic=target_dept_semantic, worker_id=worker_id,
            status='PENDING', address=address,
            reporter_name=reporter_name, reporter_phone=reporter_phone)

    def save_to_db(self, wo) -> Dict[str, Any]:
        try:
            d = wo.to_dict()
            at = d.get('accept_time')
            if isinstance(at, datetime): at = at.isoformat()
            conn = get_db()._get_connection()
            with conn.cursor() as c:
                c.execute("""INSERT INTO work_orders
                    (order_no, accept_time, user_input, sub_category, problem,
                     property_company, maintenance_unit, priority, required_cert,
                     target_dept_semantic, worker_id, status, address,
                     reporter_name, reporter_phone)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE
                        user_input=VALUES(user_input), sub_category=VALUES(sub_category),
                        problem=VALUES(problem), property_company=VALUES(property_company),
                        maintenance_unit=VALUES(maintenance_unit), priority=VALUES(priority),
                        required_cert=VALUES(required_cert),
                        target_dept_semantic=VALUES(target_dept_semantic),
                        worker_id=VALUES(worker_id), status=VALUES(status),
                        address=VALUES(address),
                        reporter_name=VALUES(reporter_name),
                        reporter_phone=VALUES(reporter_phone)""",
                    (d.get('order_no'), at, d.get('user_input'), d.get('sub_category'),
                     d.get('problem'), d.get('property_company'), d.get('maintenance_unit'),
                     d.get('priority'), None, d.get('target_dept_semantic'),
                     d.get('worker_id'), d.get('status','PENDING'), d.get('address'),
                     d.get('reporter_name'), d.get('reporter_phone')))
                return {'status':'SUCCESS','id':c.lastrowid}
        except Exception as e: return {'status':'ERROR','message':str(e)}

    def save_to_json(self, wo, output_file="result/result.json"):
        try:
            path = os.path.join(self.project_root, output_file)
            d = wo.to_dict()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = []
            if os.path.exists(path):
                try: data = json.load(open(path, encoding='utf-8'))
                except: pass
            data.insert(0, d)
            json.dump(data, open(path,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
            return {'status':'SUCCESS','record_count':len(data)}
        except Exception as e: return {'status':'ERROR','message':str(e)}

    def save_all(self, wo, output_file="result/result.json"):
        return {'json_result':self.save_to_json(wo,output_file),
                'db_result':self.save_to_db(wo), 'order_no':wo.order_no}