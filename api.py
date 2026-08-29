"""
智能工单系统 - FastAPI 接口层

将系统核心功能包装为 RESTful API，供前端调用。

【启动方式】
    uvicorn api:app --reload --host 0.0.0.0 --port 8000

【依赖安装】
    pip install fastapi uvicorn

【接口概览】
    工单流程：
        POST   /api/v1/work-order/submit         提交报修（完整信息，单次完成）
        POST   /api/v1/work-order/converse        多轮对话式提交（支持补充信息）
        GET    /api/v1/work-order/{order_no}      查询工单详情
        GET    /api/v1/work-orders                工单列表/搜索
        POST   /api/v1/work-orders/search         高级工单搜索
        POST   /api/v1/work-order/{order_no}/complete   完成工单

    多轮对话辅助：
        GET    /api/v1/session/{user_id}          查询当前会话状态
        DELETE /api/v1/session/{user_id}          取消/重置会话
        GET    /api/v1/session/{user_id}/history  查询会话对话历史

    数据查询：
        GET    /api/v1/subcategories              获取所有子类别
        GET    /api/v1/categories                 获取所有分类规则
        GET    /api/v1/keywords                   获取关键词列表
        GET    /api/v1/rules/completeness         检查规则数据完整性

    反馈管理：
        POST   /api/v1/feedback                   提交反馈
        GET    /api/v1/feedback/pending           待审核反馈列表
        GET    /api/v1/feedback/all               全部反馈列表(分页)
        POST   /api/v1/feedback/{id}/approve      审批通过
        POST   /api/v1/feedback/{id}/reject       审批驳回

    地址映射管理：
        GET    /api/v1/address-mappings           地址映射列表
        POST   /api/v1/address-mappings           新增地址映射
        PUT    /api/v1/address-mappings/{id}      更新地址映射
        DELETE /api/v1/address-mappings/{id}      删除地址映射

    系统管理：
        GET    /api/v1/workers                    工人列表
        GET    /api/v1/stats                      统计数据
        GET    /api/v1/health                     健康检查

    模型测试：
        POST   /api/v1/test/run                   启动测试（后台异步）
        GET    /api/v1/test/{task_id}/status      查询测试进度（轮询）
        GET    /api/v1/test/tasks                 历史任务列表
        GET    /api/v1/test/logs                  历史测试日志文件列表
        GET    /api/v1/test/logs/{filename}       下载/查看日志内容

    数据库管理（规则数据 CRUD）：
        GET    /api/v1/admin/subcategories        获取所有子类别定义
        POST   /api/v1/admin/subcategories        新增子类别
        PUT    /api/v1/admin/subcategories/{id}   更新子类别
        DELETE /api/v1/admin/subcategories/{id}   删除子类别
        GET    /api/v1/admin/categories           获取所有分类规则
        POST   /api/v1/admin/categories           新增分类规则
        PUT    /api/v1/admin/categories/{id}      更新分类规则
        DELETE /api/v1/admin/categories/{id}      删除分类规则（级联）
        GET    /api/v1/admin/keywords             获取所有触发关键词
        POST   /api/v1/admin/keywords             新增触发关键词
        PUT    /api/v1/admin/keywords/{id}        更新触发关键词
        DELETE /api/v1/admin/keywords/{id}        删除触发关键词
        GET    /api/v1/admin/locations            获取所有触发位置
        POST   /api/v1/admin/locations            新增触发位置
        PUT    /api/v1/admin/locations/{id}       更新触发位置
        DELETE /api/v1/admin/locations/{id}       删除触发位置

【多轮对话流程说明】
    场景：用户第一次只说了问题描述，没有提供地址。

    第一次调用：
        POST /api/v1/work-order/converse
        {"user_id": "u001", "text": "卫生间顶上漏水"}
        → 返回 MISS 状态，need_more_input: true
        → 会话保持，系统等待用户补充地址

    第二次调用（同样接口）：
        POST /api/v1/work-order/converse
        {"user_id": "u001", "text": "地址是示例区示例小区1号101室"}
        → 系统自动将新输入与之前的信息合并处理
        → 返回 SUCCESS，包含完整工单

    用户可随时通过以下接口检查/重置对话：
        GET  /api/v1/session/u001       → 查看当前对话阶段
        DELETE /api/v1/session/u001     → 重置对话，重新开始
"""

import os
import json
import re
import threading
import time
import random
import sys
from typing import Optional, List, Dict, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import FastAPI, HTTPException, Query, Path, Body, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from service import Service
from db import get_db
from feedback import FeedbackHandler
from input_processor.processor import InputProcessor
from rule_engine.worker_assigner import start_workorder as _assigner_start
from rule_engine.worker_assigner import worker_complete_workorder as _assigner_worker_complete
from rule_engine.worker_assigner import complete_workorder as _assigner_complete

# ============================================================
# 测试任务管理器（后台运行，线程安全）
# ============================================================

class TestTaskManager:
    """
    管理异步运行的测试任务。
    
    测试是长时间操作（10+分钟），通过此管理器在后台线程运行，
    前端通过 task_id 轮询进度和结果。
    """
    
    def __init__(self):
        self._tasks: Dict[str, dict] = {}
        self._lock = threading.Lock()
    
    def create_task(self, task_id: str, total: int, workers: int, sequential: bool):
        """创建测试任务记录"""
        with self._lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "status": "running",
                "progress": 0,
                "total": total,
                "workers": workers,
                "sequential": sequential,
                "start_time": datetime.now().isoformat(),
                "end_time": None,
                "accuracy": None,
                "subcategory_accuracy": None,
                "problem_accuracy": None,
                "correct_count": 0,
                "failed_count": 0,
                "log_file": None,
                "error": None,
                "log_lines": [],
                "recent_results": []
            }
    
    def update_progress(self, task_id: str, progress: int, msg: str = ""):
        """更新进度"""
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id]["progress"] = progress
                if msg:
                    self._tasks[task_id]["log_lines"].append(msg)
    
    def append_log(self, task_id: str, line: str):
        """追加日志"""
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id]["log_lines"].append(line)
    
    def complete_task(self, task_id: str, result: dict):
        """完成任务"""
        with self._lock:
            if task_id in self._tasks:
                t = self._tasks[task_id]
                t["status"] = "completed"
                t["end_time"] = datetime.now().isoformat()
                t.update(result)
                t["log_lines"] = t["log_lines"][-200:]  # 保留最近200行
    
    def fail_task(self, task_id: str, error: str):
        """标记任务失败"""
        with self._lock:
            if task_id in self._tasks:
                t = self._tasks[task_id]
                t["status"] = "failed"
                t["end_time"] = datetime.now().isoformat()
                t["error"] = error
    
    def get_task(self, task_id: str) -> Optional[dict]:
        """获取任务状态"""
        with self._lock:
            return self._tasks.get(task_id)
    
    def list_tasks(self) -> List[dict]:
        """列出所有任务"""
        with self._lock:
            return [
                {"task_id": t["task_id"], "status": t["status"],
                 "progress": t["progress"], "total": t["total"],
                 "start_time": t["start_time"], "end_time": t["end_time"]}
                for t in self._tasks.values()
            ]


_test_manager = TestTaskManager()


def _load_test_data():
    """加载测试数据和地址样本（与 test_problem_matching.py 一致）"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    detail_path = os.path.join(base_dir, "data", "test_data", "工单详情_detail.json")
    with open(detail_path, 'r', encoding='utf-8') as f:
        detail_data = json.load(f)
    
    test_cases = []
    for item in detail_data:
        overview = item.get("报修概述", "")
        proj = item.get("报修项目", "")
        typ = item.get("报修类型", "")
        if overview and proj and typ:
            test_cases.append({
                "repair_overview": overview,
                "repair_project": proj,
                "repair_type": typ,
                "repair_no": item.get("维修单号", "")
            })
    
    summary_path = os.path.join(base_dir, "data", "test_data", "报修单汇总_2026年1-6月_summary.json")
    addresses = []
    try:
        with open(summary_path, 'r', encoding='utf-8') as f:
            summary_data = json.load(f)
        for item in summary_data:
            addr = item.get("地址", "")
            if addr:
                addresses.append(addr)
    except FileNotFoundError:
        pass
    
    return test_cases, addresses


def _load_test_mappings():
    """加载分类映射（与 test_problem_matching.py 一致）"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    category_file = os.path.join(base_dir, "data", "rules", "category.json")
    subcategories_file = os.path.join(base_dir, "data", "rules", "subcategories.json")
    
    with open(category_file, 'r', encoding='utf-8') as f:
        rules = json.load(f)
    with open(subcategories_file, 'r', encoding='utf-8') as f:
        subcategories = json.load(f)
    
    valid_subcategories = {item["subCategory"] for item in subcategories}
    problem_to_subcategory = {}
    problem_to_keywords = {}
    keyword_to_problem = {}
    subcategory_to_problems = {}
    
    for rule in rules:
        sub = rule.get("subCategory", "")
        problem = rule.get("problem", "")
        keywords = rule.get("trigger_keywords", [])
        if sub and problem:
            problem_to_subcategory[problem] = sub
            problem_to_keywords[problem] = keywords
            if sub not in subcategory_to_problems:
                subcategory_to_problems[sub] = []
            subcategory_to_problems[sub].append(problem)
            for kw in keywords:
                keyword_to_problem[kw] = problem
    
    return (valid_subcategories, problem_to_subcategory, problem_to_keywords,
            keyword_to_problem, subcategory_to_problems)


