"""
智能工单系统 - problem 与 trigger_keyword 匹配测试（并发版 + 失败重跑）

【测试目标】
验证大模型在完整流程（Step1 subCategory选取 + Step2 trigger_keyword匹配）中：
1. Step1（subCategory粗筛）：prechoice_subcategories 是否包含预期的报修类型
2. Step2（trigger_keyword匹配）：trigger_keyword 是否能正确映射到预期报修项目(problem)
   - 验证标准：trigger_keyword 必须能映射到与预期problem同subCategory下的某个problem
   - 只需正确筛选出相应problem下的trigger_keyword就算正确

【错误分类】
- "subCategory分类错误"：prechoice不包含预期报修类型（第一步就错了）
- "problem匹配错误"：prechoice正确，但trigger_keyword匹配失败（第二步错了）

【输出】
- data/logs/problem_matching_{timestamp}.txt: 仅包含失败案例的行 + 总结

【参考】
- test_subcategory_coverage.py: 并发框架、用户交互、失败重跑机制
"""

import json
import os
import sys
import random
import time
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from input_processor.processor import InputProcessor


# ==================== 数据加载 ====================

def load_data(project=None):
    """
    加载测试数据和地址样本。

    Args:
        project: 报修类型名称（如 "水"、"电"），从 split_by_type 目录加载对应文件。
                 为 None 时加载全量数据。

    Returns:
        (test_cases, addresses, project_name)
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if project:
        # 从 split_by_type 目录加载指定项目
        split_file = os.path.join(base_dir, "data", "test_data", "split_by_type", f"报修_{project}.json")
        if not os.path.exists(split_file):
            print(f"❌ 错误: 项目文件不存在: {split_file}")
            available = list_available_projects(base_dir)
            print(f"   可用项目: {', '.join(available)}")
            sys.exit(1)
        with open(split_file, 'r', encoding='utf-8') as f:
            split_data = json.load(f)
        detail_data = []
        for proj_name, records in split_data.get("报修项目", {}).items():
            detail_data.extend(records)
    else:
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

    project_name = project if project else "全项目"
    return test_cases, addresses, project_name


def list_available_projects(base_dir):
    """列出 split_by_type 目录下所有可用项目名"""
    split_dir = os.path.join(base_dir, "data", "test_data", "split_by_type")
    if not os.path.exists(split_dir):
        return []
    projects = []
    for f in os.listdir(split_dir):
        if f.startswith("报修_") and f.endswith(".json"):
            name = f[3:-5]  # 去掉 "报修_" 前缀和 ".json" 后缀
            projects.append(name)
    return sorted(projects)


def get_project_summary(base_dir, project):
    """获取某个项目文件的 summary 信息"""
    split_file = os.path.join(base_dir, "data", "test_data", "split_by_type", f"报修_{project}.json")
    if os.path.exists(split_file):
        with open(split_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("summary", {})
    return {}


def load_valid_subcategories():
    """加载有效的 subCategory 集合"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sub_file = os.path.join(base_dir, "data", "rules", "subcategories.json")
    with open(sub_file, 'r', encoding='utf-8') as f:
        sub_data = json.load(f)
    return {item["subCategory"] for item in sub_data}


