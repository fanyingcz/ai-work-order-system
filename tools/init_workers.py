"""初始化 / 补齐 workers 表与维修人员数据。

两种用法：
1. 命令行：python tools/init_workers.py [--force]
2. 作为模块被 api.py 在启动时调用，保证全新数据库也能直接跑起来
   （以前这张表只能手工建，导致云端新库的统计页和派单全挂）。
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_CREATE_WORKERS_SQL = """CREATE TABLE IF NOT EXISTS workers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    phone VARCHAR(20),
    company VARCHAR(200) NOT NULL,
    department VARCHAR(200) NOT NULL,
    certs TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_company (company),
    INDEX idx_department (department)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""

# 物业/维修单位名：与 address_mapping.json 中的脱敏口径保持一致
_COMPANIES = [
    ('区域中心1', '区域中心1维修单位'),
    ('区域中心2', '区域中心2维修单位'),
    ('区域中心3', '区域中心3维修单位'),
    ('区域中心4', '区域中心4维修单位'),
    ('区域中心5', '区域中心5维修单位'),
]


def ensure_workers(force: bool = False, base_dir: str = None) -> int:
    """确保 workers 表存在且有数据，返回表中最终人数。

    Args:
        force: 为 True 时先清空重建（会解除工单里已指派的工人引用）
        base_dir: 项目根目录，用于定位 data/rules/category.json
    """
    from db import get_db

    base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db = get_db()
    c = db._get_connection().cursor()

    c.execute(_CREATE_WORKERS_SQL)

    c.execute("SELECT COUNT(*) as cnt FROM workers")
    worker_count = c.fetchone()['cnt']

    if force and worker_count > 0:
        # 先解除工单中已指派的旧工人引用，避免指向重建后的错误人员
        c.execute("UPDATE work_orders SET worker_id = NULL WHERE worker_id IS NOT NULL")
        c.execute("DELETE FROM workers")
        print(f"[init_workers] 已清空 {worker_count} 条旧工人数据")
        worker_count = 0

    if worker_count == 0:
        rules_path = os.path.join(base_dir, 'data', 'rules', 'category.json')
        with open(rules_path, 'r', encoding='utf-8') as f:
            rules = json.load(f)
        for rule in rules:
            certs = rule.get('required_cert', [])
            if isinstance(certs, str):
                certs = [certs] if certs else []
            for idx, (comp, dept) in enumerate(_COMPANIES):
                c.execute(
                    'INSERT INTO workers (name, phone, company, department, certs) '
                    'VALUES (%s,%s,%s,%s,%s)',
                    (f'worker_{rule["problem"]}_{idx+1}',
                     f'138{rule["id"]:04d}{idx+1}0000', comp, dept,
                     json.dumps(certs, ensure_ascii=False))
                )
        print(f'[init_workers] 已生成 {len(rules) * len(_COMPANIES)} 名维修人员'
              f'（{len(_COMPANIES)} 个区域中心）')

    # 确保 work_orders 有 worker_id 列（老库升级用）
    try:
        c.execute("ALTER TABLE work_orders ADD COLUMN worker_id INT DEFAULT NULL "
                  "AFTER target_dept_semantic")
        c.execute("ALTER TABLE work_orders ADD INDEX idx_worker_id (worker_id)")
        print("worker_id column added to work_orders")
    except Exception as e:
        # 列已存在时必然报错，属于预期路径，不打 ERROR
        print(f"worker_id column already exists (or other error): {e}")

    c.execute("SELECT COUNT(*) as cnt FROM workers")
    return c.fetchone()['cnt']


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="初始化/重建维修人员数据")
    parser.add_argument('--force', action='store_true', help='清空 workers 表后重新生成')
    args = parser.parse_args()
    print(f"Total workers: {ensure_workers(force=args.force)}")
    print("Done")