def _run_test_background(task_id: str, test_count: int, workers: int, sequential: bool):
    """在后台线程中运行测试（与 test_problem_matching.py 逻辑一致）"""
    try:
        tm = _test_manager
        tm.append_log(task_id, f"🚀 测试开始: {test_count} 条, {workers} 并发")
        
        # 1. 加载数据
        tm.append_log(task_id, "🔄 加载测试数据...")
        test_cases, addresses = _load_test_data()
        (valid_subcategories, problem_to_subcategory, problem_to_keywords,
         keyword_to_problem, subcategory_to_problems) = _load_test_mappings()
        
        tm.append_log(task_id, f"   工单有效用例: {len(test_cases)}")
        tm.append_log(task_id, f"   地址样本: {len(addresses)}")
        
        total = min(test_count, len(test_cases))
        if sequential:
            selected = test_cases[:total]
        else:
            selected = random.sample(test_cases, total)
        
        rules_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "rules")
        start_time = time.time()
        
        tm.append_log(task_id, f"\n🔄 测试 {total} 个用例...")
        
        # 2. 并发执行测试
        results_by_idx = {}
        
        def process_one(case, idx):
            repair_overview = case["repair_overview"]
            expected_type = case["repair_type"]
            expected_project = case["repair_project"]
            
            # 跳过无效subCategory
            if expected_type not in valid_subcategories:
                return idx, {
                    "correct": True, "status": "SKIPPED",
                    "expected_type": expected_type
                }
            
            address = random.choice(addresses) if addresses else "上海市浦东新区某小区"
            full_input = f"{repair_overview}，地址是{address}"
            uid = f"api_test_{idx}_{int(time.time() * 1000000) % 10000000}"
            
            try:
                processor = InputProcessor(rules_dir=rules_dir)
                result = processor.process_user_input(uid, full_input)
                status = result.get("status", "ERROR")
                prechoice = result.get("prechoice_subcategories")
                trigger_keyword = result.get("trigger_keyword")
                
                if status in ("ERROR", "MISS", "NO_MATCH", "UNCLASSIFIABLE"):
                    return idx, {"correct": status == "UNCLASSIFIABLE",
                                 "status": status, "expected_type": expected_type}
                
                # 验证 prechoice
                pre_ok = bool(prechoice and isinstance(prechoice, list) and expected_type in prechoice)
                
                # 验证 trigger_keyword
                trig_ok = False
                if pre_ok and trigger_keyword:
                    if trigger_keyword == expected_project:
                        trig_ok = True
                    elif trigger_keyword in problem_to_keywords.get(expected_project, []):
                        trig_ok = True
                    elif trigger_keyword in keyword_to_problem:
                        mapped = keyword_to_problem[trigger_keyword]
                        mapped_sub = problem_to_subcategory.get(mapped)
                        if mapped == expected_project or mapped_sub == expected_type:
                            trig_ok = True
                
                correct = pre_ok and trig_ok
                error_type = None
                if not pre_ok:
                    error_type = "subCategory分类错误"
                elif not trig_ok:
                    error_type = "problem匹配错误"
                
                return idx, {
                    "correct": correct, "status": "SUCCESS",
                    "expected_type": expected_type,
                    "expected_project": expected_project,
                    "prechoice": prechoice,
                    "trigger_keyword": trigger_keyword,
                    "error_type": error_type
                }
            except Exception as e:
                return idx, {"correct": False, "status": "EXCEPTION", "error": str(e)}
            finally:
                try:
                    processor.cancel_session(uid)
                except:
                    pass
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(process_one, case, i+1): i+1
                       for i, case in enumerate(selected)}
            done = 0
            for future in as_completed(futures):
                idx, result = future.result()
                results_by_idx[idx] = result
                done += 1
                if done % max(1, total // 20) == 0:
                    pct = int(done / total * 100)
                    tm.update_progress(task_id, pct, f"  进度: {done}/{total} ({pct}%)")
        
        # 3. 统计
        total_elapsed = time.time() - start_time
        correct_count = sum(1 for r in results_by_idx.values() if r["correct"])
        skipped_count = sum(1 for r in results_by_idx.values() if r.get("status") == "SKIPPED")
        effective = total - skipped_count
        
        sub_errors = sum(1 for r in results_by_idx.values()
                         if r.get("error_type") == "subCategory分类错误")
        prob_errors = sum(1 for r in results_by_idx.values()
                          if r.get("error_type") == "problem匹配错误")
        sub_ok = sum(1 for r in results_by_idx.values()
                     if r.get("prechoice") and isinstance(r.get("prechoice"), list)
                     and r.get("expected_type") in r["prechoice"])
        prob_ok = sum(1 for r in results_by_idx.values()
                      if r.get("status") != "SKIPPED" and r["correct"])
        
        accuracy = round(correct_count / effective * 100, 1) if effective > 0 else 0
        sub_acc = round(sub_ok / effective * 100, 1) if effective > 0 else 0
        prob_passed = sum(1 for r in results_by_idx.values()
                          if r.get("prechoice") and isinstance(r.get("prechoice"), list)
                          and r.get("expected_type") in r["prechoice"])
        prob_acc = round(prob_ok / prob_passed * 100, 1) if prob_passed > 0 else 0
        
        # 4. 收集失败案例
        failures = []
        for i, r in sorted(results_by_idx.items()):
            if not r["correct"] and r["status"] != "SKIPPED":
                case = selected[i-1]
                failures.append({
                    "index": i,
                    "repair_overview": case["repair_overview"],
                    "expected_type": r["expected_type"],
                    "expected_project": r["expected_project"],
                    "prechoice": r.get("prechoice"),
                    "trigger_keyword": r.get("trigger_keyword"),
                    "error_type": r.get("error_type", "未知")
                })
        
        # 5. 保存日志文件
        from datetime import datetime as dt
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "logs")
        os.makedirs(log_dir, exist_ok=True)
        timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(log_dir, f"problem_matching_{timestamp}.txt")
        
        log_lines = [
            "=" * 90,
            "problem & trigger_keyword 匹配测试 - 失败案例日志",
            "=" * 90,
            f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"测试数量: {total} 条",
            "",
            f"📊 测试结果汇总",
            f"  综合正确率: {accuracy}% ({correct_count}/{effective})",
            f"  subCategory通过率: {sub_acc}%",
            f"  problem匹配率: {prob_acc}%",
            f"  总耗时: {total_elapsed:.1f}秒",
            "",
            "📋 失败案例:",
            "-" * 60,
        ]
        for f in failures:
            log_lines.append(f"[{f['index']}/{total}] {f['repair_overview'][:50]}")
            log_lines.append(f"  预期类型: {f['expected_type']}  预期项目: {f['expected_project']}")
            log_lines.append(f"  模型prechoice: {f.get('prechoice')}  模型trigger: {f.get('trigger_keyword')}")
            log_lines.append(f"  错误类型: {f['error_type']}")
            log_lines.append("")
        
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(log_lines))
        
        result = {
            "accuracy": accuracy,
            "subcategory_accuracy": sub_acc,
            "problem_accuracy": prob_acc,
            "correct_count": correct_count,
            "failed_count": len(failures),
            "effective_total": effective,
            "total_elapsed_seconds": round(total_elapsed, 1),
            "log_file": log_path,
            "failures": failures[:20],  # 前20条
            "total_failures": len(failures)
        }
        
        tm.append_log(task_id, f"\n✅ 测试完成! 正确率: {accuracy}% | 失败: {len(failures)}条")
        tm.complete_task(task_id, result)
        
    except Exception as e:
        _test_manager.fail_task(task_id, str(e))
        _test_manager.append_log(task_id, f"❌ 测试异常: {e}")

# ============================================================
# FastAPI 应用初始化
# ============================================================

app = FastAPI(
    title="智能工单系统 API",
    description="基于 DeepSeek 大模型的智能报修工单自动分类与生成系统接口",
    version="2.0.0"
)

# CORS 配置：允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 全局 Service 实例（单例，复用连接）
# ============================================================

_service: Optional[Service] = None


def get_service() -> Service:
    """获取或初始化全局 Service 实例"""
    global _service
    if _service is None:
        _service = Service()
    return _service


def get_db_instance():
    """获取数据库实例"""
    return get_db()


# ============================================================
# Pydantic 请求/响应模型
# ============================================================

class WorkOrderSubmitRequest(BaseModel):
    """单次提交（完整信息，无多轮对话）"""
    user_id: str = Field(..., description="用户唯一标识", min_length=1,
                         json_schema_extra={"example": "user001"})
    user_input: str = Field(..., description="完整的报修描述（问题描述 + 地址）", min_length=1,
                            json_schema_extra={"example": "卫生间顶上漏水严重，地址是示例区示例小区1号101室"})
    reporter_name: Optional[str] = Field(None, description="报修人姓名",
                                         json_schema_extra={"example": "张三"})
    reporter_phone: Optional[str] = Field(None, description="报修人联系电话",
                                          json_schema_extra={"example": "13800138000"})


class WorkOrderConverseRequest(BaseModel):
    """多轮对话提交"""
    user_id: str = Field(..., description="用户唯一标识", min_length=1,
                         json_schema_extra={"example": "user001"})
    text: str = Field(..., description="本轮输入的文本（可以是问题描述，也可以是地址补充）", min_length=1,
                      json_schema_extra={"example": "卫生间顶上漏水"})
    reporter_name: Optional[str] = Field(None, description="报修人姓名",
                                         json_schema_extra={"example": "张三"})
    reporter_phone: Optional[str] = Field(None, description="报修人联系电话",
                                          json_schema_extra={"example": "13800138000"})


class WorkOrderQueryParams(BaseModel):
    """工单查询参数（POST版）"""
    order_no: Optional[str] = None
    sub_category: Optional[str] = None
    property_company: Optional[str] = None
    status: Optional[str] = None
    keyword: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=200)


