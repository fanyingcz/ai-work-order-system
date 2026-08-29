"""
Error Feedback Handler

Handles user error feedback on work order problem classifications.

Flow:
1. User submits: order_no, human_problem, human_keyword
2. System auto-looks-up model_problem from work_orders
3. Record saved with status='pending'
4. Admin approves: status='approved', keyword added to category_trigger_keywords
5. Admin rejects: status='rejected'
"""

from typing import Optional, List, Dict, Any
from db import get_db


class FeedbackHandler:

    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        """Ensure error_feedbacks table exists."""
        try:
            db = get_db()
            conn = db._get_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS error_feedbacks (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        order_no VARCHAR(30) NOT NULL,
                        model_problem VARCHAR(200),
                        human_problem VARCHAR(200) NOT NULL,
                        human_keyword VARCHAR(200) NOT NULL,
                        status VARCHAR(20) DEFAULT 'pending',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_order_no (order_no),
                        INDEX idx_status (status)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
            print("[FeedbackHandler] error_feedbacks table ready")
        except Exception as e:
            print(f"[FeedbackHandler] ensure_table failed: {e}")

    def submit(self, order_no: str, human_problem: str, human_keyword: str) -> Dict[str, Any]:
        """
        Submit error feedback. Auto-lookup model_problem, status=pending.

        Args:
            order_no: Work order number
            human_problem: Human-corrected problem
            human_keyword: Human-provided keyword to add to trigger list
        Returns:
            {'status': 'SUCCESS'/'ERROR', 'message': ..., 'id': ...}
        """
        try:
            db = get_db()
            order = db.get_by_order_no(order_no)
            model_problem = order.get('problem', '') if order else ''
            conn = db._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO error_feedbacks (order_no, model_problem, human_problem, human_keyword, status) "
                    "VALUES (%s, %s, %s, %s, 'pending')",
                    (order_no, model_problem, human_problem, human_keyword)
                )
                return {
                    'status': 'SUCCESS',
                    'message': 'Feedback submitted, pending review',
                    'id': cursor.lastrowid,
                    'model_problem': model_problem,
                    'human_problem': human_problem,
                    'human_keyword': human_keyword
                }
        except Exception as e:
            print(f"[FeedbackHandler] submit failed: {e}")
            return {'status': 'ERROR', 'message': str(e)}

    def get_pending(self) -> List[Dict[str, Any]]:
        """Get all pending feedbacks for review."""
        try:
            db = get_db()
            conn = db._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM error_feedbacks WHERE status='pending' ORDER BY created_at DESC")
                return cursor.fetchall()
        except Exception as e:
            print(f"[FeedbackHandler] get_pending failed: {e}")
            return []

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all feedbacks with pagination."""
        try:
            db = get_db()
            conn = db._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM error_feedbacks ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    (limit, offset))
                return cursor.fetchall()
        except Exception as e:
            print(f"[FeedbackHandler] get_all failed: {e}")
            return []

    def get_by_id(self, feedback_id: int) -> Optional[Dict[str, Any]]:
        """Get a single feedback by id."""
        try:
            db = get_db()
            conn = db._get_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM error_feedbacks WHERE id=%s", (feedback_id,))
                return cursor.fetchone()
        except Exception as e:
            print(f"[FeedbackHandler] get_by_id failed: {e}")
            return None

    def approve(self, feedback_id: int) -> Dict[str, Any]:
        """
        Admin approves a feedback.
        - Status: pending -> approved
        - Adds human_keyword to the corresponding category's trigger_keywords
        """
        try:
            db = get_db()
            fb = self.get_by_id(feedback_id)
            if not fb:
                return {'status': 'ERROR', 'message': 'Feedback not found'}
            if fb['status'] != 'pending':
                return {'status': 'ERROR', 'message': f'Status is not pending: {fb["status"]}'}

            conn = db._get_connection()
            human_problem = fb.get('human_problem', '')
            human_keyword = fb.get('human_keyword', '')

            # Sync keyword to category_trigger_keywords
            if human_problem and human_keyword:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT id FROM categories WHERE problem=%s", (human_problem,))
                    cat = cursor.fetchone()
                    if cat:
                        cat_id = cat['id']
                        cursor.execute(
                            "SELECT id FROM category_trigger_keywords WHERE category_id=%s AND keyword=%s",
                            (cat_id, human_keyword))
                        if not cursor.fetchone():
                            cursor.execute(
                                "INSERT INTO category_trigger_keywords (category_id, keyword) VALUES (%s, %s)",
                                (cat_id, human_keyword))
                            print(f"[FeedbackHandler] Keyword '{human_keyword}' added to category {cat_id}")
                        else:
                            print(f"[FeedbackHandler] Keyword '{human_keyword}' already exists, skipped")

            # Update status
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE error_feedbacks SET status='approved' WHERE id=%s", (feedback_id,))

            return {'status': 'SUCCESS', 'message': 'Feedback approved, keyword synced to rules'}
        except Exception as e:
            print(f"[FeedbackHandler] approve failed: {e}")
            return {'status': 'ERROR', 'message': str(e)}

    def reject(self, feedback_id: int) -> Dict[str, Any]:
        """
        Admin rejects a feedback.
        - Status: pending -> rejected
        - No changes made to rules
        """
        try:
            db = get_db()
            fb = self.get_by_id(feedback_id)
            if not fb:
                return {'status': 'ERROR', 'message': 'Feedback not found'}
            if fb['status'] != 'pending':
                return {'status': 'ERROR', 'message': f'Status is not pending: {fb["status"]}'}

            conn = db._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE error_feedbacks SET status='rejected' WHERE id=%s", (feedback_id,))

            return {'status': 'SUCCESS', 'message': 'Feedback rejected'}
        except Exception as e:
            print(f"[FeedbackHandler] reject failed: {e}")
            return {'status': 'ERROR', 'message': str(e)}