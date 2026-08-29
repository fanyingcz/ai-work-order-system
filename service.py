"""
Smart Work Order System - Unified external entry point.
"""
from typing import Optional, Dict, Any
from input_processor import InputProcessor
from address_handler import AddressHandler
from rule_engine import RuleEngine
from rule_engine.worker_assigner import assign_worker, complete_workorder
from work_order import WorkOrderGenerator


class Service:

    def __init__(self, rules_dir: str = "data/rules"):
        self.rules_dir = rules_dir
        self.input_processor = InputProcessor(rules_dir=rules_dir)
        self.address_handler = AddressHandler(rules_dir=rules_dir)
        self.rule_engine = RuleEngine(rules_dir=rules_dir)
        self.work_order_generator = WorkOrderGenerator(json_dir=rules_dir)

    def handle_request(self, user_id: str, user_input: str,
                       reporter_name: str = None, reporter_phone: str = None) -> Dict[str, Any]:
        details = {}
        try:
            # Step 1: Input processing
            input_result = self.input_processor.process_user_input(user_id, user_input)

            # 合并 API 传入的报修人信息与 LLM 提取的信息
            # API 值（前端/系统传入）优先，LLM 提取值作为补充
            final_reporter_name = reporter_name or input_result.get('reporter_name')
            final_reporter_phone = reporter_phone or input_result.get('reporter_phone')

            details['input_processor'] = {
                'status': input_result.get('status'),
                'content': input_result.get('content'),
                'prechoice_subcategories': input_result.get('prechoice_subcategories'),
                'address': input_result.get('address'),
                'location': input_result.get('location'),
                'trigger_keyword': input_result.get('trigger_keyword'),
                'trigger_location': input_result.get('trigger_location'),
                'reporter_name': final_reporter_name,
                'reporter_phone': final_reporter_phone,
                'message_to_user': input_result.get('message_to_user'),
                'need_more_input': input_result.get('need_more_input', False)
            }

            if input_result.get('need_more_input', False):
                return {'status': 'MISS', 'work_order': None,
                        'message': input_result.get('message_to_user', 'Missing info'),
                        'details': details}

            if input_result['status'] != 'SUCCESS':
                return {'status': 'ERROR', 'work_order': None,
                        'message': f'Input processing failed: {input_result.get("message_to_user", "")}',
                        'details': details}

            trigger_keyword = input_result.get('trigger_keyword')
            address = input_result.get('address')
            trigger_location = input_result.get('trigger_location')
            prechoice_subcategories = input_result.get('prechoice_subcategories', [])

            if not trigger_keyword:
                return {'status': 'MISS', 'work_order': None,
                        'message': 'Cannot match specific repair keyword', 'details': details}

            # Step 2: Address processing
            property_company = 'miss'
            maintenance_unit = 'miss'
            processed_address = address

            if address:
                address_result = self.address_handler.process(address)
                details['address_handler'] = {
                    'status': address_result.status,
                    'property_company': address_result.property_company,
                    'maintenance_unit': address_result.maintenance_unit,
                    'reliability': address_result.address_info.reliability if address_result.address_info else None,
                    'address_info': address_result.address_info.to_dict() if address_result.address_info else None
                }

                reliability = address_result.address_info.reliability if address_result.address_info else None
                district = address_result.address_info.district if address_result.address_info else ""
                if not (reliability is not None and reliability >= 7 and district == "浦东新区"):
                    return {'status': 'WRONG', 'work_order': None, 'message': 'WRONG', 'details': details}

                if address_result.property_company:
                    property_company = address_result.property_company
                if address_result.maintenance_unit:
                    maintenance_unit = address_result.maintenance_unit
            else:
                details['address_handler'] = {'status': 'MISS', 'property_company': None,
                                               'maintenance_unit': None, 'reliability': None, 'address_info': None}

            # Step 3: Rule engine matching (try each prechoice subcategory)
            rule_result = None
            matched_sub_category = None
            for sub_category in prechoice_subcategories:
                current_result = self.rule_engine.match_dict(
                    sub_category=sub_category,
                    trigger_keywords=[trigger_keyword],
                    trigger_location=trigger_location
                )
                if current_result and current_result.get('status') == 'MATCHED':
                    rule_result = current_result
                    matched_sub_category = sub_category
                    break

            if not rule_result:
                return {'status': 'MISS', 'work_order': None,
                        'message': 'Cannot match repair rule', 'details': details}

            priority = rule_result.get('priority', '')
            required_cert = rule_result.get('required_cert', [])
            target_dept_semantic = rule_result.get('target_dept_semantic', '')
            problem = rule_result.get('problem', trigger_keyword)

            # Step 4: Worker assignment
            worker_id = None
            if isinstance(required_cert, list) and required_cert and property_company != 'miss':
                worker_id = assign_worker(required_cert, property_company, maintenance_unit)

            details['rule_engine'] = {
                'matched_sub_category': matched_sub_category,
                'status': rule_result.get('status'),
                'problem': problem,
                'priority': priority,
                'required_cert': required_cert,
                'target_dept_semantic': target_dept_semantic,
                'worker_id': worker_id
            }

            # Step 5: Generate work order
            work_order = self.work_order_generator.generate(
                user_input=user_input, problem=problem, priority=priority,
                target_dept_semantic=target_dept_semantic,
                property_company=property_company, maintenance_unit=maintenance_unit,
                worker_id=worker_id, address=processed_address,
                reporter_name=final_reporter_name, reporter_phone=final_reporter_phone
            )

            save_result = self.work_order_generator.save_to_db(work_order)
            details['work_order'] = {
                'order_no': work_order.order_no,
                'accept_time': work_order.accept_time.isoformat() if work_order.accept_time else None,
                'db_save_status': save_result.get('status'),
                'db_save_message': save_result.get('message')
            }

            # 在返回的 work_order 字典中附加工人信息（姓名 + 电话），供前端直接使用
            work_order_dict = work_order.to_dict()
            if worker_id is not None:
                from db import get_db as _get_db
                worker_row = _get_db().get_worker_by_id(worker_id)
                if worker_row:
                    work_order_dict['worker_info'] = {
                        'id': worker_row.get('id'),
                        'name': worker_row.get('name'),
                        'phone': worker_row.get('phone'),
                        'company': worker_row.get('company'),
                        'department': worker_row.get('department')
                    }

            return {'status': 'SUCCESS', 'work_order': work_order_dict,
                    'message': 'Work order generated and saved to database',
                    'details': details}

        except Exception as e:
            return {'status': 'ERROR', 'work_order': None,
                    'message': f'System error: {str(e)}', 'details': details}

    def complete_order(self, order_no: str) -> Dict[str, Any]:
        """Mark a work order as completed."""
        return complete_workorder(order_no)