class FeedbackSubmitRequest(BaseModel):
    """提交反馈"""
    order_no: str = Field(..., json_schema_extra={"example": "WO20260709000001"})
    human_problem: str = Field(..., json_schema_extra={"example": "下水道堵塞疏通"})
    human_keyword: str = Field(..., json_schema_extra={"example": "总下水堵住"})


class FeedbackListQuery(BaseModel):
    """反馈列表查询参数"""
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=200)
    status: Optional[str] = Field(None, description="筛选状态：pending/approved/rejected")


class AddressMappingAddRequest(BaseModel):
    """新增地址映射"""
    community: str = Field(..., min_length=1, json_schema_extra={"example": "示例小区"})
    street: str = Field(default="", json_schema_extra={"example": "示例路"})
    property_company: str = Field(..., min_length=1, json_schema_extra={"example": "XX物业"})
    maintenance_unit: str = Field(default="", json_schema_extra={"example": "XX维修公司"})
    district: str = Field(default="浦东新区", description="区县")
    city: str = Field(default="上海市", description="城市")


class AddressMappingUpdateRequest(BaseModel):
    """更新地址映射"""
    street: Optional[str] = None
    property_company: Optional[str] = None
    maintenance_unit: Optional[str] = None


# ============================================================
# 通用响应包装
# ============================================================

def success_response(data: Any = None, message: str = "操作成功") -> dict:
    """标准成功响应"""
    return {"code": 0, "message": message, "data": data}


def error_response(message: str, code: int = -1) -> dict:
    """标准错误响应"""
    return {"code": code, "message": message, "data": None}


# ============================================================
# API - 健康检查
# ============================================================

@app.get("/api/v1/health", tags=["系统管理"])
async def health_check():
    """
    健康检查
    
    返回服务运行状态和版本信息。
    """
    return success_response({
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    })


# ============================================================
# API - 工单流程（单次提交 / 多轮对话）
# ============================================================

@app.post("/api/v1/work-order/submit", tags=["工单流程"])
async def submit_work_order(request: WorkOrderSubmitRequest):
    """
    提交报修工单（单次提交）
    
    适用于用户一次性提供了完整的报修描述（含地址）。
    执行完整的 5 步处理：
    1. AI 语义理解 & 分类（Step1 + Step2）
    2. 地址验证 & 解析
    3. 规则匹配
    4. 工人指派
    5. 工单生成 & 保存
    
    如果用户尚未提供完整信息（缺地址），请使用 converse 接口进行多轮对话。
    """
    service = get_service()
    
    # 清除该用户的任何已有会话，确保一个干净的上下文
    service.input_processor.cancel_session(request.user_id)
    
    result = service.handle_request(request.user_id, request.user_input,
                                    reporter_name=request.reporter_name,
                                    reporter_phone=request.reporter_phone)
    
    if result['status'] == 'SUCCESS':
        return success_response(
            data={
                "work_order": result['work_order'],
                "details": {
                    "input_processor": result['details'].get('input_processor'),
                    "rule_engine": result['details'].get('rule_engine'),
                }
            },
            message=result['message']
        )
    elif result['status'] == 'MISS':
        return success_response(
            data={
                "need_more_input": True,
                "content": result['details'].get('input_processor', {}).get('content'),
                "message_to_user": result['message']
            },
            message=result['message']
        )
    elif result['status'] == 'WRONG':
        return error_response(
            message="地址不在服务范围内（仅限浦东新区，地址可信度≥7）",
            code=1001
        )
    else:
        return error_response(
            message=result.get('message', '系统处理异常'),
            code=1002
        )


@app.post("/api/v1/work-order/converse", tags=["工单流程"])
async def converse_work_order(request: WorkOrderConverseRequest):
    """
    多轮对话式提交报修

    这是推荐前端使用的接口。支持多轮对话：
    - 第1次调用：用户只输入问题描述（无地址）
        → 系统返回 MISS，提示用户补充地址
        → 会话保持（会话状态为 awaiting_supplement）
    - 第2次调用：用户输入地址补充
        → 系统自动合并，继续处理
        → 返回 SUCCESS 或继续 MISS
    - 如果用户想重新开始，调用 DELETE /session/{user_id}
    
    处理逻辑：
    1. 检查该用户是否有活跃会话
       - 无会话 → 当作首次提交，创建新会话，走完整处理
       - 有会话且状态为 awaiting_supplement → 合并新旧输入，重新提交
       - 有会话且状态为 completed → 重置会话，当作新提交
    2. 返回处理结果
    """
    service = get_service()
    user_id = request.user_id
    text = request.text.strip()
    
    if not text:
        return error_response(message="输入内容不能为空", code=1006)
    
    # 检查当前会话状态
    session_status = service.input_processor.check_session_status(user_id)
    has_session = session_status.get('has_session', False)
    
    # ===== 持久化报修人信息到会话（多轮对话中保持） =====
    reporter_name = request.reporter_name
    reporter_phone = request.reporter_phone
    if not has_session and (reporter_name or reporter_phone):
        # 首次调用即提供了报修人信息，存入会话备用
        session = service.input_processor.session_manager.get_or_create_session(user_id)
        if reporter_name:
            session.set_reporter_name(reporter_name)
        if reporter_phone:
            session.set_reporter_phone(reporter_phone)
    elif has_session:
        # 已有会话，若本次未传报修人信息则从会话中读取
        session = service.input_processor.session_manager.get_session(user_id)
        if session:
            if not reporter_name:
                reporter_name = session.get_reporter_name()
            else:
                session.set_reporter_name(reporter_name)
            if not reporter_phone:
                reporter_phone = session.get_reporter_phone()
            else:
                session.set_reporter_phone(reporter_phone)

    if not has_session:
        # ===== 首次提交，创建新会话 =====
        result = service.handle_request(user_id, text,
                                        reporter_name=reporter_name,
                                        reporter_phone=reporter_phone)
        
        if result['status'] == 'SUCCESS':
            return success_response(
                data={
                    "work_order": result['work_order'],
                    "details": {
                        "input_processor": result['details'].get('input_processor'),
                        "rule_engine": result['details'].get('rule_engine'),
                    }
                },
                message=result['message']
            )
        elif result['status'] == 'MISS':
            return success_response(
                data={
                    "need_more_input": True,
                    "content": result['details'].get('input_processor', {}).get('content'),
                    "message_to_user": result['message'],
                    "session_alive": True  # 会话已保持，用户可以继续补充
                },
                message=result['message']
            )
        elif result['status'] == 'WRONG':
            return error_response(
                message="地址不在服务范围内（仅限浦东新区，地址可信度≥7）",
                code=1001
            )
        else:
            return error_response(
                message=result.get('message', '系统处理异常'),
                code=1002
            )
    else:
        # ===== 已有会话（awaiting_supplement 或 completed） =====
        step = session_status.get('step', 'initial')
        
        if step == 'awaiting_supplement':
            # 当前在等待补充地址阶段
            # 将新的输入与已保存的内容合并，重新提交
            existing_content = session_status.get('content', '') or ''
            
            # 策略：构建一个包含之前描述+新地址的完整文本
            # 如果新输入看起来像地址（含"路"、"号"、"新村"、"小区"、"地址"等）
            # 或者已有 content 但缺地址，就合并
            has_address_keywords = any(kw in text for kw in ['地址', '路', '号', '新村', '小区', '苑', '里', '寓', '城', '庄', '村', '弄', '室'])
            
            if has_address_keywords:
                full_input = f"{existing_content}，地址是{text}"
            else:
                # 用户补充的可能不是地址，而是更多问题描述，合并试试
                full_input = f"{existing_content}，{text}"
            
            # 清除旧会话，重新提交完整信息（保留 reporter 信息到新会话）
            service.input_processor.cancel_session(user_id)
            # 预先将 reporter 信息存入即将创建的新会话（handle_request 内部会 get_or_create_session）
            if reporter_name or reporter_phone:
                new_sess = service.input_processor.session_manager.get_or_create_session(user_id)
                if reporter_name:
                    new_sess.set_reporter_name(reporter_name)
                if reporter_phone:
                    new_sess.set_reporter_phone(reporter_phone)
            result = service.handle_request(user_id, full_input,
                                            reporter_name=reporter_name,
                                            reporter_phone=reporter_phone)
            
            if result['status'] == 'SUCCESS':
                return success_response(
                    data={
                        "work_order": result['work_order'],
                        "details": {
                            "input_processor": result['details'].get('input_processor'),
                            "rule_engine": result['details'].get('rule_engine'),
                        }
                    },
                    message=result['message']
                )
            elif result['status'] == 'MISS':
                # 仍然缺信息，保持新会话
                return success_response(
                    data={
                        "need_more_input": True,
                        "content": result['details'].get('input_processor', {}).get('content'),
                        "message_to_user": result['message'],
                        "session_alive": True
                    },
                    message=result['message']
                )
            elif result['status'] == 'WRONG':
                return error_response(
                    message="地址不在服务范围内（仅限浦东新区，地址可信度≥7）",
                    code=1001
                )
            else:
                return error_response(
                    message=result.get('message', '系统处理异常'),
                    code=1002
                )
        else:
            # 会话处于其他状态（completed 等），重置并重新开始
            service.input_processor.cancel_session(user_id)
            # 递归调用，走首次提交流程
            return await converse_work_order(
                WorkOrderConverseRequest(user_id=user_id, text=text)
            )


# ============================================================
# API - 工单查询
# ============================================================

