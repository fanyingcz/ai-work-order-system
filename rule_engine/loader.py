"""
规则引擎模块 - 规则加载器
"""
import json
from pathlib import Path
from typing import List
from .models import StandardizedRule
from db import get_db


def load_rules_from_json(json_path: str) -> List[dict]:
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_all_rules(json_dir: str) -> List[StandardizedRule]:
    raw_rules = None

    try:
        db = get_db()
        if db.rules_data_exists():
            db_results = db.get_all_categories()
            if db_results:
                raw_rules = []
                for row in db_results:
                    # Parse required_cert from DB (comma-separated or need to join from category_required_certs)
                    raw_cert = row.get('required_cert', '')
                    if isinstance(raw_cert, str):
                        certs = [c.strip() for c in raw_cert.split('及') if c.strip()] if raw_cert else []
                    elif isinstance(raw_cert, list):
                        certs = raw_cert
                    else:
                        certs = []
                    raw_rules.append({
                        'id': row.get('rule_id'),
                        'category': row.get('category', ''),
                        'subCategory': row.get('sub_category', ''),
                        'problem': row.get('problem', ''),
                        'priority': row.get('priority', ''),
                        'required_cert': certs,
                        'target_dept_semantic': row.get('target_dept_semantic', ''),
                        'trigger_keywords': row.get('trigger_keywords', []),
                        'trigger_location': row.get('trigger_location', [])
                    })
                print(f"[RuleEngine Loader] loaded {len(raw_rules)} rules from DB")
    except Exception as e:
        print(f"[RuleEngine Loader] DB load failed, fallback to JSON: {e}")

    if raw_rules is None:
        category_file = Path(json_dir) / 'category.json'
        if not category_file.exists():
            raise FileNotFoundError(f"category.json not found: {category_file}")
        raw_rules = load_rules_from_json(str(category_file))
        print(f"[RuleEngine Loader] loaded {len(raw_rules)} rules from JSON")

    all_rules = []
    for raw_rule in raw_rules:
        certs = raw_rule.get('required_cert', [])
        if isinstance(certs, str):
            certs = [certs] if certs else []
        standardized_rule = StandardizedRule(
            rule_id=str(raw_rule.get('id', '')),
            category=raw_rule.get('category', ''),
            sub_category=raw_rule.get('subCategory', ''),
            problem=raw_rule.get('problem', ''),
            priority=raw_rule.get('priority', ''),
            required_cert=certs,
            target_dept_semantic=raw_rule.get('target_dept_semantic', ''),
            trigger_keywords=raw_rule.get('trigger_keywords', []),
            trigger_location=raw_rule.get('trigger_location', [])
        )
        all_rules.append(standardized_rule)

    return all_rules