def load_mappings():
    """
    加载分类映射关系。

    Returns:
        valid_subcategories: set of valid subCategory names
        problem_to_subcategory: dict, problem -> subCategory
        problem_to_keywords: dict, problem -> list of trigger_keywords
        keyword_to_problem: dict, trigger_keyword -> problem
        subcategory_to_problems: dict, subCategory -> list of problems
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

    return valid_subcategories, problem_to_subcategory, problem_to_keywords, keyword_to_problem, subcategory_to_problems


# ==================== 验证逻辑 ====================

def get_expected_subcategory(expected_problem, problem_to_subcategory, subcategory_to_problems):
    """
    获取预期报修项目(problem)所属的 subCategory。

    优先从 problem_to_subcategory 直接查找，如果找不到则遍历 subcategory_to_problems。

    Returns:
        str or None: 预期的 subCategory
    """
    if expected_problem in problem_to_subcategory:
        return problem_to_subcategory[expected_problem]
    # 遍历查找
    for sub, problems in subcategory_to_problems.items():
        if expected_problem in problems:
            return sub
    return None


def check_prechoice(prechoice, expected_subcategory):
    """
    检查 prechoice_subcategories 是否包含预期的 subCategory。

    Returns:
        (bool, str): (是否包含, 说明)
    """
    if not prechoice or not isinstance(prechoice, list):
        return False, f"prechoice 为空或不是列表"
    if expected_subcategory in prechoice:
        return True, f"prechoice {prechoice} 包含预期的 {expected_subcategory}"
    return False, f"prechoice {prechoice} 不包含预期的 {expected_subcategory}"


def check_trigger_keyword(trigger_keyword, expected_subcategory, keyword_to_problem,
                           problem_to_keywords, expected_problem):
    """
    检查 trigger_keyword 是否与预期报修项目(problem)语义匹配。

    验证逻辑：
    1. trigger_keyword 非空是基本要求
    2. trigger_keyword 必须能在 keyword_to_problem 中找到对应的 problem
    3. 映射到的 problem 所属 subCategory 必须与预期 problem 的 subCategory 一致
    4. 或者 trigger_keyword 是预期 problem 的 trigger_keywords 之一

    Returns:
        (bool, str): (是否匹配, 说明)
    """
    if not trigger_keyword:
        return False, "trigger_keyword 为空"

    # 1. 精确匹配：trigger_keyword 就是预期 problem
    if trigger_keyword == expected_problem:
        return True, f"trigger_keyword '{trigger_keyword}' 与预期problem完全一致"

    # 2. trigger_keyword 是预期 problem 的 trigger_keywords 之一
    expected_kws = problem_to_keywords.get(expected_problem, [])
    if trigger_keyword in expected_kws:
        return True, f"trigger_keyword '{trigger_keyword}' 是预期problem的触发关键词"

    # 3. 反向映射：trigger_keyword 映射到的 problem 是否与预期 subCategory 一致
    if trigger_keyword in keyword_to_problem:
        mapped_problem = keyword_to_problem[trigger_keyword]
        # 需要知道 mapped_problem 所属的 subCategory
        # 通过遍历 subcategory_to_problems 查找
        # 但这里我们直接使用 expected_subcategory 来做比较
        # 实际上 keyword_to_problem 中没有 subCategory 信息，需要额外查找
        # 简化处理：如果 mapped_problem == expected_problem，那就是正确
        if mapped_problem == expected_problem:
            return True, f"trigger_keyword '{trigger_keyword}' 映射到预期problem"
        # 否则需要进一步判断：mapped_problem 和 expected_problem 是否在同一 subCategory 下
        # 这里返回需要外部进一步判断的状态
        return False, f"trigger_keyword '{trigger_keyword}' 映射到 '{mapped_problem}'，非预期problem '{expected_problem}'"
    else:
        return False, f"trigger_keyword '{trigger_keyword}' 不在规则文件的 trigger_keywords 中"


def check_trigger_keyword_full(trigger_keyword, expected_problem, expected_subcategory,
                                keyword_to_problem, problem_to_keywords,
                                problem_to_subcategory, subcategory_to_problems):
    """
    完整检查 trigger_keyword 是否匹配预期 problem。

    判断逻辑：
    1. trigger_keyword 为空 → 失败
    2. trigger_keyword 精确匹配预期 problem → 成功
    3. trigger_keyword 是预期 problem 的 keywords → 成功
    4. trigger_keyword 映射到的 problem 与预期 problem 在同一 subCategory 下 → 成功
    5. 其他情况 → 失败

    Returns:
        (bool, str, str or None): (是否匹配, 说明, 匹配到的problem)
    """
    if not trigger_keyword:
        return False, "trigger_keyword 为空", None

    # 精确匹配
    if trigger_keyword == expected_problem:
        return True, f"trigger_keyword 与预期problem完全一致", expected_problem

    # 是预期 problem 的关键词
    expected_kws = problem_to_keywords.get(expected_problem, [])
    if trigger_keyword in expected_kws:
        return True, f"trigger_keyword 是预期problem的触发关键词", expected_problem

    # 反向映射查找
    if trigger_keyword in keyword_to_problem:
        mapped_problem = keyword_to_problem[trigger_keyword]
        mapped_subcategory = problem_to_subcategory.get(mapped_problem)
        # 遍历查找 mapped_subcategory
        if mapped_subcategory is None:
            for sub, probs in subcategory_to_problems.items():
                if mapped_problem in probs:
                    mapped_subcategory = sub
                    break

        if mapped_problem == expected_problem:
            return True, f"trigger_keyword 精确映射到预期problem", expected_problem

        if mapped_subcategory == expected_subcategory:
            return True, f"trigger_keyword 映射到同subCategory下的 '{mapped_problem}'", mapped_problem
        else:
            return False, (f"trigger_keyword 映射到 '{mapped_problem}' "
                           f"(subCategory='{mapped_subcategory}')，"
                           f"与预期subCategory='{expected_subcategory}'不匹配"), mapped_problem
    else:
        return False, f"trigger_keyword 不在规则文件中，无法验证", None


# ==================== 单条测试处理 ====================

def process_one_case(case, idx, total, addresses, valid_subcategories,
                     problem_to_subcategory, problem_to_keywords,
                     keyword_to_problem, subcategory_to_problems, processor):
    """
    处理单个测试用例（共享 processor 实例，避免重复创建 DB 连接）。

    流程：
    1. 执行完整流程（Step1 + Step2）
    2. 检查 prechoice 是否包含预期 subCategory
    3. 检查 trigger_keyword 是否正确匹配
    4. 分类错误类型

    Returns:
        (result_dict, console_line, is_failure, is_error)
    """
    repair_overview = case["repair_overview"]
    expected_type = case["repair_type"]
    expected_project = case["repair_project"]
    repair_no = case["repair_no"]

    # 获取预期 project 所属的 subCategory
    expected_subcategory = get_expected_subcategory(
        expected_project, problem_to_subcategory, subcategory_to_problems
    )

    # 跳过无效 subCategory
    if expected_type not in valid_subcategories:
        msg = f"[{idx}/{total}] 测试: {repair_overview[:60]}... 预期subCategory: {expected_type} ⏭️ SKIPPED"
        return {
            "index": idx, "repair_no": repair_no,
            "input": repair_overview, "expected_type": expected_type,
            "expected_project": expected_project,
            "expected_subcategory": expected_subcategory,
            "status": "SKIPPED", "prechoice": None,
            "trigger_keyword": None, "error_type": None,
            "correct": False, "elapsed_time": 0,
        }, msg, False, False

    address = random.choice(addresses) if addresses else "上海市浦东新区某小区"
    full_input = f"{repair_overview}，地址是{address}"
    user_id = f"problem_test_{idx}_{int(time.time() * 1000000) % 10000000}"

    try:
        t_start = time.time()

        # 执行完整流程
        result = processor.process_user_input(user_id, full_input)
        elapsed = time.time() - t_start

        status = result.get("status", "ERROR")
        prechoice = result.get("prechoice_subcategories")
        trigger_keyword = result.get("trigger_keyword")

        # ====== ERROR 处理 ======
        if status == "ERROR":
            err_msg = result.get("message_to_user", "")
            msg = f"[{idx}/{total}] 测试: {repair_overview[:60]}... ❌ ERROR ({err_msg})"
            return {
                "index": idx, "repair_no": repair_no,
                "input": repair_overview, "expected_type": expected_type,
                "expected_project": expected_project,
                "expected_subcategory": expected_subcategory,
                "status": "ERROR", "prechoice": prechoice,
                "trigger_keyword": trigger_keyword, "error_type": "系统ERROR",
                "correct": False, "elapsed_time": round(elapsed, 2),
                "message": err_msg
            }, msg, True, True

        # ====== MISS 处理 ======
        if status in ("MISS", "NO_MATCH"):
            msg = f"[{idx}/{total}] 测试: {repair_overview[:60]}... 预期: {expected_project} ❌ {status}"
            return {
                "index": idx, "repair_no": repair_no,
                "input": repair_overview, "expected_type": expected_type,
                "expected_project": expected_project,
                "expected_subcategory": expected_subcategory,
                "status": status, "prechoice": prechoice,
                "trigger_keyword": trigger_keyword, "error_type": f"状态为{status}",
                "correct": False, "elapsed_time": round(elapsed, 2),
            }, msg, True, True

        # ====== UNCLASSIFIABLE 处理：纯催办/取消报修，无法自动分类，跳过不计入失败 ======
        if status == "UNCLASSIFIABLE":
            msg = f"[{idx}/{total}] 测试: {repair_overview[:60]}... ⏭️ UNCLASSIFIABLE (催办/取消，转人工)"
            return {
                "index": idx, "repair_no": repair_no,
                "input": repair_overview, "expected_type": expected_type,
                "expected_project": expected_project,
                "expected_subcategory": expected_subcategory,
                "status": "UNCLASSIFIABLE", "prechoice": prechoice,
                "trigger_keyword": trigger_keyword, "error_type": None,
                "correct": True, "elapsed_time": round(elapsed, 2),
            }, msg, False, False  # 不计入失败统计

        # ====== SUCCESS: 开始逐层验证 ======
        # Step 1: 检查 prechoice 是否包含预期 subCategory
        pre_ok, pre_msg = check_prechoice(prechoice, expected_type)

        # Step 2: 检查 trigger_keyword 是否匹配预期 problem
        trig_ok = False
        trig_msg = ""
        error_type = None
        mapped_problem_out = None

        if pre_ok:
            # Step 1 通过，检查 Step 2
            trig_ok, trig_msg, mapped_problem_out = check_trigger_keyword_full(
                trigger_keyword, expected_project, expected_type,
                keyword_to_problem, problem_to_keywords,
                problem_to_subcategory, subcategory_to_problems
            )
            if not trig_ok:
                error_type = "problem匹配错误"
        else:
            # Step 1 就失败了
            trig_msg = f"因subCategory分类错误，跳过trigger验证"
            error_type = "subCategory分类错误"

        correct = pre_ok and trig_ok

        if correct:
            msg = (f"[{idx}/{total}] 测试: {repair_overview[:60]}... "
                   f"预期: {expected_type}/{expected_project} ✅ 正确 "
                   f"(prechoice={prechoice}, trigger={trigger_keyword})")
        elif error_type == "subCategory分类错误":
            msg = (f"[{idx}/{total}] 测试: {repair_overview[:60]}... "
                   f"预期: {expected_type}/{expected_project} ❌ subCategory错误 "
                   f"(prechoice={prechoice})")
        else:
            msg = (f"[{idx}/{total}] 测试: {repair_overview[:60]}... "
                   f"预期: {expected_type}/{expected_project} ❌ problem错误 "
                   f"(trigger={trigger_keyword}, {trig_msg})")

        return {
            "index": idx, "repair_no": repair_no,
            "input": repair_overview, "expected_type": expected_type,
            "expected_project": expected_project,
            "expected_subcategory": expected_subcategory,
            "status": status, "prechoice": prechoice,
            "trigger_keyword": trigger_keyword, "error_type": error_type,
            "correct": correct, "elapsed_time": round(elapsed, 2),
            "pre_ok": pre_ok, "trig_ok": trig_ok,
            "trig_msg": trig_msg, "mapped_problem": mapped_problem_out,
        }, msg, (not correct), False

    except Exception as e:
        msg = f"[{idx}/{total}] 测试: {repair_overview[:60]}... ❌ 异常: {e}"
        return {
            "index": idx, "repair_no": repair_no,
            "input": repair_overview, "expected_type": expected_type,
            "expected_project": expected_project,
            "expected_subcategory": expected_subcategory,
            "status": "EXCEPTION", "prechoice": None,
            "trigger_keyword": None, "error_type": "系统异常",
            "correct": False, "elapsed_time": 0, "error": str(e)
        }, msg, True, True

    finally:
        try:
            processor.cancel_session(user_id)
        except Exception:
            pass


# ==================== 批量运行 ====================

def _run_batch(tasks, addresses, valid_subcategories, problem_to_subcategory,
               problem_to_keywords, keyword_to_problem, subcategory_to_problems,
               processor, workers, label):
    """
    运行一批测试任务（共享 processor 实例）。

    Returns:
        (results_by_idx, all_console, error_indices)
    """
    results_by_idx = {}
    all_console = []
    error_indices = set()

    print(f"  [{label}] 启动 {workers} 个 Worker，处理 {len(tasks)} 个用例...")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                process_one_case,
                task[0], task[1], task[2],
                addresses, valid_subcategories,
                problem_to_subcategory, problem_to_keywords,
                keyword_to_problem, subcategory_to_problems,
                processor
            ): task[1]
            for task in tasks
        }

        for future in as_completed(futures):
            result, msg, is_failure, is_error = future.result()
            idx = result["index"]
            results_by_idx[idx] = result
            all_console.append((idx, msg))
            # 仅重试技术性失败（API 异常/空返回），判定逻辑错误重试无意义
            if is_error or result["status"] in ("ERROR", "EXCEPTION", "MISS", "NO_MATCH"):
                error_indices.add(idx)

    return results_by_idx, all_console, error_indices


def _extract_idx(msg):
    m = re.match(r'\[(\d+)/\d+\]', msg)
    return int(m.group(1)) if m else 0


def run_problem_matching_test(test_cases, addresses, valid_subcategories,
                               problem_to_subcategory, problem_to_keywords,
                               keyword_to_problem, subcategory_to_problems,
                               test_count=200, workers=5, sequential=False):
    """两轮测试：全部用例 + 重试错误用例（共享 InputProcessor 实例）"""
    total = min(test_count, len(test_cases))
    if sequential:
        selected = test_cases[:total]
    else:
        selected = random.sample(test_cases, total)

    rules_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "rules"
    )

    # 创建共享的 InputProcessor（只连接一次 DB，仅一条错误日志）
    processor = InputProcessor(rules_dir=rules_dir)

    start_time = time.time()

    # ====== 第一轮 ======
    print(f"\n🔄 第一轮：全部 {total} 个用例")
    print("-" * 70)

    all_tasks = []
    for i, case in enumerate(selected):
        idx = i + 1
        all_tasks.append((case, idx, total))

    results_by_idx, all_console, error_indices = _run_batch(
        all_tasks, addresses, valid_subcategories,
        problem_to_subcategory, problem_to_keywords,
        keyword_to_problem, subcategory_to_problems,
        processor, workers, "第一轮"
    )

    # ====== 第二轮：重试错误用例 ======
    if error_indices:
        retry_tasks = []
        for idx in sorted(error_indices):
            case = selected[idx - 1]
            retry_tasks.append((case, idx, total))

        print(f"\n🔄 第二轮：重试 {len(retry_tasks)} 个失败/异常用例")
        print("-" * 70)

        retry_results, retry_console, retry_errors = _run_batch(
            retry_tasks, addresses, valid_subcategories,
            problem_to_subcategory, problem_to_keywords,
            keyword_to_problem, subcategory_to_problems,
            processor, workers, "第二轮"
        )

        # 更新结果
        for idx, result in retry_results.items():
            results_by_idx[idx] = result
            if idx not in retry_errors:
                result["retry"] = "recovered"

        old_console_by_idx = {idx: msg for idx, msg in all_console}
        for idx, msg in retry_console:
            tag = "[重试恢复]" if idx not in retry_errors else "[重试仍失败]"
            old_console_by_idx[idx] = f"{msg} {tag}"
        all_console = [(idx, old_console_by_idx[idx]) for idx in sorted(old_console_by_idx)]

        final_errors = retry_errors
    else:
        final_errors = error_indices

    # 按序号排序打印
    all_console.sort(key=lambda x: x[0])
    for _, msg in all_console:
        print(msg)

    # ====== 统计 ======
    total_elapsed = time.time() - start_time
    correct = sum(1 for r in results_by_idx.values() if r["correct"])
    skipped = sum(1 for r in results_by_idx.values() if r["status"] == "SKIPPED")
    effective_total = total - skipped

    # 错误分类统计
    subcategory_errors = sum(
        1 for r in results_by_idx.values()
        if r.get("error_type") == "subCategory分类错误"
    )
    problem_errors = sum(
        1 for r in results_by_idx.values()
        if r.get("error_type") == "problem匹配错误"
    )
    other_errors = sum(
        1 for r in results_by_idx.values()
        if not r["correct"] and r.get("error_type") not in ("subCategory分类错误", "problem匹配错误")
        and r["status"] != "SKIPPED"
    )

    # subCategory 通过率
    subcategory_ok = sum(1 for r in results_by_idx.values() if r.get("pre_ok", False))

    # problem 通过率（在 subCategory 通过的基础上）
    subcategory_passed = sum(1 for r in results_by_idx.values() if r.get("pre_ok", False))
    problem_ok = sum(1 for r in results_by_idx.values() if r.get("trig_ok", False))

    accuracy = (correct / effective_total * 100) if effective_total > 0 else 0
    subcategory_accuracy = (subcategory_ok / effective_total * 100) if effective_total > 0 else 0
    problem_accuracy = (problem_ok / subcategory_passed * 100) if subcategory_passed > 0 else 0
    retry_recovered = sum(1 for r in results_by_idx.values() if r.get("retry") == "recovered")

    # 按报修类型细分
    type_stats = {}
    for r in results_by_idx.values():
        t = r["expected_type"]
        if t not in type_stats:
            type_stats[t] = {"total": 0, "correct": 0, "sub_err": 0, "prob_err": 0}
        type_stats[t]["total"] += 1
        if r["correct"]:
            type_stats[t]["correct"] += 1
        if r.get("error_type") == "subCategory分类错误":
            type_stats[t]["sub_err"] += 1
        if r.get("error_type") == "problem匹配错误":
            type_stats[t]["prob_err"] += 1

    type_breakdown = {}
    for t, s in sorted(type_stats.items(), key=lambda x: -x[1]["total"]):
        type_breakdown[t] = {
            "total": s["total"],
            "correct": s["correct"],
            "sub_err": s["sub_err"],
            "prob_err": s["prob_err"],
            "rate": round(s["correct"] / s["total"] * 100, 1) if s["total"] > 0 else 0
        }

    summary_lines = []
    summary_lines.append("")
    summary_lines.append("=" * 70)
    summary_lines.append("📊 测试结果汇总 - problem & trigger_keyword 匹配测试")
    summary_lines.append("=" * 70)
    summary_lines.append(f"  并发数: {workers}")
    summary_lines.append(f"  有效测试数: {effective_total}")
    summary_lines.append(f"  ✅ 完全正确: {correct}")
    summary_lines.append(f"  ❌ 总计失败: {effective_total - correct}")
    summary_lines.append(f"     ├─ subCategory分类错误: {subcategory_errors}")
    summary_lines.append(f"     └─ problem匹配错误: {problem_errors}")
    if other_errors > 0:
        summary_lines.append(f"     └─ 其他错误(ERROR/MISS/异常): {other_errors}")
    if retry_recovered > 0:
        summary_lines.append(f"  ♻️  重试恢复: {retry_recovered} 条")
    summary_lines.append(f"  📈 subCategory通过率: {subcategory_accuracy:.1f}% ({subcategory_ok}/{effective_total})")
    summary_lines.append(f"  📈 problem匹配率(在subCategory通过基础上): {problem_accuracy:.1f}% ({problem_ok}/{subcategory_passed})")
    summary_lines.append(f"  📈 综合正确率: {accuracy:.1f}%")
    summary_lines.append(f"  ⏱️  总耗时: {total_elapsed:.1f}秒")
    summary_lines.append(f"  ⏱️  平均每条: {total_elapsed / total:.1f}秒")
    summary_lines.append("")
    summary_lines.append("📊 各类型统计:")
    summary_lines.append(f"  {'类型':10s} {'总数':>5s} {'正确':>5s} {'subCategory错误':>14s} {'problem错误':>12s} {'正确率':>8s}")
    summary_lines.append("  " + "-" * 60)
    for t, s in type_breakdown.items():
        summary_lines.append(
            f"  {t:10s} {s['total']:>5d} {s['correct']:>5d} "
            f"{s['sub_err']:>14d} {s['prob_err']:>12d} {s['rate']:>7.1f}%"
        )

    for line in summary_lines:
        print(line)

    # 构建 file_lines：仅失败案例 + 总结
    file_lines = []
    # 头部说明
    file_lines.append("=" * 90)
    file_lines.append("problem & trigger_keyword 匹配测试 - 失败案例日志")
    file_lines.append("=" * 90)
    file_lines.append(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    file_lines.append(f"测试数量: {total} 条 (跳过 {skipped} 条无效subCategory)")
    file_lines.append("")
    file_lines.append("【错误类型说明】")
    file_lines.append("  subCategory分类错误: 模型在Step1粗筛时未能将预期报修类型选入prechoice")
    file_lines.append("  problem匹配错误: subCategory正确但trigger_keyword未能匹配到预期problem")
    file_lines.append("  其他错误: 系统ERROR/MISS/NO_MATCH/异常")
    file_lines.append("=" * 90)
    file_lines.append("")

    for r in sorted(results_by_idx.values(), key=lambda x: x["index"]):
        if not r["correct"] or r["status"] in ("ERROR", "EXCEPTION", "MISS", "NO_MATCH"):
            idx = r["index"]
            case = selected[idx - 1]

            error_type = r.get("error_type", "未知")
            pre = r.get("prechoice")
            trig = r.get("trigger_keyword")
            trig_msg = r.get("trig_msg", "")

            file_lines.append(f"[{idx}/{total}] 维修单号: {r['repair_no']}")
            file_lines.append(f"  报修概述: {case['repair_overview']}")
            file_lines.append(f"  预期报修类型(subCategory): {r['expected_type']}")
            file_lines.append(f"  预期报修项目(problem): {r['expected_project']}")
            file_lines.append(f"  模型prechoice: {pre}")
            file_lines.append(f"  模型trigger_keyword: {trig}")
            file_lines.append(f"  错误类型: {error_type}")
            if error_type == "subCategory分类错误":
                file_lines.append(f"  说明: prechoice不包含预期subCategory '{r['expected_type']}'，分类第一步就错了")
            elif error_type == "problem匹配错误":
                file_lines.append(f"  说明: {trig_msg}")
                if r.get("mapped_problem"):
                    file_lines.append(f"  映射到的problem: {r['mapped_problem']}")
            elif error_type in ("系统ERROR", "系统异常"):
                file_lines.append(f"  说明: {r.get('message', r.get('error', ''))}")
            else:
                file_lines.append(f"  说明: 状态为 {r['status']}")
            file_lines.append(f"  耗时: {r['elapsed_time']}秒")
            if r.get("retry") == "recovered":
                file_lines.append(f"  备注: 重试后恢复")
            file_lines.append("")

    file_lines.append("")
    file_lines.extend(summary_lines)

    return file_lines, accuracy


# ==================== 主函数 ====================

def main():
    print("=" * 70)
    print("   problem & trigger_keyword 匹配测试（并发 + 失败重跑）")
    print("   验证：subCategory分类 → trigger_keyword匹配 两步正确性")
    print("=" * 70)

    if not os.environ.get('ds_apikey'):
        print("❌ 错误: 环境变量 ds_apikey 未设置")
        print("   请先设置 DeepSeek API Key:")
        print("   set ds_apikey=your_key_here")
        sys.exit(1)

    # 支持命令行参数: python test_problem_matching.py [test_count] [workers] [sequential] [project]
    # 例如: python test_problem_matching.py 1000 5 0           (1000条, 5并发, 随机, 全项目)
    # 例如: python test_problem_matching.py 1000 5 0 水        (1000条, 5并发, 随机, 仅"水"项目)
    # 例如: python test_problem_matching.py                    (交互式输入)
    import sys
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    available_projects = list_available_projects(base_dir)

    if len(sys.argv) > 1:
        # 命令行参数模式
        try:
            test_count = int(sys.argv[1])
            workers = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            sequential = (sys.argv[3] == "1") if len(sys.argv) > 3 else False
            project = sys.argv[4] if len(sys.argv) > 4 else None
            # 验证项目名
            if project and project not in available_projects:
                print(f"❌ 错误: 未知项目 '{project}'")
                print(f"   可用项目: {', '.join(available_projects)}")
                sys.exit(1)
            print(f"\n📋 命令行参数: {test_count} 条, {workers} 并发, "
                  f"{'顺序抽取' if sequential else '随机抽取'}, 项目: {project or '全项目'}")
            if project:
                summary = get_project_summary(base_dir, project)
                if summary:
                    total = summary.get("总单元数", "?")
                    proj_count = summary.get("报修项目数", "?")
                    print(f"   项目摘要: 共 {total} 条记录, {proj_count} 个报修项目")
        except (ValueError, IndexError) as e:
            print(f"❌ 参数解析错误: {e}")
            print("   用法: python test_problem_matching.py [测试数量] [并发数] [顺序模式(0/1)] [项目名]")
            print("   示例: python test_problem_matching.py 1000 5 0 水")
            sys.exit(1)
    else:
        # 交互式参数输入 — 先选项目，再选测试参数
        # 第一步：选择测试范围（全类型 vs 某个类型）
        print(f"\n  可选项目:")
        print(f"    0 - 全项目 (使用 工单详情_detail.json)")
        for i, proj in enumerate(available_projects, 1):
            summary = get_project_summary(base_dir, proj)
            total = summary.get("总单元数", "?")
            proj_count = summary.get("报修项目数", "?")
            print(f"    {i} - {proj} ({total}条, {proj_count}个报修项目)")
        project_input = input(f"\n  请选择测试范围 [默认: 0=全项目]: ").strip()
        if project_input and project_input != "0":
            try:
                proj_idx = int(project_input) - 1
                if 0 <= proj_idx < len(available_projects):
                    project = available_projects[proj_idx]
                else:
                    print(f"  ❌ 无效选择，使用全项目")
                    project = None
            except ValueError:
                if project_input in available_projects:
                    project = project_input
                else:
                    print(f"  ❌ 无效项目名 '{project_input}'，使用全项目")
                    project = None
        else:
            project = None

        selected_label = project if project else "全项目"
        print(f"  ✅ 已选择: {selected_label}")
        if project:
            summary = get_project_summary(base_dir, project)
            if summary:
                total = summary.get("总单元数", "?")
                proj_count = summary.get("报修项目数", "?")
                print(f"     共 {total} 条记录, {proj_count} 个报修项目")

        # 第二步：输入测试参数
        print(f"\n📋 请输入测试参数（直接回车使用默认值）：")

        test_count_input = input(f"  测试条目数量 [默认: 200]: ").strip()
        test_count = int(test_count_input) if test_count_input else 200

        workers_input = input(f"  并发线程数量 [默认: 5]: ").strip()
        workers = int(workers_input) if workers_input else 5

        mode_input = input(f"  抽样方式: (1) 顺序抽取 (2) 随机抽取 [默认: 2]: ").strip()
        sequential = (mode_input == "1")

        print(f"\n  配置确认: {test_count} 条, {workers} 并发, "
              f"{'顺序抽取' if sequential else '随机抽取'}, 项目: {project or '全项目'}")

    print("\n🔄 加载数据...")
    test_cases, addresses, project_name = load_data(project=project)
    valid_subcategories, problem_to_subcategory, problem_to_keywords, \
        keyword_to_problem, subcategory_to_problems = load_mappings()

    print(f"   工单有效用例: {len(test_cases)}")
    print(f"   地址样本: {len(addresses)}")
    print(f"   有效subCategory数: {len(valid_subcategories)}")
    total_problems = sum(len(v) for v in subcategory_to_problems.values())
    print(f"   problem总数: {total_problems}")
    total_keywords = len(keyword_to_problem)
    print(f"   trigger_keyword总数: {total_keywords}")

    # 测试数量适配：不超过实际可用用例数
    available_count = len(test_cases)
    if test_count > available_count:
        print(f"   ⚠️  指定测试数量 {test_count} 超过可用用例数 {available_count}，将按 {available_count} 条进行测试")
        test_count = available_count

    print(f"\n🚀 开始两轮测试（第一轮全部 + 第二轮重试失败），共 {test_count} 条...")

    file_lines, accuracy = run_problem_matching_test(
        test_cases, addresses, valid_subcategories,
        problem_to_subcategory, problem_to_keywords,
        keyword_to_problem, subcategory_to_problems,
        test_count=test_count, workers=workers, sequential=sequential
    )

    # 保存日志
    log_dir = os.path.join(base_dir, "data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 项目测试日志名: (项目名称)_时间戳.txt；全项目: problem_matching_时间戳.txt
    if project:
        txt_path = os.path.join(log_dir, f"({project_name})_{timestamp}.txt")
    else:
        txt_path = os.path.join(log_dir, f"problem_matching_{timestamp}.txt")

    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(file_lines))
        f.write("\n")

    print(f"\n📝 日志已保存到: {txt_path}")
    print(f"   文件仅包含失败案例 + 总结，共 {len(file_lines)} 行")
    print("=" * 70)

    return {"accuracy": accuracy}


if __name__ == "__main__":
    main()