@app.get("/api/v1/work-order/{order_no}", tags=["工单流程"])
async def get_work_order(order_no: str = Path(..., description="工单号")):
    """根据工单号查询工单详情"""
    try:
        db = get_db_instance()
        wo = db.get_by_order_no(order_no)
        if not wo:
            return error_response(message=f"工单 {order_no} 不存在", code=1004)

        # 反查工人信息（worker_id 一定存在对应工人，因为是从 workers 表分配出来的）
        worker_id = wo.get('worker_id')
        if worker_id is not None:
            row = db.get_worker_by_id(worker_id)
            if row:
                wo['worker_info'] = {
                    'id': row.get('id'),
                    'name': row.get('name'),
                    'phone': row.get('phone'),
                    'company': row.get('company'),
                    'department': row.get('department')
                }

        return success_response(data=wo)
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=1500)


@app.get("/api/v1/work-orders", tags=["工单流程"])
async def list_work_orders(
    order_no: Optional[str] = Query(None, description="工单号"),
    sub_category: Optional[str] = Query(None, description="报修类型"),
    property_company: Optional[str] = Query(None, description="物业公司"),
    status: Optional[str] = Query(None, description="工单状态"),
    keyword: Optional[str] = Query(None, description="关键词搜索（user_input/address）"),
    worker_id: Optional[int] = Query(None, description="指派工人ID"),
    start_time: Optional[str] = Query(None, description="开始时间，如 2026-07-01 00:00:00"),
    end_time: Optional[str] = Query(None, description="结束时间，如 2026-07-13 23:59:59"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=200, description="每页条数"),
):
    """
    多条件组合查询工单列表
    
    支持按工单号、报修类型、物业公司、状态、工人ID、关键词、时间范围筛选。
    """
    try:
        db = get_db_instance()
        offset = (page - 1) * limit
        
        results = db.search(
            order_no=order_no, sub_category=sub_category,
            property_company=property_company, status=status,
            keyword=keyword, worker_id=worker_id,
            start_time=start_time, end_time=end_time,
            limit=limit, offset=offset
        )
        total = db.search_count(
            order_no=order_no, sub_category=sub_category,
            property_company=property_company, status=status,
            keyword=keyword, worker_id=worker_id,
            start_time=start_time, end_time=end_time
        )
        
        return success_response(data={
            "items": results,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit if total > 0 else 0
        })
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=1500)


class WorkOrderSearchRequest(BaseModel):
    """高级工单搜索请求（支持worker_id）"""
    order_no: Optional[str] = None
    sub_category: Optional[str] = None
    property_company: Optional[str] = None
    status: Optional[str] = None
    keyword: Optional[str] = None
    worker_id: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=200)


@app.post("/api/v1/work-orders/search", tags=["工单流程"])
async def search_work_orders(params: WorkOrderSearchRequest):
    """
    高级工单搜索（POST方式）
    
    与 GET 方式功能相同，但支持更多参数通过 body 传递。
    """
    try:
        db = get_db_instance()
        offset = (params.page - 1) * params.limit
        
        results = db.search(
            order_no=params.order_no, sub_category=params.sub_category,
            property_company=params.property_company, status=params.status,
            keyword=params.keyword, worker_id=params.worker_id,
            start_time=params.start_time,
            end_time=params.end_time, limit=params.limit, offset=offset
        )
        total = db.search_count(
            order_no=params.order_no, sub_category=params.sub_category,
            property_company=params.property_company, status=params.status,
            keyword=params.keyword, worker_id=params.worker_id,
            start_time=params.start_time,
            end_time=params.end_time
        )
        
        return success_response(data={
            "items": results,
            "total": total,
            "page": params.page,
            "limit": params.limit,
            "total_pages": (params.limit + params.limit - 1) // params.limit if total > 0 else 0
        })
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=1500)


@app.post("/api/v1/work-order/{order_no}/start", tags=["工单流程"])
async def start_work_order(order_no: str = Path(..., description="工单号")):
    """
    开始处理工单（将状态从 PENDING 变更为 processing）
    
    只有待处理（PENDING）状态的工单可以开始处理。
    """
    try:
        result = _assigner_start(order_no)
        if result['status'] == 'SUCCESS':
            return success_response(message=result['message'])
        return error_response(message=result['message'], code=1005)
    except Exception as e:
        return error_response(message=f"操作失败: {str(e)}", code=1500)


@app.post("/api/v1/work-order/{order_no}/complete", tags=["工单流程"])
async def complete_work_order(order_no: str = Path(..., description="工单号")):
    """标记工单为已完成"""
    try:
        service = get_service()
        result = service.complete_order(order_no)
        if result['status'] == 'SUCCESS':
            return success_response(message=result['message'])
        return error_response(message=result['message'], code=1005)
    except Exception as e:
        return error_response(message=f"操作失败: {str(e)}", code=1500)


@app.post("/api/v1/work-order/{order_no}/worker-complete", tags=["工单流程"])
async def worker_complete_work_order(
    order_no: str = Path(..., description="工单号"),
    worker_id: int = Body(..., embed=True, description="工人ID")
):
    """
    工人完成处理（将状态从 processing 变更为 worker_completed）
    
    由工人前端调用，表示工人已完成为其分配的工作。
    只有状态为 processing（处理中）且分配给该工人的工单可以操作。
    之后管理员/调度员可在原前端点击"完成"将工单变为 completed。
    """
    try:
        result = _assigner_worker_complete(order_no, worker_id=worker_id)
        if result['status'] == 'SUCCESS':
            return success_response(message=result['message'])
        return error_response(message=result['message'], code=1005)
    except Exception as e:
        return error_response(message=f"操作失败: {str(e)}", code=1500)


class WorkerLoginRequest(BaseModel):
    """工人登录请求"""
    worker_name: str = Field(..., description="工人姓名", min_length=1,
                             json_schema_extra={"example": "张三"})
    password: str = Field(..., description="工人ID（作为密码）", min_length=1,
                          json_schema_extra={"example": "1"})


@app.post("/api/v1/worker/login", tags=["系统管理"])
async def worker_login(request: WorkerLoginRequest):
    """
    工人登录
    
    用户名 = 工人姓名（workers 表中 name 字段）
    密码 = 工人 ID（workers 表中 id 字段）
    
    登录成功后返回工人信息和该工人名下的所有工单。
    """
    try:
        db = get_db_instance()
        worker = None
        conn = db._get_connection()
        with conn.cursor() as c:
            c.execute("SELECT id, name, phone, company, department, certs FROM workers WHERE name = %s",
                      (request.worker_name,))
            worker = c.fetchone()
        
        if not worker:
            return error_response(message=f"工人 '{request.worker_name}' 不存在", code=1401)
        
        if str(worker['id']) != request.password.strip():
            return error_response(message="密码错误（应为工人ID）", code=1402)
        
        return success_response(
            data={
                "worker": {
                    "id": worker['id'],
                    "name": worker['name'],
                    "phone": worker.get('phone', ''),
                    "company": worker.get('company', ''),
                    "department": worker.get('department', ''),
                    "certs": worker.get('certs', '')
                }
            },
            message=f"登录成功，欢迎 {worker['name']}"
        )
    except Exception as e:
        return error_response(message=f"登录失败: {str(e)}", code=1500)


class WorkOrderUpdateRequest(BaseModel):
    """工单更新请求（仅 PENDING 状态可更新）"""
    user_input: Optional[str] = Field(None, description="报修概述")
    sub_category: Optional[str] = Field(None, description="报修类型")
    problem: Optional[str] = Field(None, description="报修项目")
    priority: Optional[str] = Field(None, description="优先级")
    property_company: Optional[str] = Field(None, description="物业公司")
    maintenance_unit: Optional[str] = Field(None, description="维修单位")
    address: Optional[str] = Field(None, description="报修地址")
    reporter_name: Optional[str] = Field(None, description="报修人姓名")
    reporter_phone: Optional[str] = Field(None, description="报修人联系电话")
    worker_id: Optional[int] = Field(None, description="指派工人ID")


@app.put("/api/v1/work-order/{order_no}", tags=["工单流程"])
async def update_work_order(order_no: str = Path(..., description="工单号"),
                            request: WorkOrderUpdateRequest = Body(...)):
    """
    更新工单信息（仅 PENDING 状态可更新）
    
    可在工单详情页修改报修概述、类型、项目、优先级、物业公司、维修单位、地址等信息。
    """
    try:
        db = get_db_instance()
        # 先检查工单是否存在及状态
        wo = db.get_by_order_no(order_no)
        if not wo:
            return error_response(message=f"工单 {order_no} 不存在", code=1004)
        if wo.get('status', '').upper() != 'PENDING':
            return error_response(message="仅待处理状态的工单可以更新", code=1007)
        
        # 构建更新数据（仅更新非 None 字段）
        update_data = {}
        for field in ['user_input', 'sub_category', 'problem', 'priority',
                       'property_company', 'maintenance_unit', 'address',
                       'reporter_name', 'reporter_phone', 'worker_id']:
            val = getattr(request, field, None)
            if val is not None:
                update_data[field] = val
        
        if not update_data:
            return error_response(message="没有需要更新的字段", code=1008)
        
        db.update_by_order_no(order_no, update_data)
        return success_response(message="工单更新成功")
    except Exception as e:
        return error_response(message=f"更新失败: {str(e)}", code=1500)


# ============================================================
# API - 多轮对话辅助（会话管理）
# ============================================================

