"""Initialize workers table and populate data"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_db

parser = argparse.ArgumentParser(description="初始化/重建维修人员数据")
parser.add_argument('--force', action='store_true', help='清空 workers 表后重新生成')
args = parser.parse_args()

db = get_db()
c = db._get_connection().cursor()

# Ensure workers table
c.execute("""CREATE TABLE IF NOT EXISTS workers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    phone VARCHAR(20),
    company VARCHAR(200) NOT NULL,
    department VARCHAR(200) NOT NULL,
    certs TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_company (company),
    INDEX idx_department (department)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

c.execute("SELECT COUNT(*) as cnt FROM workers")
worker_count = c.fetchone()['cnt']

if args.force and worker_count > 0:
    # 先解除工单中已指派的旧工人引用，避免指向重建后的错误人员
    c.execute("UPDATE work_orders SET worker_id = NULL WHERE worker_id IS NOT NULL")
    c.execute("DELETE FROM workers")
    print(f"[init_workers] 已清空 {worker_count} 条旧工人数据")
    worker_count = 0

if worker_count == 0:
    with open('data/rules/category.json', 'r', encoding='utf-8') as f:
        rules = json.load(f)
    companies = [
        ('区域中心1', '区域中心1维修单位'),
        ('区域中心2', '区域中心2维修单位'),
        ('区域中心3', '区域中心3维修单位'),
        ('区域中心4', '区域中心4维修单位'),
        ('区域中心5', '区域中心5维修单位'),
    ]
    for rule in rules:
        certs = rule.get('required_cert', [])
        if isinstance(certs, str):
            certs = [certs] if certs else []
        for idx, (comp, dept) in enumerate(companies):
            c.execute('INSERT INTO workers (name, phone, company, department, certs) VALUES (%s,%s,%s,%s,%s)',
                      (f'worker_{rule["problem"]}_{idx+1}',
                       f'138{rule["id"]:04d}{idx+1}0000', comp, dept,
                       json.dumps(certs, ensure_ascii=False)))
    print(f'[init_workers] 已生成 {len(rules) * len(companies)} 名维修人员（{len(companies)} 个区域中心）')

c.execute("SELECT COUNT(*) as cnt FROM workers")
print(f"Total workers: {c.fetchone()['cnt']}")

# Ensure worker_id column exists in work_orders
try:
    c.execute("ALTER TABLE work_orders ADD COLUMN worker_id INT DEFAULT NULL AFTER target_dept_semantic")
    c.execute("ALTER TABLE work_orders ADD INDEX idx_worker_id (worker_id)")
    print("worker_id column added to work_orders")
except Exception as e:
    print(f"worker_id column already exists (or other error): {e}")

print("Done")
