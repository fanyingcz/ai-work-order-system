"""
智能工单系统 - subCategory 粗筛覆盖率测试（并行版 + 失败重跑）

【测试目标】
验证大模型在第一步粗筛时，选出的2个 prechoice_subcategories 是否能在95%以上的
情况下覆盖正确的 subCategory。

【并行 + 重试机制】
1. 第一轮：所有用例并行测试（默认 5 并发）
2. 第二轮：收集第一轮中 ERROR/EXCEPTION 的用例，重新并行测试
3. 第二轮仍失败的记为最终 ERROR

【输出】
- data/logs/subcategory_coverage_{timestamp}.txt: 仅包含未覆盖/ERROR的行 + 总结
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


def load_data():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


def load_valid_subcategories():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sub_file = os.path.join(base_dir, "data", "rules", "subcategories.json")
    with open(sub_file, 'r', encoding='utf-8') as f:
        sub_data = json.load(f)
    return {item["subCategory"] for item in sub_data}


def process_one_case(case, idx, total, addresses, valid_subcategories, rules_dir):
    """处理单个测试用例。返回 (result_dict, console_line, is_failure, is_error)。"""
    repair_overview = case["repair_overview"]
    expected_type = case["repair_type"]
    expected_project = case["repair_project"]
    repair_no = case["repair_no"]

    if expected_type not in valid_subcategories:
        msg = f"[{idx}/{total}] 测试: {repair_overview[:60]}... 预期: {expected_type} ⏭️ SKIPPED"
        return {
            "index": idx, "repair_no": repair_no,
            "input": repair_overview, "expected_type": expected_type,
            "expected_project": expected_project,
            "status": "SKIPPED", "prechoice": None,
            "correct": False, "elapsed_time": 0,
        }, msg, False, False

    address = random.choice(addresses) if addresses else "上海市浦东新区某小区"
    full_input = f"{repair_overview}，地址是{address}"
    user_id = f"coverage_test_{idx}_{int(time.time() * 1000000) % 10000000}"

    try:
        processor = InputProcessor(rules_dir=rules_dir)
    except Exception as e:
        msg = f"[{idx}/{total}] 测试: {repair_overview[:60]}... 预期: {expected_type} ❌ 初始化异常: {e}"
        return {
            "index": idx, "repair_no": repair_no,
            "input": repair_overview, "expected_type": expected_type,
            "expected_project": expected_project,
            "status": "EXCEPTION", "prechoice": None,
            "correct": False, "elapsed_time": 0, "error": str(e)
        }, msg, True, True

    try:
        t_start = time.time()
        step1_result = processor._step1_select_subcategories(user_id, full_input)
        elapsed = time.time() - t_start

        status = step1_result.get("status", "ERROR")
        prechoice = step1_result.get("prechoice")

        if status == "ERROR":
            err_msg = step1_result.get("message_to_user", "")
            msg = f"[{idx}/{total}] 测试: {repair_overview[:60]}... 预期: {expected_type} ❌ ERROR ({err_msg})"
            result = {
                "index": idx, "repair_no": repair_no,
                "input": repair_overview, "expected_type": expected_type,
                "expected_project": expected_project,
                "status": "ERROR", "prechoice": prechoice,
                "correct": False, "elapsed_time": round(elapsed, 2),
                "message": err_msg
            }
            return result, msg, True, True
        else:
            is_correct = prechoice and expected_type in prechoice
            if is_correct:
                msg = f"[{idx}/{total}] 测试: {repair_overview[:60]}... 预期: {expected_type} ✅ 覆盖 (prechoice={prechoice})"
            else:
                msg = f"[{idx}/{total}] 测试: {repair_overview[:60]}... 预期: {expected_type} ❌ 未覆盖 (prechoice={prechoice})"

            result = {
                "index": idx, "repair_no": repair_no,
                "input": repair_overview, "expected_type": expected_type,
                "expected_project": expected_project,
                "status": status, "prechoice": prechoice,
                "correct": is_correct, "elapsed_time": round(elapsed, 2)
            }
            return result, msg, (not is_correct), False

    except Exception as e:
        msg = f"[{idx}/{total}] 测试: {repair_overview[:60]}... 预期: {expected_type} ❌ 异常: {e}"
        result = {
            "index": idx, "repair_no": repair_no,
            "input": repair_overview, "expected_type": expected_type,
            "expected_project": expected_project,
            "status": "EXCEPTION", "prechoice": None,
            "correct": False, "elapsed_time": 0, "error": str(e)
        }
        return result, msg, True, True

    finally:
        try:
            processor.cancel_session(user_id)
        except Exception:
            pass


def _run_batch(tasks, addresses, valid_subcategories, rules_dir, workers, label):
    """
    运行一批测试任务并返回结果。

    Args:
        tasks: [(case, idx, total), ...]
        label: 本轮标签（如"第一轮"、"第二轮重试"）

    Returns:
        (results_by_idx: dict, all_console: list, error_indices: set)
    """
    results_by_idx = {}
    all_console = []
    error_indices = set()

    print(f"  [{label}] 启动 {workers} 个 Worker，处理 {len(tasks)} 个用例...")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(process_one_case, task[0], task[1], task[2],
                            addresses, valid_subcategories, rules_dir): task[1]
            for task in tasks
        }

        for future in as_completed(futures):
            result, msg, is_failure, is_error = future.result()
            idx = result["index"]
            results_by_idx[idx] = result
            all_console.append((idx, msg))
            if is_error or result["status"] in ("ERROR", "EXCEPTION"):
                error_indices.add(idx)

    return results_by_idx, all_console, error_indices


def _extract_idx(msg):
    m = re.match(r'\[(\d+)/\d+\]', msg)
    return int(m.group(1)) if m else 0


def run_coverage_test(test_cases, addresses, valid_subcategories,
                       test_count=200, workers=5, sequential=False):
    """两轮测试：第一轮全部 + 第二轮重试错误用例。"""
    total = min(test_count, len(test_cases))
    if sequential:
        selected = test_cases[:total]
    else:
        selected = random.sample(test_cases, total)

    rules_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "rules"
    )

    start_time = time.time()

    # ====== 第一轮：全部用例 ======
    print(f"\n🔄 第一轮：全部 {total} 个用例")
    print("-" * 70)

    all_tasks = []
    for i, case in enumerate(selected):
        idx = i + 1
        all_tasks.append((case, idx, total))

    results_by_idx, all_console, error_indices = _run_batch(
        all_tasks, addresses, valid_subcategories, rules_dir, workers, "第一轮"
    )

    # ====== 第二轮：重试错误用例 ======
    if error_indices:
        retry_tasks = []
        for idx in sorted(error_indices):
            case = selected[idx - 1]  # idx 是 1-based
            retry_tasks.append((case, idx, total))

        print(f"\n🔄 第二轮：重试 {len(retry_tasks)} 个错误/异常用例")
        print("-" * 70)

        retry_results, retry_console, retry_errors = _run_batch(
            retry_tasks, addresses, valid_subcategories, rules_dir, workers, "第二轮"
        )

        # 更新结果：用重试结果替换第一轮的错误结果
        for idx, result in retry_results.items():
            results_by_idx[idx] = result
            # 标记重试结果
            if idx not in retry_errors:
                result["retry"] = "recovered"

        # 更新控制台输出
        old_console_by_idx = {idx: msg for idx, msg in all_console}
        for idx, msg in retry_console:
            old_console_by_idx[idx] = f"{msg} [重试恢复]" if idx not in retry_errors else f"{msg} [重试仍失败]"
        all_console = [(idx, old_console_by_idx[idx]) for idx in sorted(old_console_by_idx)]

        # 更新最终错误集合
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
    errors_count = len(final_errors)
    skipped = sum(1 for r in results_by_idx.values() if r["status"] == "SKIPPED")
    misses = sum(1 for r in results_by_idx.values() if r["status"] == "MISS")
    effective_total = total - skipped
    coverage_rate = (correct / effective_total * 100) if effective_total > 0 else 0
    retry_recovered = sum(1 for r in results_by_idx.values() if r.get("retry") == "recovered")

    type_stats = {}
    for r in results_by_idx.values():
        t = r["expected_type"]
        if t not in type_stats:
            type_stats[t] = {"total": 0, "correct": 0}
        type_stats[t]["total"] += 1
        if r["correct"]:
            type_stats[t]["correct"] += 1
    type_breakdown = {
        t: {"total": s["total"], "correct": s["correct"],
            "rate": round(s["correct"] / s["total"] * 100, 1) if s["total"] > 0 else 0}
        for t, s in sorted(type_stats.items(), key=lambda x: -x[1]["total"])
    }

    summary_lines = []
    summary_lines.append("")
    summary_lines.append("=" * 70)
    summary_lines.append("📊 测试结果汇总")
    summary_lines.append("=" * 70)
    summary_lines.append(f"  并发数: {workers}")
    summary_lines.append(f"  有效测试数: {effective_total}")
    summary_lines.append(f"  ✅ 覆盖正确: {correct}")
    summary_lines.append(f"  ❌ 未覆盖: {effective_total - correct}")
    summary_lines.append(f"  ⚠️ 错误/异常: {errors_count}")
    if retry_recovered > 0:
        summary_lines.append(f"  ♻️  重试恢复: {retry_recovered} 条")
    summary_lines.append(f"  📍 缺地址(MISS): {misses}")
    summary_lines.append(f"  📈 覆盖率: {coverage_rate}%")
    summary_lines.append(f"  🎯 目标: 95.0%")
    summary_lines.append(f"  {'✅ 达标' if coverage_rate >= 95.0 else '❌ 未达标'}")
    summary_lines.append(f"  ⏱️  总耗时: {total_elapsed}秒")
    summary_lines.append(f"  ⏱️  平均每条: {total_elapsed / total:.1f}秒")
    summary_lines.append("")
    summary_lines.append("📊 各类型覆盖率:")
    for t, s in type_breakdown.items():
        bar = "█" * int(s["rate"] / 10) + "░" * (10 - int(s["rate"] / 10))
        summary_lines.append(f"  {t:8s}  {s['correct']}/{s['total']}  {s['rate']:5.1f}%  {bar}")

    for line in summary_lines:
        print(line)

    # 构建 file_lines：仅未覆盖 + 最终ERROR + 总结
    file_lines = []
    for r in sorted(results_by_idx.values(), key=lambda x: x["index"]):
        if not r["correct"] or r["status"] in ("ERROR", "EXCEPTION"):
            idx = r["index"]
            case = selected[idx - 1]
            if r["status"] in ("ERROR", "EXCEPTION"):
                err = r.get("message") or r.get("error", "")
                tag = "[重试仍失败]" if r["index"] in final_errors else ""
                file_lines.append(
                    f"[{idx}/{total}] 测试: {case['repair_overview'][:60]}... "
                    f"预期: {r['expected_type']} ❌ ERROR ({err}) {tag}".strip()
                )
            elif not r["correct"]:
                pre = r.get("prechoice")
                file_lines.append(
                    f"[{idx}/{total}] 测试: {case['repair_overview'][:60]}... "
                    f"预期: {r['expected_type']} ❌ 未覆盖 (prechoice={pre})"
                )

    file_lines.sort(key=_extract_idx)
    file_lines.extend(summary_lines)

    return file_lines, coverage_rate


def main():
    print("=" * 70)
    print("   subCategory 粗筛覆盖率测试（并行 + 失败重跑）")
    print("=" * 70)

    if not os.environ.get('ds_apikey'):
        print("❌ 错误: 环境变量 ds_apikey 未设置")
        sys.exit(1)

    # 交互式参数输入
    print("\n📋 请输入测试参数（直接回车使用默认值）：")
    
    test_count_input = input(f"  测试条目数量 [默认: 200]: ").strip()
    test_count = int(test_count_input) if test_count_input else 200

    workers_input = input(f"  并发线程数量 [默认: 5]: ").strip()
    workers = int(workers_input) if workers_input else 5

    mode_input = input(f"  抽样方式: (1) 顺序抽取 (2) 随机抽取 [默认: 2]: ").strip()
    sequential = (mode_input == "1")

    print(f"\n  配置确认: {test_count} 条, {workers} 并发, {'顺序抽取' if sequential else '随机抽取'}")

    print("\n🔄 加载数据...")
    test_cases, addresses = load_data()
    valid_subcategories = load_valid_subcategories()
    print(f"   工单有效用例: {len(test_cases)}")
    print(f"   地址样本: {len(addresses)}")

    print(f"\n🚀 开始两轮测试（第一轮全部 + 第二轮重试错误），共 {test_count} 条...")

    file_lines, coverage_rate = run_coverage_test(
        test_cases, addresses, valid_subcategories,
        test_count=test_count, workers=workers, sequential=sequential
    )

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(base_dir, "data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_path = os.path.join(log_dir, f"subcategory_coverage_{timestamp}.txt")

    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(file_lines))
        f.write("\n")

    print(f"\n📝 日志已保存到: {txt_path}")
    print(f"   文件仅包含未覆盖/ERROR 行 + 总结，共 {len(file_lines)} 行")
    print("=" * 70)

    return {"coverage_rate": coverage_rate}


if __name__ == "__main__":
    main()