@app.get("/api/v1/session/{user_id}", tags=["会话管理"])
async def get_session_status(user_id: str = Path(..., description="用户ID")):
    """
    查询用户的当前会话状态
    
    关键字段说明：
    - has_session: 是否有活跃会话
    - step: 当前阶段（initial/awaiting_supplement/completed）
    - session_state: 生命周期（ACTIVE/COMPLETED/PERSISTED）
    - content: 已提取的规范化报修描述
    - message: 当前状态的描述信息
    
    前端可根据 session_state 判断：
    - 无会话 → 用户可输入新的报修
    - awaiting_supplement → 需要用户补充地址
    - COMPLETED → 工单已生成，可跳转详情页
    """
    service = get_service()
    status_info = service.input_processor.check_session_status(user_id)
    return success_response(data=status_info)


@app.get("/api/v1/session/{user_id}/history", tags=["会话管理"])
async def get_session_history(user_id: str = Path(..., description="用户ID")):
    """
    获取用户的会话对话历史
    
    返回该用户在当前会话中的所有对话记录。
    如果用户想查看之前说过什么（如确认已经提供了哪些信息）。
    """
    service = get_service()
    session = service.input_processor.session_manager.get_session(user_id)
    if session is None:
        return success_response(
            data={"has_session": False, "history": []},
            message="没有活跃会话"
        )
    
    history = session.get_history()
    return success_response(data={
        "has_session": True,
        "step": session.get_step(),
        "session_state": session.get_session_state(),
        "content": session.get_content(),
        "address": session.get_address(),
        "prechoice_subcategories": session.get_prechoice_subcategories(),
        "trigger_keyword": session.get_trigger_keyword(),
        "history": history
    })


@app.delete("/api/v1/session/{user_id}", tags=["会话管理"])
async def cancel_session(user_id: str = Path(..., description="用户ID")):
    """
    取消/重置用户的当前会话
    
    应用场景：
    - 用户想重新开始报修（之前的描述说错了）
    - 多轮对话中途放弃当前报修
    - 前端页面切换时需要清理状态
    
    重置后，用户下一次调用 /converse 将作为全新报修处理。
    """
    service = get_service()
    service.input_processor.cancel_session(user_id)
    return success_response(message="会话已取消，可重新开始报修")


# ============================================================
# API - 数据查询
# ============================================================

@app.get("/api/v1/subcategories", tags=["数据查询"])
async def get_subcategories():
    """
    获取所有维修子类别及描述
    
    返回15种维修子类别的完整定义，包括：
    - id: 编号
    - subCategory: 子类别名称
    - description: 详细描述（含"属于"和"不属于"的边界说明）
    
    前端可用此接口展示分类选项给管理员参考。
    """
    try:
        db = get_db_instance()
        if db.rules_data_exists():
            data = db.get_all_subcategories()
        else:
            with open("data/rules/subcategories.json", "r", encoding="utf-8") as f:
                data = json.load(f)
        return success_response(data=data)
    except Exception as e:
        return error_response(message=f"获取失败: {str(e)}", code=1500)


@app.get("/api/v1/categories", tags=["数据查询"])
async def get_categories():
    """
    获取全部分类规则（含关键词和位置）
    
    返回完整的维修分类规则，每条包含：
    - rule_id, category, sub_category, problem
    - priority, required_cert, target_dept_semantic
    - trigger_keywords: 触发关键词列表
    - trigger_location: 触发位置列表
    """
    try:
        db = get_db_instance()
        if db.rules_data_exists():
            data = db.get_all_categories()
        else:
            with open("data/rules/category.json", "r", encoding="utf-8") as f:
                data = json.load(f)
        return success_response(data=data)
    except Exception as e:
        return error_response(message=f"获取失败: {str(e)}", code=1500)


@app.get("/api/v1/keywords", tags=["数据查询"])
async def get_keywords_by_subcategory(
    sub_category: Optional[str] = Query(None, description="按子类别筛选，如'管道窨井'")
):
    """
    按 subCategory 获取所有 trigger_keywords
    
    支持按子类别筛选，如果不传 sub_category 则返回所有。
    返回结构按 subCategory 分组：
    {
        "管道窨井": {"trigger_keywords": ["马桶堵塞", ...], "trigger_locations": [...]},
        "电气电路": {"trigger_keywords": ["插座没电", ...], "trigger_locations": [...]},
        ...
    }
    """
    try:
        db = get_db_instance()
        if sub_category:
            data = db.get_trigger_data_by_subcategories([sub_category])
        else:
            categories = db.get_all_categories() if db.rules_data_exists() else []
            if not categories:
                with open("data/rules/category.json", "r", encoding="utf-8") as f:
                    categories = json.load(f)
            data = {}
            for cat in categories:
                sub = cat.get('subCategory', cat.get('sub_category', ''))
                if sub not in data:
                    data[sub] = {"trigger_keywords": [], "trigger_locations": []}
                for kw in cat.get('trigger_keywords', []):
                    if kw not in data[sub]["trigger_keywords"]:
                        data[sub]["trigger_keywords"].append(kw)
                for loc in cat.get('trigger_location', cat.get('trigger_locations', [])):
                    if loc not in data[sub]["trigger_locations"]:
                        data[sub]["trigger_locations"].append(loc)
        return success_response(data=data)
    except Exception as e:
        return error_response(message=f"获取失败: {str(e)}", code=1500)


@app.get("/api/v1/rules/completeness", tags=["数据查询"])
async def check_rules_completeness():
    """
    检查规则数据完整性
    
    返回各规则表的数据量统计，帮助管理员确认规则是否已正确导入。
    
    如果 categories_count == 0，说明规则数据未导入，
    需要先调用 tools/migrate_json_to_db.py 导入规则。
    """
    try:
        db = get_db_instance()
        conn = db._get_connection()
        result = {}
        
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) AS cnt FROM categories")
            result['categories_count'] = c.fetchone()['cnt']
            
            c.execute("SELECT COUNT(*) AS cnt FROM category_trigger_keywords")
            result['keywords_count'] = c.fetchone()['cnt']
            
            c.execute("SELECT COUNT(*) AS cnt FROM category_trigger_locations")
            result['locations_count'] = c.fetchone()['cnt']
            
            c.execute("SELECT COUNT(*) AS cnt FROM subcategories")
            result['subcategories_count'] = c.fetchone()['cnt']
            
            c.execute("SELECT COUNT(*) AS cnt FROM address_mappings")
            result['address_mappings_count'] = c.fetchone()['cnt']
            
            c.execute("SELECT COUNT(*) AS cnt FROM work_orders")
            result['work_orders_count'] = c.fetchone()['cnt']
            
            c.execute("SELECT COUNT(*) AS cnt FROM workers")
            result['workers_count'] = c.fetchone()['cnt']
        
        return success_response(data=result)
    except Exception as e:
        return error_response(message=f"检查失败: {str(e)}", code=1500)


# ============================================================
# API - 反馈管理
# ============================================================

@app.post("/api/v1/feedback", tags=["反馈管理"])
async def submit_feedback(request: FeedbackSubmitRequest):
    """
    提交分类错误反馈
    
    当用户发现系统分类结果有误时，提交人工修正建议。
    管理员审核通过后（approve），关键词会自动同步到规则表。
    
    参数说明：
    - order_no: 需要修正的工单号
    - human_problem: 人工判定的正确维修项目（problem）
    - human_keyword: 应该新增/修正的关键词
    """
    try:
        fh = FeedbackHandler()
        result = fh.submit(request.order_no, request.human_problem, request.human_keyword)
        if result['status'] == 'SUCCESS':
            return success_response(
                data={
                    "id": result['id'],
                    "model_problem": result.get('model_problem'),
                    "human_problem": result.get('human_problem'),
                    "human_keyword": result.get('human_keyword')
                },
                message="反馈已提交，等待审核"
            )
        return error_response(message=result.get('message', '提交失败'), code=1101)
    except Exception as e:
        return error_response(message=f"提交失败: {str(e)}", code=1500)


@app.get("/api/v1/feedback/pending", tags=["反馈管理"])
async def get_pending_feedbacks():
    """获取所有待审核的反馈列表"""
    try:
        fh = FeedbackHandler()
        data = fh.get_pending()
        return success_response(data={
            "items": data,
            "total": len(data)
        })
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=1500)


@app.get("/api/v1/feedback/all", tags=["反馈管理"])
async def get_all_feedbacks(
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=200, description="每页条数"),
    status: Optional[str] = Query(None, description="筛选状态：pending/approved/rejected")
):
    """
    获取全部反馈列表（分页，支持按状态筛选）
    
    新增接口，弥补之前只有 pending 查询的不足。
    管理员可查看所有已审批或已驳回的反馈记录。
    """
    try:
        fh = FeedbackHandler()
        data = fh.get_all(limit=limit, offset=(page-1)*limit)
        
        # 按状态筛选
        if status:
            data = [item for item in data if item.get('status') == status]
        
        return success_response(data={
            "items": data,
            "page": page,
            "limit": limit
        })
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=1500)


@app.post("/api/v1/feedback/{feedback_id}/approve", tags=["反馈管理"])
async def approve_feedback(feedback_id: int = Path(..., description="反馈ID")):
    """
    审批通过反馈
    
    操作：
    1. 反馈状态从 pending → approved
    2. 自动将 human_keyword 插入 category_trigger_keywords 表
    3. 如果关键词已存在则跳过
    """
    try:
        fh = FeedbackHandler()
        result = fh.approve(feedback_id)
        if result['status'] == 'SUCCESS':
            return success_response(message=result['message'])
        return error_response(message=result['message'], code=1102)
    except Exception as e:
        return error_response(message=f"操作失败: {str(e)}", code=1500)


