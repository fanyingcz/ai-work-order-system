"""
Worker Assigner - assigns a worker based on required certifications and property company.

Logic:
  Input: required_cert (List[str]), property_company (str), maintenance_unit (str)
  1. Find all workers whose certs contain ALL required_cert
  2. Filter by matching property_company (company) or maintenance_unit (department)
  3. Among matching workers, pick the one with fewest current 'processing' orders
  4. Return that worker's id
"""

from typing import Optional, List, Dict, Any
from db import get_db


def assign_worker(required_cert: List[str], property_company: str,
                  maintenance_unit: Optional[str] = None) -> Optional[int]:
    """
    Assign a worker with all required certifications, matching the property company,
    with the lightest current processing workload.

    Args:
        required_cert: list of certificate strings required
        property_company: the property company (区域中心) to match
        maintenance_unit: the maintenance unit (区域中心维修单位) to match

    Returns:
        worker_id (int) if found, None otherwise
    """
    if not required_cert:
        return None

    try:
        db = get_db()
        conn = db._get_connection()
        with conn.cursor() as c:
            # Step 1: Find all workers whose certs contain ALL required_cert
            # Workers stored as JSON array string in certs column
            if maintenance_unit:
                c.execute(
                    "SELECT id, name, company, department, certs FROM workers "
                    "WHERE company = %s OR department = %s",
                    (property_company or '', maintenance_unit))
            elif property_company:
                c.execute("SELECT id, name, company, department, certs FROM workers WHERE company = %s",
                           (property_company,))
            else:
                c.execute("SELECT id, name, company, department, certs FROM workers")
            scoped_workers = c.fetchall()

            # 如果区域中心下没有符合的工人，扩大到全部工人库
            if not scoped_workers:
                c.execute("SELECT id, name, company, department, certs FROM workers")
                scoped_workers = c.fetchall()

            # Filter: certs must contain ALL required_cert
            import json
            matching_workers = []
            for w in scoped_workers:
                try:
                    worker_certs = json.loads(w['certs']) if isinstance(w['certs'], str) else w['certs']
                except (json.JSONDecodeError, TypeError):
                    continue
                if not isinstance(worker_certs, list):
                    worker_certs = [worker_certs] if worker_certs else []
                # Check all required certs are in worker's certs
                if all(rc in worker_certs for rc in required_cert):
                    matching_workers.append(w)

            if not matching_workers:
                print(f"[WorkerAssigner] No worker found with all certs {required_cert} for company {property_company}")
                return None

            # Step 2: For each matching worker, count their current 'processing' orders
            worker_ids = [w['id'] for w in matching_workers]
            placeholders = ','.join(['%s'] * len(worker_ids))
            c.execute(f"""
                SELECT worker_id, COUNT(*) as cnt FROM work_orders
                WHERE worker_id IN ({placeholders}) AND status = 'processing'
                GROUP BY worker_id
            """, worker_ids)
            workload = {row['worker_id']: row['cnt'] for row in c.fetchall()}

            # Step 3: Pick worker with minimum workload
            best_worker = min(matching_workers, key=lambda w: workload.get(w['id'], 0))
            print(f"[WorkerAssigner] Assigned worker id={best_worker['id']} name={best_worker['name']} "
                  f"certs={best_worker['certs']} workload={workload.get(best_worker['id'], 0)}")
            return best_worker['id']

    except Exception as e:
        print(f"[WorkerAssigner] Error: {e}")
        return None


def start_workorder(order_no: str) -> Dict[str, Any]:
    """Mark a work order as processing. Only valid from PENDING status."""
    try:
        db = get_db()
        conn = db._get_connection()
        with conn.cursor() as c:
            c.execute("UPDATE work_orders SET status = 'processing' WHERE order_no = %s AND UPPER(status) = 'PENDING'",
                       (order_no,))
            if c.rowcount == 0:
                c.execute("SELECT status FROM work_orders WHERE order_no = %s", (order_no,))
                row = c.fetchone()
                current = row['status'] if row else 'NOT_FOUND'
                return {'status': 'ERROR', 'message': f'Cannot start: current status is {current}'}
            return {'status': 'SUCCESS', 'message': f'Work order {order_no} marked as processing'}
    except Exception as e:
        return {'status': 'ERROR', 'message': str(e)}


def worker_complete_workorder(order_no: str, worker_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Mark a work order as worker_completed. Valid from PROCESSING status.
    
    This is called by the worker frontend when the worker finishes their part.
    The status changes: PROCESSING -> WORKER_COMPLETED.
    If worker_id is provided, verify the order is assigned to that worker.
    """
    try:
        db = get_db()
        conn = db._get_connection()
        with conn.cursor() as c:
            # First check current status and worker assignment
            c.execute("SELECT status, worker_id FROM work_orders WHERE order_no = %s", (order_no,))
            row = c.fetchone()
            if not row:
                return {'status': 'ERROR', 'message': f'Work order {order_no} not found'}
            
            current = row['status']
            if current.upper() != 'PROCESSING':
                return {'status': 'ERROR', 'message': f'Cannot complete: current status is {current}'}
            
            if worker_id is not None:
                assigned_worker = row.get('worker_id')
                if assigned_worker is None:
                    return {'status': 'ERROR', 'message': 'Work order has no assigned worker'}
                if int(assigned_worker) != int(worker_id):
                    return {'status': 'ERROR', 'message': 'Work order is not assigned to this worker'}
            
            c.execute("UPDATE work_orders SET status = 'worker_completed' WHERE order_no = %s AND UPPER(status) = 'PROCESSING'",
                       (order_no,))
            if c.rowcount == 0:
                return {'status': 'ERROR', 'message': f'Cannot complete: current status is {current}'}
            return {'status': 'SUCCESS', 'message': f'Work order {order_no} marked as worker_completed'}
    except Exception as e:
        return {'status': 'ERROR', 'message': str(e)}


def complete_workorder(order_no: str) -> Dict[str, Any]:
    """Mark a work order as completed. Valid from PENDING, PROCESSING or WORKER_COMPLETED status."""
    try:
        db = get_db()
        conn = db._get_connection()
        with conn.cursor() as c:
            c.execute("""UPDATE work_orders SET status = 'completed' 
                         WHERE order_no = %s AND UPPER(status) IN ('PENDING', 'PROCESSING', 'WORKER_COMPLETED')""",
                       (order_no,))
            if c.rowcount == 0:
                c.execute("SELECT status FROM work_orders WHERE order_no = %s", (order_no,))
                row = c.fetchone()
                current = row['status'] if row else 'NOT_FOUND'
                return {'status': 'ERROR', 'message': f'Cannot complete: current status is {current}'}
            return {'status': 'SUCCESS', 'message': f'Work order {order_no} marked as completed'}
    except Exception as e:
        return {'status': 'ERROR', 'message': str(e)}
