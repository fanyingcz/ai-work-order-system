"""
Error Feedback Module

Handles user-submitted error feedback on work order problem classifications.
Users submit: order_no, correct human_problem, correct human_keyword.
System auto-looks-up model_problem from work_orders table.
Status flow: pending -> approved (keyword synced to rules) / rejected.
"""

from .handler import FeedbackHandler

__all__ = ['FeedbackHandler']