@app.post("/api/v1/feedback/{feedback_id}/reject", tags=["反馈管理"])
async def reject_feedback(feedback_id: int = Path(..., description="反馈ID")):
    """
    驳回反馈
    
    操作：
    1. 反馈状态从 pending → rejected
    2. 不修改规则表
    """
    try:
        fh = FeedbackHandler()
        result = fh.reject(feedback_id)
        if result['status'] == 'SUCCESS':
            return success_response(message=result['message'])
        return error_response(message=result['message'], code=1103)
    except Exception as e:
        return error_response(message=f"操作失败: {str(e)}", code=1500)


# ============================================================
# API - 地址映射管理
# ============================================================

@app.get("/api/v1/address-mappings", tags=["地址映射管理"])
async def list_address_mappings():
    """获取所有地址映射"""
    try:
        db = get_db_instance()
        data = db.get_all_address_mappings()
        return success_response(data=data)
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=1500)


@app.post("/api/v1/address-mappings", tags=["地址映射管理"])
async def add_address_mapping(request: AddressMappingAddRequest):
    """
    新增地址映射
    
    将小区名称与物业公司、维修单位绑定。
    如果小区已存在（community + street 组合重复），返回错误。
    """
    try:
        db = get_db_instance()
        conn = db._get_connection()
        with conn.cursor() as c:
            c.execute(
                "INSERT INTO address_mappings (community, street, property_company, maintenance_unit, district, city) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (request.community, request.street, request.property_company,
                 request.maintenance_unit, request.district, request.city)
            )
        return success_response(
            data={"id": c.lastrowid},
            message=f"地址映射已添加: {request.community}"
        )
    except Exception as e:
        if 'Duplicate' in str(e):
            return error_response(message=f"小区 '{request.community}' 已存在", code=1201)
        return error_response(message=f"添加失败: {str(e)}", code=1500)


@app.put("/api/v1/address-mappings/{mapping_id}", tags=["地址映射管理"])
async def update_address_mapping(
    mapping_id: int = Path(..., description="映射ID"),
    request: AddressMappingUpdateRequest = Body(...)
):
    """
    更新地址映射
    
    支持更新 street / property_company / maintenance_unit 字段。
    注意：community（小区名称）不可修改，如需修改请删除后重建。
    """
    try:
        fields = {}
        if request.street is not None:
            fields['street'] = request.street
        if request.property_company is not None:
            fields['property_company'] = request.property_company
        if request.maintenance_unit is not None:
            fields['maintenance_unit'] = request.maintenance_unit
        
        if not fields:
            return error_response(message="没有要更新的字段（支持: street, property_company, maintenance_unit）", code=1202)
        
        db = get_db_instance()
        conn = db._get_connection()
        with conn.cursor() as c:
            set_clause = ', '.join(f"{k}=%s" for k in fields)
            values = list(fields.values()) + [mapping_id]
            c.execute(f"UPDATE address_mappings SET {set_clause} WHERE id=%s", values)
            if c.rowcount == 0:
                return error_response(message=f"未找到ID={mapping_id}的记录", code=1203)
            return success_response(message=f"地址映射 ID={mapping_id} 已更新")
    except Exception as e:
        return error_response(message=f"更新失败: {str(e)}", code=1500)


@app.delete("/api/v1/address-mappings/{mapping_id}", tags=["地址映射管理"])
async def delete_address_mapping(mapping_id: int = Path(..., description="映射ID")):
    """删除地址映射"""
    try:
        db = get_db_instance()
        conn = db._get_connection()
        with conn.cursor() as c:
            c.execute("DELETE FROM address_mappings WHERE id=%s", (mapping_id,))
            if c.rowcount == 0:
                return error_response(message=f"未找到ID={mapping_id}的记录", code=1203)
            return success_response(message=f"地址映射 ID={mapping_id} 已删除")
    except Exception as e:
        return error_response(message=f"删除失败: {str(e)}", code=1500)


# ============================================================
# API - 数据库管理（规则数据 CRUD）
# ============================================================

class SubcategoryAddRequest(BaseModel):
    """新增子类别"""
    sub_category: str = Field(..., min_length=1)
    description: str = Field(default="")


class SubcategoryUpdateRequest(BaseModel):
    """更新子类别"""
    sub_category: Optional[str] = None
    description: Optional[str] = None


class CategoryAddRequest(BaseModel):
    """新增分类规则"""
    rule_id: int = Field(...)
    category: str = Field(...)
    sub_category: str = Field(...)
    problem: str = Field(...)
    priority: str = Field(default="")
    required_cert: str = Field(default="")
    target_dept_semantic: str = Field(default="")
    description: str = Field(default="")


class CategoryUpdateRequest(BaseModel):
    """更新分类规则"""
    rule_id: Optional[int] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    problem: Optional[str] = None
    priority: Optional[str] = None
    required_cert: Optional[str] = None
    target_dept_semantic: Optional[str] = None
    description: Optional[str] = None


class KeywordAddRequest(BaseModel):
    """新增关键词"""
    category_id: int = Field(...)
    keyword: str = Field(..., min_length=1)


class KeywordUpdateRequest(BaseModel):
    """更新关键词"""
    keyword: str = Field(..., min_length=1)


class LocationAddRequest(BaseModel):
    """新增位置"""
    category_id: int = Field(...)
    location: str = Field(..., min_length=1)


class LocationUpdateRequest(BaseModel):
    """更新位置"""
    location: str = Field(..., min_length=1)


# --- subcategories ---

@app.get("/api/v1/admin/subcategories", tags=["数据库管理"])
async def admin_list_subcategories():
    """获取所有子类别定义"""
    try:
        db = get_db_instance()
        data = db.get_all_subcategories()
        return success_response(data=data)
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=1500)


@app.post("/api/v1/admin/subcategories", tags=["数据库管理"])
async def admin_add_subcategory(request: SubcategoryAddRequest):
    """新增子类别"""
    try:
        db = get_db_instance()
        new_id = db.add_subcategory(request.sub_category, request.description)
        return success_response(data={"id": new_id}, message=f"子类别 '{request.sub_category}' 已添加")
    except Exception as e:
        return error_response(message=f"添加失败: {str(e)}", code=1500)


@app.put("/api/v1/admin/subcategories/{record_id}", tags=["数据库管理"])
async def admin_update_subcategory(record_id: int, request: SubcategoryUpdateRequest):
    """更新子类别"""
    try:
        db = get_db_instance()
        # 先获取现有数据，用新值覆盖
        existing = None
        conn = db._get_connection()
        with conn.cursor() as c:
            c.execute("SELECT * FROM subcategories WHERE id=%s", (record_id,))
            existing = c.fetchone()
        if not existing:
            return error_response(message=f"未找到ID={record_id}的记录", code=1203)
        sub = request.sub_category if request.sub_category is not None else existing['sub_category']
        desc = request.description if request.description is not None else existing['description']
        affected = db.update_subcategory(record_id, sub, desc)
        return success_response(message=f"子类别 ID={record_id} 已更新")
    except Exception as e:
        return error_response(message=f"更新失败: {str(e)}", code=1500)


@app.delete("/api/v1/admin/subcategories/{record_id}", tags=["数据库管理"])
async def admin_delete_subcategory(record_id: int):
    """删除子类别"""
    try:
        db = get_db_instance()
        affected = db.delete_subcategory(record_id)
        if affected == 0:
            return error_response(message=f"未找到ID={record_id}的记录", code=1203)
        return success_response(message=f"子类别 ID={record_id} 已删除")
    except Exception as e:
        return error_response(message=f"删除失败: {str(e)}", code=1500)


# --- categories ---

@app.get("/api/v1/admin/categories", tags=["数据库管理"])
async def admin_list_categories():
    """获取所有分类规则"""
    try:
        db = get_db_instance()
        data = db.get_all_categories()
        return success_response(data=data)
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=1500)


@app.post("/api/v1/admin/categories", tags=["数据库管理"])
async def admin_add_category(request: CategoryAddRequest):
    """新增分类规则"""
    try:
        db = get_db_instance()
        data = request.model_dump()
        new_id = db.add_category(data)
        return success_response(data={"id": new_id}, message=f"分类规则已添加 (rule_id={request.rule_id})")
    except Exception as e:
        return error_response(message=f"添加失败: {str(e)}", code=1500)


@app.put("/api/v1/admin/categories/{record_id}", tags=["数据库管理"])
async def admin_update_category(record_id: int, request: CategoryUpdateRequest):
    """更新分类规则"""
    try:
        db = get_db_instance()
        data = {k: v for k, v in request.model_dump().items() if v is not None}
        if not data:
            return error_response(message="没有要更新的字段", code=1202)
        affected = db.update_category(record_id, data)
        if affected == 0:
            return error_response(message=f"未找到ID={record_id}的记录", code=1203)
        return success_response(message=f"分类规则 ID={record_id} 已更新")
    except Exception as e:
        return error_response(message=f"更新失败: {str(e)}", code=1500)


@app.delete("/api/v1/admin/categories/{record_id}", tags=["数据库管理"])
async def admin_delete_category(record_id: int):
    """删除分类规则（级联删除关联的 keywords 和 locations）"""
    try:
        db = get_db_instance()
        affected = db.delete_category(record_id)
        if affected == 0:
            return error_response(message=f"未找到ID={record_id}的记录", code=1203)
        return success_response(message=f"分类规则 ID={record_id} 及其关联数据已删除")
    except Exception as e:
        return error_response(message=f"删除失败: {str(e)}", code=1500)


# --- keywords ---

@app.get("/api/v1/admin/keywords", tags=["数据库管理"])
async def admin_list_keywords():
    """获取所有触发关键词（含关联的 category 信息）"""
    try:
        db = get_db_instance()
        data = db.get_all_keywords_flat()
        return success_response(data=data)
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=1500)


@app.post("/api/v1/admin/keywords", tags=["数据库管理"])
async def admin_add_keyword(request: KeywordAddRequest):
    """新增触发关键词"""
    try:
        db = get_db_instance()
        new_id = db.add_keyword(request.category_id, request.keyword)
        return success_response(data={"id": new_id}, message=f"关键词 '{request.keyword}' 已添加")
    except Exception as e:
        return error_response(message=f"添加失败: {str(e)}", code=1500)


@app.put("/api/v1/admin/keywords/{record_id}", tags=["数据库管理"])
async def admin_update_keyword(record_id: int, request: KeywordUpdateRequest):
    """更新触发关键词"""
    try:
        db = get_db_instance()
        affected = db.update_keyword(record_id, request.keyword)
        if affected == 0:
            return error_response(message=f"未找到ID={record_id}的记录", code=1203)
        return success_response(message=f"关键词 ID={record_id} 已更新")
    except Exception as e:
        return error_response(message=f"更新失败: {str(e)}", code=1500)


@app.delete("/api/v1/admin/keywords/{record_id}", tags=["数据库管理"])
async def admin_delete_keyword(record_id: int):
    """删除触发关键词"""
    try:
        db = get_db_instance()
        affected = db.delete_keyword(record_id)
        if affected == 0:
            return error_response(message=f"未找到ID={record_id}的记录", code=1203)
        return success_response(message=f"关键词 ID={record_id} 已删除")
    except Exception as e:
        return error_response(message=f"删除失败: {str(e)}", code=1500)


# --- locations ---

@app.get("/api/v1/admin/locations", tags=["数据库管理"])
async def admin_list_locations():
    """获取所有触发位置（含关联的 category 信息）"""
    try:
        db = get_db_instance()
        data = db.get_all_locations_flat()
        return success_response(data=data)
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=1500)


@app.post("/api/v1/admin/locations", tags=["数据库管理"])
async def admin_add_location(request: LocationAddRequest):
    """新增触发位置"""
    try:
        db = get_db_instance()
        new_id = db.add_location(request.category_id, request.location)
        return success_response(data={"id": new_id}, message=f"位置 '{request.location}' 已添加")
    except Exception as e:
        return error_response(message=f"添加失败: {str(e)}", code=1500)


@app.put("/api/v1/admin/locations/{record_id}", tags=["数据库管理"])
async def admin_update_location(record_id: int, request: LocationUpdateRequest):
    """更新触发位置"""
    try:
        db = get_db_instance()
        affected = db.update_location(record_id, request.location)
        if affected == 0:
            return error_response(message=f"未找到ID={record_id}的记录", code=1203)
        return success_response(message=f"位置 ID={record_id} 已更新")
    except Exception as e:
        return error_response(message=f"更新失败: {str(e)}", code=1500)


@app.delete("/api/v1/admin/locations/{record_id}", tags=["数据库管理"])
async def admin_delete_location(record_id: int):
    """删除触发位置"""
    try:
        db = get_db_instance()
        affected = db.delete_location(record_id)
        if affected == 0:
            return error_response(message=f"未找到ID={record_id}的记录", code=1203)
        return success_response(message=f"位置 ID={record_id} 已删除")
    except Exception as e:
        return error_response(message=f"删除失败: {str(e)}", code=1500)


# ============================================================
# API - 人员管理
# ============================================================

class WorkerAddRequest(BaseModel):
    """新增工人"""
    name: str = Field(..., min_length=1)
    phone: str = Field(default="")
    company: str = Field(default="")
    department: str = Field(default="")
    certs: str = Field(default="")


class WorkerUpdateRequest(BaseModel):
    """更新工人"""
    name: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    department: Optional[str] = None
    certs: Optional[str] = None


@app.get("/api/v1/admin/workers", tags=["数据库管理"])
async def admin_list_workers():
    """获取所有工人"""
    try:
        db = get_db_instance()
        data = db.get_all_workers()
        return success_response(data=data)
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=1500)


@app.post("/api/v1/admin/workers", tags=["数据库管理"])
async def admin_add_worker(request: WorkerAddRequest):
    """新增工人"""
    try:
        db = get_db_instance()
        new_id = db.add_worker(request.model_dump())
        return success_response(data={"id": new_id}, message=f"工人 '{request.name}' 已添加")
    except Exception as e:
        return error_response(message=f"添加失败: {str(e)}", code=1500)


@app.put("/api/v1/admin/workers/{record_id}", tags=["数据库管理"])
async def admin_update_worker(record_id: int, request: WorkerUpdateRequest):
    """更新工人"""
    try:
        db = get_db_instance()
        data = {k: v for k, v in request.model_dump().items() if v is not None}
        if not data:
            return error_response(message="没有要更新的字段", code=1202)
        affected = db.update_worker(record_id, data)
        if affected == 0:
            return error_response(message=f"未找到ID={record_id}的记录", code=1203)
        return success_response(message=f"工人 ID={record_id} 已更新")
    except Exception as e:
        return error_response(message=f"更新失败: {str(e)}", code=1500)


@app.delete("/api/v1/admin/workers/{record_id}", tags=["数据库管理"])
async def admin_delete_worker(record_id: int):
    """删除工人"""
    try:
        db = get_db_instance()
        affected = db.delete_worker(record_id)
        if affected == 0:
            return error_response(message=f"未找到ID={record_id}的记录", code=1203)
        return success_response(message=f"工人 ID={record_id} 已删除")
    except Exception as e:
        return error_response(message=f"删除失败: {str(e)}", code=1500)


# ============================================================
# API - 提示词管理 (Prompts)
# ============================================================

class PromptUpdateRequest(BaseModel):
    """更新提示词配置"""
    path: str = Field(..., description="JSON路径，如 step1.system_role / step2.classification_rules")
    value: Any = Field(..., description="新值（字符串或数组）")
    action: Optional[str] = Field(None, description="操作类型: add/remove/update。数组类型字段需要")


class PromptRuleRequest(BaseModel):
    """单条规则操作"""
    rule_text: str = Field(..., min_length=1, description="规则文本")
    index: Optional[int] = Field(None, description="规则索引（update/remove时需要）")


@app.get("/api/v1/admin/prompts", tags=["提示词管理"])
async def get_prompts():
    """
    获取完整的提示词配置
    
    返回 prompts.json 的全部内容，用于前端编辑。
    """
    try:
        from input_processor.prompt_manager import PromptManager
        pm = PromptManager()
        return success_response(data=pm.get_raw_data())
    except Exception as e:
        return error_response(message=f"获取失败: {str(e)}", code=1500)


@app.post("/api/v1/admin/prompts/reload", tags=["提示词管理"])
async def reload_prompts():
    """
    热重载提示词配置
    
    修改 prompts.json 后调用此接口使更改立即生效，无需重启服务。
    """
    try:
        from input_processor.prompt_manager import PromptManager, get_prompt_manager
        pm = get_prompt_manager()
        pm.reload()
        return success_response(message="提示词配置已重新加载", data={"version": pm.get_version()})
    except Exception as e:
        return error_response(message=f"重载失败: {str(e)}", code=1500)


@app.put("/api/v1/admin/prompts/field", tags=["提示词管理"])
async def update_prompt_field(request: PromptUpdateRequest):
    """
    更新提示词配置中的单个字段
    
    支持更新字符串字段和数组字段。
    path 示例：
    - "step1.system_role" — 更新字符串
    - "step1.thinking_steps" — 替换整个数组
    - "step1.notes" — 替换整个数组
    - "step2.classification_rules" — 替换整个数组
    - "step2.requirements" — 替换整个数组
    """
    try:
        from input_processor.prompt_manager import PromptManager
        pm = PromptManager()
        parts = request.path.split('.')
        if len(parts) < 2:
            return error_response(message=f"无效路径: {request.path}", code=1202)
        
        section = parts[0]
        field = '.'.join(parts[1:])
        
        if section == 'step1':
            if field == 'system_role':
                pm.update_step1_system_role(str(request.value))
            elif field == 'thinking_steps':
                pm.update_step1_thinking_steps(list(request.value))
            elif field == 'notes':
                pm.update_step1_notes(list(request.value))
            else:
                return error_response(message=f"不支持的字段: {request.path}", code=1202)
        elif section == 'step2':
            if field == 'system_role':
                pm.update_step2_system_role(str(request.value))
            elif field == 'classification_rules':
                pm.update_step2_classification_rules(list(request.value))
            elif field == 'requirements':
                pm.update_step2_requirements(list(request.value))
            elif field == 'location_requirements':
                pm.update_step2_location_requirements(list(request.value))
            elif field == 'location_selection_prompt':
                pm.update_step2_location_prompt(str(request.value))
            else:
                return error_response(message=f"不支持的字段: {request.path}", code=1202)
        else:
            return error_response(message=f"不支持的section: {section}", code=1202)
        
        return success_response(message=f"字段 '{request.path}' 已更新")
    except Exception as e:
        return error_response(message=f"更新失败: {str(e)}", code=1500)


@app.post("/api/v1/admin/prompts/step2/rule", tags=["提示词管理"])
async def add_step2_rule(request: PromptRuleRequest):
    """在 Step2 分类规则末尾追加一条规则"""
    try:
        from input_processor.prompt_manager import PromptManager
        pm = PromptManager()
        pm.add_step2_rule(request.rule_text)
        return success_response(message="规则已添加")
    except Exception as e:
        return error_response(message=f"添加失败: {str(e)}", code=1500)


@app.put("/api/v1/admin/prompts/step2/rule/{index}", tags=["提示词管理"])
async def update_step2_rule(index: int, request: PromptRuleRequest):
    """修改 Step2 的某一条分类规则"""
    try:
        from input_processor.prompt_manager import PromptManager
        pm = PromptManager()
        pm.update_step2_rule(index, request.rule_text)
        return success_response(message=f"规则 #{index} 已更新")
    except Exception as e:
        return error_response(message=f"更新失败: {str(e)}", code=1500)


@app.delete("/api/v1/admin/prompts/step2/rule/{index}", tags=["提示词管理"])
async def delete_step2_rule(index: int):
    """删除 Step2 的某一条分类规则"""
    try:
        from input_processor.prompt_manager import PromptManager
        pm = PromptManager()
        pm.remove_step2_rule(index)
        return success_response(message=f"规则 #{index} 已删除")
    except Exception as e:
        return error_response(message=f"删除失败: {str(e)}", code=1500)


@app.put("/api/v1/admin/prompts/step1/task/{task_key}", tags=["提示词管理"])
async def update_step1_task(task_key: str, value: str = Body(..., embed=True)):
    """更新 Step1 某个任务的描述"""
    try:
        from input_processor.prompt_manager import PromptManager
        pm = PromptManager()
        pm.update_step1_task(task_key, value)
        return success_response(message=f"任务 '{task_key}' 已更新")
    except Exception as e:
        return error_response(message=f"更新失败: {str(e)}", code=1500)


# ============================================================
# API - 系统管理
# ============================================================

@app.get("/api/v1/workers", tags=["系统管理"])
async def list_workers(
    company: Optional[str] = Query(None, description="按物业公司筛选")
):
    """获取工人列表"""
    try:
        db = get_db_instance()
        conn = db._get_connection()
        with conn.cursor() as c:
            if company:
                c.execute("SELECT id, name, company, department, certs FROM workers WHERE company = %s", (company,))
            else:
                c.execute("SELECT id, name, company, department, certs FROM workers")
            data = c.fetchall()
        return success_response(data=data)
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=1500)


@app.get("/api/v1/stats", tags=["系统管理"])
async def get_statistics():
    """
    获取系统统计数据
    
    返回数据：
    - total_orders: 工单总数
    - status_distribution: 各状态工单分布
    - subcategory_distribution: 各子类别工单分布（按数量降序）
    - company_distribution: 各物业公司工单分布
    - total_workers: 工人总数
    - pending_feedbacks: 待审核反馈数
    """
    try:
        db = get_db_instance()
        conn = db._get_connection()
        
        stats = {}
        
        # 工单总数
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) AS total FROM work_orders")
            stats['total_orders'] = c.fetchone()['total']
        
        # 各状态工单数
        with conn.cursor() as c:
            c.execute("SELECT status, COUNT(*) AS cnt FROM work_orders GROUP BY status")
            stats['status_distribution'] = {row['status']: row['cnt'] for row in c.fetchall()}
        
        # 各子类别工单数（降序）
        with conn.cursor() as c:
            c.execute("SELECT sub_category, COUNT(*) AS cnt FROM work_orders GROUP BY sub_category ORDER BY cnt DESC")
            stats['subcategory_distribution'] = [
                {"sub_category": row['sub_category'], "count": row['cnt']}
                for row in c.fetchall()
            ]
        
        # 各物业公司工单数（降序）
        with conn.cursor() as c:
            c.execute("SELECT property_company, COUNT(*) AS cnt FROM work_orders GROUP BY property_company ORDER BY cnt DESC")
            stats['company_distribution'] = [
                {"company": row['property_company'], "count": row['cnt']}
                for row in c.fetchall()
            ]
        
        # 工人总数
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) AS total FROM workers")
            stats['total_workers'] = c.fetchone()['total']
        
        # 待审核反馈数
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) AS cnt FROM error_feedbacks WHERE status='pending'")
            stats['pending_feedbacks'] = c.fetchone()['cnt']
        
        return success_response(data=stats)
    except Exception as e:
        return error_response(message=f"获取统计失败: {str(e)}", code=1500)


# ============================================================
# API - 模型准确度测试
# ============================================================

class TestRunRequest(BaseModel):
    """启动测试请求"""
    test_count: int = Field(default=200, ge=10, le=2000, description="测试条数")
    workers: int = Field(default=3, ge=1, le=10, description="并发数")
    sequential: bool = Field(default=False, description="是否顺序抽取（否则随机）")


@app.post("/api/v1/test/run", tags=["模型测试"])
async def start_test(request: TestRunRequest):
    """
    启动模型准确度测试（后台异步运行）

    测试流程：
    1. 从测试数据中随机/顺序抽取指定数量的用例
    2. 并发调用 AI 完成 subCategory + trigger_keyword 匹配
    3. 对比预期结果，统计分类准确率
    4. 保存失败案例日志到 data/logs/

    测试耗时：200条约2分钟，1000条约10分钟。

    返回 task_id，前端通过轮询 GET /test/{task_id}/status 获取进度和结果。
    """
    import uuid
    task_id = f"test_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"

    _test_manager.create_task(task_id, request.test_count, request.workers, request.sequential)

    # 后台线程启动测试
    thread = threading.Thread(
        target=_run_test_background,
        args=(task_id, request.test_count, request.workers, request.sequential),
        daemon=True
    )
    thread.start()

    return success_response(
        data={"task_id": task_id, "status": "running"},
        message=f"测试已启动: {request.test_count} 条, {request.workers} 并发"
    )


@app.get("/api/v1/test/{task_id}/status", tags=["模型测试"])
async def get_test_status(task_id: str = Path(..., description="任务ID")):
    """
    查询测试任务状态（轮询用）

    状态说明：
    - running: 测试进行中，progress 字段为完成百分比
    - completed: 测试完成，返回 accuracy、failures 等结果
    - failed: 测试失败，返回 error
    - not_found: 任务ID不存在

    前端应每隔3-5秒轮询一次，直到 status 变为 completed 或 failed。
    """
    task = _test_manager.get_task(task_id)
    if not task:
        return error_response(message=f"任务 {task_id} 不存在", code=1301)

    if task["status"] == "completed":
        return success_response(data={
            "task_id": task_id,
            "status": "completed",
            "accuracy": task["accuracy"],
            "subcategory_accuracy": task["subcategory_accuracy"],
            "problem_accuracy": task["problem_accuracy"],
            "correct_count": task["correct_count"],
            "failed_count": task["failed_count"],
            "effective_total": task["effective_total"],
            "total_elapsed_seconds": task["total_elapsed_seconds"],
            "log_file": task["log_file"],
            "failures": task.get("failures", [])[:10],
            "total_failures": task["total_failures"],
            "start_time": task["start_time"],
            "end_time": task["end_time"]
        })
    elif task["status"] == "failed":
        return error_response(message=f"测试失败: {task.get('error', '未知错误')}", code=1302)
    else:
        return success_response(data={
            "task_id": task_id,
            "status": "running",
            "progress": task["progress"],
            "total": task["total"],
            "log_lines": task["log_lines"][-20:] if task.get("log_lines") else [],
            "start_time": task["start_time"]
        })


@app.get("/api/v1/test/tasks", tags=["模型测试"])
async def list_test_tasks():
    """列出所有测试任务（最近5个）"""
    tasks = _test_manager.list_tasks()
    return success_response(data={"tasks": tasks[-5:]})


@app.get("/api/v1/test/logs", tags=["模型测试"])
async def list_test_logs():
    """
    列出历史测试日志文件

    返回 data/logs/ 目录下的所有测试日志，
    按文件名排序，最新的在前。
    """
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(base_dir, "data", "logs")
        if not os.path.exists(log_dir):
            return success_response(data={"logs": []})

        files = []
        for f in sorted(os.listdir(log_dir), reverse=True):
            if f.startswith("problem_matching_") and f.endswith(".txt"):
                path = os.path.join(log_dir, f)
                size = os.path.getsize(path)
                mtime = datetime.fromtimestamp(os.path.getmtime(path)).isoformat()
                files.append({
                    "filename": f,
                    "size_bytes": size,
                    "modified_time": mtime
                })
        return success_response(data={"logs": files})
    except Exception as e:
        return error_response(message=str(e), code=1500)


@app.get("/api/v1/test/logs/{filename}", tags=["模型测试"])
async def download_test_log(filename: str = Path(..., description="日志文件名")):
    """
    下载/查看指定测试日志文件内容

    返回日志文件的全部文本内容。
    示例：filename = problem_matching_20260709_122359.txt
    """
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(base_dir, "data", "logs")
        path = os.path.join(log_dir, filename)

        # 安全检查：防止路径遍历
        if not os.path.realpath(path).startswith(os.path.realpath(log_dir)):
            return error_response(message="非法文件名", code=1303)

        if not os.path.exists(path):
            return error_response(message=f"日志文件 {filename} 不存在", code=1304)

        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        return success_response(data={
            "filename": filename,
            "content": content,
            "line_count": content.count('\n') + 1
        })
    except Exception as e:
        return error_response(message=str(e), code=1500)


# ============================================================
# 启动入口
# ============================================================

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("  智能工单系统 API Server")
    print("=" * 60)
    print("  API 文档: http://localhost:8000/docs")
    print("  API 地址: http://localhost:8000/api/v1")
    print("=" * 60)
    print("  接口数量: 46 个")
    print("  分组:")
    print("    - 工单流程     6 个")
    print("    - 会话管理     3 个")
    print("    - 数据查询     4 个")
    print("    - 反馈管理     5 个")
    print("    - 地址映射     4 个")
    print("    - 系统管理     3 个")
    print("    - 模型测试     5 个")
    print("    - 数据库管理  16 个")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
