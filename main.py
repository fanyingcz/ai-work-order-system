#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
智能工单系统 - 主程序入口

【功能】
1. 交互式模式
2. JSON 批量模式
3. 数据库查询模式
4. 完整测试模式
5. 模型准确度测试模式
6. 反馈管理（提交关键词建议、审核反馈）
7. 地址映射管理（增删改查）
"""

import sys
import os
import json
import random
import time
import argparse
from datetime import datetime
from typing import Optional, List, Dict, Any

from db import get_db
from feedback import FeedbackHandler


# ============================================================
# Feedback & Address interactive helpers
# ============================================================

def _feedback_submit(user_input: str):
    parts = user_input.split(None, 3)
    if len(parts) < 4:
        print("用法: feedback-submit <工单号> <人工problem> <人工关键词>")
        return
    fh = FeedbackHandler()
    r = fh.submit(parts[1], parts[2], parts[3])
    if r['status'] == 'SUCCESS':
        print(f"✅ 反馈已提交, ID={r['id']}, 等待审核")
        print(f"   工单号: {parts[1]}")
        print(f"   模型判定problem: {r.get('model_problem', 'N/A')}")
        print(f"   人工判定problem: {parts[2]}")
        print(f"   人工关键词: {parts[3]}")
    else:
        print(f"❌ 提交失败: {r['message']}")


def _feedback_list():
    fh = FeedbackHandler()
    pending = fh.get_pending()
    if not pending:
        print("📋 没有待审核的反馈")
        return
    print(f"📋 待审核反馈 (共 {len(pending)} 条):")
    print("-" * 80)
    for fb in pending:
        print(f"  ID={fb['id']} | 工单={fb['order_no']} | 模型problem={fb['model_problem']} | "
              f"人工problem={fb['human_problem']} | 关键词={fb['human_keyword']} | {fb['status']}")
    print("-" * 80)


def _feedback_review(user_input: str):
    parts = user_input.split()
    if len(parts) < 3:
        print("用法: feedback-review <反馈ID> approve|reject")
        return
    try:
        fid = int(parts[1])
    except ValueError:
        print("❌ 反馈ID必须是数字")
        return
    action = parts[2].lower()
    fh = FeedbackHandler()
    if action == 'approve':
        r = fh.approve(fid)
    elif action == 'reject':
        r = fh.reject(fid)
    else:
        print("❌ 操作只能是 approve 或 reject")
        return
    if r['status'] == 'SUCCESS':
        print(f"✅ {r['message']}")
    else:
        print(f"❌ {r['message']}")


def _addr_list():
    db = get_db()
    conn = db._get_connection()
    with conn.cursor() as c:
        c.execute("SELECT id, community, street, property_company, maintenance_unit, district FROM address_mappings ORDER BY id")
        rows = c.fetchall()
    if not rows:
        print("📋 没有地址映射数据")
        return
    print(f"📋 地址映射 (共 {len(rows)} 条):")
    print("-" * 100)
    print(f"  {'ID':4s} {'小区名称':16s} {'街道':14s} {'物业公司':20s} {'维修单位':16s} {'区县':8s}")
    print(f"  {'─'*4} {'─'*16} {'─'*14} {'─'*20} {'─'*16} {'─'*8}")
    for r in rows:
        print(f"  {r['id']:<4d} {(r['community'] or '')[:14]:16s} {(r['street'] or '')[:12]:14s} "
              f"{(r['property_company'] or '')[:18]:20s} {(r['maintenance_unit'] or '')[:14]:16s} "
              f"{(r['district'] or '')[:6]:8s}")
    print("-" * 100)
    db.close()


def _addr_add(user_input: str):
    parts = user_input.split(None, 4)
    if len(parts) < 3:
        print("用法: addr-add <小区名称> <街道> [物业公司] [维修单位]")
        print("  小区名称 必填, 街道为空时用 - 代替")
        return
    community = parts[1]
    street = parts[2] if parts[2] != '-' else ''
    property_company = parts[3] if len(parts) > 3 else ''
    maintenance_unit = parts[4] if len(parts) > 4 else ''
    if not community.strip():
        print("❌ 小区名称不能为空")
        return
    try:
        db = get_db()
        conn = db._get_connection()
        with conn.cursor() as c:
            c.execute(
                "INSERT INTO address_mappings (community, street, property_company, maintenance_unit, district, city) "
                "VALUES (%s, %s, %s, %s, '浦东新区', '上海市')",
                (community, street, property_company, maintenance_unit))
            print(f"✅ 地址映射已添加, ID={c.lastrowid}")
            print(f"   小区: {community} | 街道: {street or '(无)'} | 物业: {property_company or '(无)'} | 维修: {maintenance_unit or '(无)'}")
    except Exception as e:
        if 'Duplicate' in str(e) or 'duplicate' in str(e):
            print(f"❌ 添加失败: (小区={community}, 街道={street}) 已存在")
        else:
            print(f"❌ 添加失败: {e}")


def _addr_modify(user_input: str):
    parts = user_input.split()
    if len(parts) < 3:
        print("用法: addr-modify <ID> <字段>=<值> [<字段>=<值> ...]")
        print("  字段: community, street, property_company, maintenance_unit")
        return
    try:
        aid = int(parts[1])
    except ValueError:
        print("❌ ID必须是数字")
        return
    fields = {}
    for p in parts[2:]:
        if '=' not in p:
            print(f"❌ 格式错误: {p}")
            return
        k, v = p.split('=', 1)
        k = k.strip()
        v = v.strip()
        if k in ('community', 'street', 'property_company', 'maintenance_unit'):
            if k == 'community' and not v:
                print("❌ community 不能为空")
                return
            fields[k] = v
        else:
            print(f"❌ 未知字段: {k}")
            return
    if not fields:
        print("❌ 没有要更新的字段")
        return
    try:
        db = get_db()
        conn = db._get_connection()
        with conn.cursor() as c:
            set_clause = ', '.join(f"{k}=%s" for k in fields)
            values = list(fields.values()) + [aid]
            c.execute(f"UPDATE address_mappings SET {set_clause} WHERE id=%s", values)
            if c.rowcount == 0:
                print(f"❌ 未找到ID={aid}的记录")
            else:
                print(f"✅ 地址映射 ID={aid} 已更新: {fields}")
    except Exception as e:
        if 'Duplicate' in str(e) or 'duplicate' in str(e):
            print(f"❌ 更新失败: (community, street) 组合已存在")
        else:
            print(f"❌ 更新失败: {e}")


def _addr_delete(user_input: str):
    parts = user_input.split()
    if len(parts) < 2:
        print("用法: addr-delete <ID>")
        return
    try:
        aid = int(parts[1])
    except ValueError:
        print("❌ ID必须是数字")
        return
    db = get_db()
    conn = db._get_connection()
    with conn.cursor() as c:
        c.execute("DELETE FROM address_mappings WHERE id=%s", (aid,))
        if c.rowcount == 0:
            print(f"❌ 未找到ID={aid}的记录")
        else:
            print(f"✅ 地址映射 ID={aid} 已删除")


# ============================================================
# Data loaders
# ============================================================

def load_testmap_addresses() -> List[str]:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    testmap_path = os.path.join(base_dir, "testmap.txt")
    if not os.path.exists(testmap_path):
        return []
    addresses = []
    with open(testmap_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            parts = line.split('- ', 1)
            addr = parts[1].strip() if len(parts) == 2 else line
            if addr: addresses.append(addr)
    return addresses


def load_test_cases() -> List[Dict[str, str]]:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    detail_path = os.path.join(base_dir, "data", "test_data", "工单详情_detail.json")
    if not os.path.exists(detail_path):
        return []
    with open(detail_path, 'r', encoding='utf-8') as f:
        detail_data = json.load(f)
    test_cases = []
    for item in detail_data:
        if item.get("报修概述") and item.get("报修项目") and item.get("报修类型"):
            test_cases.append({
                "repair_overview": item["报修概述"],
                "repair_project": item["报修项目"],
                "repair_type": item["报修类型"],
                "repair_no": item.get("维修单号", "")
            })
    return test_cases


def load_classification_maps() -> tuple:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base_dir, "data", "rules", "category.json"), 'r', encoding='utf-8') as f:
        rules = json.load(f)
    with open(os.path.join(base_dir, "data", "rules", "subcategories.json"), 'r', encoding='utf-8') as f:
        subcategories = json.load(f)
    valid_subcategories = {item["subCategory"] for item in subcategories}
    problem_to_keywords, subcategory_to_problems, keyword_to_problem = {}, {}, {}
    for rule in rules:
        sub, problem, keywords = rule.get("subCategory",""), rule.get("problem",""), rule.get("trigger_keywords",[])
        if sub and problem:
            subcategory_to_problems.setdefault(sub, []).append(problem)
            problem_to_keywords[problem] = keywords
            for kw in keywords: keyword_to_problem[kw] = problem
    return subcategory_to_problems, problem_to_keywords, keyword_to_problem, valid_subcategories


# ============================================================
# Print helpers
# ============================================================

def print_banner():
    print("=" * 60)
    print("          智能工单系统 v2.0")
    print("=" * 60)
    print("说明：请输入您的报修信息（问题描述 + 地址）")
    print("      系统将引导您完成报修流程")
    print()
    print("  报修命令：")
    print("    quit/exit        退出程序")
    print("    cancel           取消当前报修")
    print("    status           查看当前会话状态")
    print("    switch <user>    切换用户")
    print()
    print("  查询命令：")
    print("    list             查看最近20条工单")
    print("    list <关键词>     按关键词搜索")
    print("    detail <工单号>   查看工单详情")
    print()
    print("  反馈管理：")
    print("    feedback-submit <工单号> <problem> <关键词>")
    print("    feedback-list    查看待审核反馈")
    print("    feedback-review <ID> approve|reject")
    print()
    print("  地址管理：")
    print("    addr-list        查看地址映射")
    print("    addr-add <小区> <街道> [物业] [维修]")
    print("    addr-modify <ID> <字段>=<值> ...")
    print("    addr-delete <ID>")
    print()
    print("  测试模式：")
    print("    test             完整测试")
    print("    benchmark        模型准确度测试")
    print("=" * 60)


def print_work_order(work_order: dict):
    print()
    print("=" * 60)
    print("  📋 工单详情")
    print("=" * 60)
    print(f"  工单号:        {work_order.get('order_no', 'N/A')}")
    print(f"  受理时间:      {work_order.get('accept_time', 'N/A')}")
    print(f"  工单状态:      {work_order.get('status', 'N/A')}")
    print("-" * 60)
    print(f"  报修概述:      {work_order.get('user_input', 'N/A')}")
    print(f"  报修类型:      {work_order.get('sub_category', 'N/A')}")
    print(f"  报修项目:      {work_order.get('problem', 'N/A')}")
    print("-" * 60)
    print(f"  优先级:        {work_order.get('priority', 'N/A')}")
    print(f"  所需资质证书:  {work_order.get('required_cert', 'N/A')}")
    print(f"  目标维修部门:  {work_order.get('target_dept_semantic', 'N/A')}")
    print("-" * 60)
    print(f"  报修地址:      {work_order.get('address', 'N/A')}")
    print(f"  物业公司:      {work_order.get('property_company', 'N/A')}")
    print(f"  维修单位:      {work_order.get('maintenance_unit', 'N/A')}")

    # 显示指派的工人信息
    worker_id = work_order.get('worker_id')
    if worker_id:
        worker = get_db().get_worker_by_id(worker_id)
        if worker:
            print("-" * 60)
            print(f"  指派工人:      {worker.get('name', 'N/A')}")
            print(f"  联系电话:      {worker.get('phone', 'N/A')}")

    print("=" * 60)
    print()


# ============================================================
# DB query mode
# ============================================================

def db_query_mode(args):
    db = get_db()
    if args.detail:
        wo = db.get_by_order_no(args.detail)
        if wo: print_work_order(wo)
        else: print(f"❌ 未找到工单号: {args.detail}")
        db.close()
        return
    limit = args.limit or 100
    offset = ((args.page or 1) - 1) * limit
    results = db.search(
        order_no=args.order_no, sub_category=args.sub_category,
        property_company=args.property_company, required_cert=args.required_cert,
        target_dept_semantic=args.target_dept_semantic, priority=args.priority,
        status=args.status, keyword=args.keyword,
        start_time=args.start_time, end_time=args.end_time,
        limit=limit, offset=offset)
    total = db.search_count(
        order_no=args.order_no, sub_category=args.sub_category,
        property_company=args.property_company, required_cert=args.required_cert,
        target_dept_semantic=args.target_dept_semantic, priority=args.priority,
        status=args.status, keyword=args.keyword,
        start_time=args.start_time, end_time=args.end_time)
    print()
    print(f"📊 工单查询结果 | 总计: {total} 条 | 显示: {len(results)} 条")
    print("-" * 90)
    if results:
        print(f"  {'序号':4s} {'工单号':22s} {'报修项目':16s} {'类型':14s} {'优先级':12s} {'物业公司':12s}")
        print(f"  {'─'*4} {'─'*22} {'─'*16} {'─'*14} {'─'*12} {'─'*12}")
        for i, wo in enumerate(results, 1):
            print(f"  {i:<4d} {wo.get('order_no', 'N/A'):22s} "
                  f"{wo.get('problem', 'N/A'):16s} {wo.get('sub_category', 'N/A'):14s} "
                  f"{wo.get('priority', 'N/A'):12s} {wo.get('property_company', 'N/A'):12s}")
    db.close()


# ============================================================
# Interactive embedded query
# ============================================================

def _interactive_list(user_input: str):
    db = get_db()
    parts = user_input.split()
    keyword = status = sub_category = property_company = required_cert = target_dept_semantic = None
    limit = 20
    i = 1
    while i < len(parts):
        if parts[i] == '--status' and i+1 < len(parts):
            status = parts[i+1].upper(); i+=2
        elif parts[i] == '--sub_category' and i+1 < len(parts):
            sub_category = parts[i+1]; i+=2
        elif parts[i] == '--limit' and i+1 < len(parts):
            try: limit = int(parts[i+1])
            except ValueError: pass
            i+=2
        else:
            keyword = ' '.join(parts[i:]); break
    results = db.search(keyword=keyword, status=status, sub_category=sub_category, limit=limit)
    total = db.search_count(keyword=keyword, status=status, sub_category=sub_category)
    print(f"\n📊 工单列表 - 共 {total} 条, 显示 {len(results)} 条")
    print("-" * 80)
    if results:
        for i, wo in enumerate(results, 1):
            print(f"  {i:<3d} {wo.get('order_no','N/A'):22s} {wo.get('problem','N/A'):16s} "
                  f"{wo.get('sub_category','N/A'):14s} {wo.get('priority','N/A'):12s} "
                  f"{wo.get('status','N/A'):6s} {wo.get('property_company','N/A'):12s}")
    print("-" * 80)
    db.close()


def _interactive_detail(order_no: str):
    db = get_db()
    wo = db.get_by_order_no(order_no)
    if wo: print_work_order(wo)
    else: print(f"❌ 未找到工单号: {order_no}")
    db.close()


def _interactive_test(service):
    print("\n🧪 完整测试模式")
    try:
        count_str = input("  测试数量 (默认5, 建议<=20): ").strip()
        test_count = int(count_str) if count_str else 5
    except (ValueError, KeyboardInterrupt):
        print("  取消测试"); return
    full_test_mode(service, min(test_count, 20))


def _interactive_benchmark(service):
    print("\n📐 模型准确度测试模式")
    try:
        count_str = input("  测试数量 (默认5, 建议<=30): ").strip()
        test_count = int(count_str) if count_str else 5
    except (ValueError, KeyboardInterrupt):
        print("  取消测试"); return
    benchmark_mode(service, min(test_count, 30))


# ============================================================
# Test modes
# ============================================================

def full_test_mode(service, test_count: int):
    test_cases = load_test_cases()
    addresses = load_testmap_addresses()
    if not test_cases or not addresses:
        print("❌ 测试数据不可用"); return
    actual = min(test_count, len(test_cases))
    selected = random.sample(test_cases, actual)
    sc = mc = ec = 0
    print(f"\n{'='*60}\n  🧪 完整测试 ({actual} 条)\n{'='*60}")
    for idx, case in enumerate(selected, 1):
        full = f"{case['repair_overview']}，地址是{random.choice(addresses)}"
        uid = f"full_test_{idx}"
        print(f"\n[{idx}/{actual}] {case['repair_overview'][:50]}...")
        print(f"  预期: {case['repair_type']} | {case['repair_project']}")
        try:
            result = service.handle_request(uid, full)
            if result['status'] == 'SUCCESS':
                sc += 1
                wo = result.get('work_order', {})
                print(f"  ✅ {wo.get('order_no','')} | {wo.get('sub_category','')} | {wo.get('problem','')}")
            elif result['status'] == 'MISS': mc += 1; print(f"  ⚠️ {result.get('message','')}")
            else: ec += 1; print(f"  ❌ {result.get('message','')}")
        except Exception as e: ec += 1; print(f"  🔴 {e}")
        service.input_processor.cancel_session(uid)
    print(f"\n{'='*60}\n  结果: ✅ {sc}  ⚠️ {mc}  ❌ {ec}  成功率: {(sc/actual*100) if actual else 0:.1f}%\n{'='*60}")


def benchmark_mode(service, test_count: int):
    test_cases = load_test_cases()
    addresses = load_testmap_addresses()
    scp, pk, kp, vs = load_classification_maps()
    if not test_cases or not addresses: print("❌ 测试数据不可用"); return
    actual = min(test_count, len(test_cases))
    selected = random.sample(test_cases, actual)
    passed = failed = skipped = pc = tc = ae = 0
    print(f"\n{'='*60}\n  📐 模型准确度测试 ({actual} 条)\n{'='*60}")
    for idx, case in enumerate(selected, 1):
        if case['repair_type'] not in vs: skipped += 1; continue
        full = f"{case['repair_overview']}，地址是{random.choice(addresses)}"
        uid = f"bench_{idx}_{int(time.time())}"
        print(f"\n[{idx}/{actual}] {case['repair_overview'][:50]}...")
        print(f"  预期: {case['repair_type']} | {case['repair_project']}")
        try:
            r = service.input_processor.process_user_input(uid, full)
            print(f"  输出: prechoice={r.get('prechoice_subcategories')} trigger={r.get('trigger_keyword')}")
            tp = True
            if r.get('prechoice_subcategories') and isinstance(r['prechoice_subcategories'], list) and case['repair_type'] in r['prechoice_subcategories']:
                pc += 1; print(f"  ✅ prechoice 匹配")
            else:
                tp = False; print(f"  ❌ prechoice 不匹配")
            if r.get('trigger_keyword'):
                tk = r['trigger_keyword']
                if tk == case['repair_project'] or tk in pk.get(case['repair_project'], []) or tk in case['repair_project'] or case['repair_project'] in tk:
                    tc += 1; print(f"  ✅ trigger 匹配")
            if r.get('address'): ae += 1
            if tp: passed += 1
            else: failed += 1
        except Exception as e: failed += 1; print(f"  🔴 {e}")
        service.input_processor.cancel_session(uid)
    tv = actual - skipped
    print(f"\n{'='*60}\n  结果: prechoice={pc}/{tv}={pc/tv*100 if tv else 0:.1f}%  trigger={tc}/{tv}={tc/tv*100 if tv else 0:.1f}%  通过={passed}\n{'='*60}")


# ============================================================
# Interactive mode
# ============================================================

def interactive_mode(service, default_user_id: str = "user001"):
    current_user = default_user_id
    accumulated_input = ""
    print_banner()
    while True:
        try:
            prompt = f"[{current_user}] 请补充信息 > " if accumulated_input else f"[{current_user}] 请输入报修信息 > "
            user_input = input(prompt).strip()
            if not user_input: continue

            lower = user_input.lower()

            # Exit
            if lower in ('quit', 'exit', 'q'):
                print("感谢使用，再见！"); break

            # Cancel
            if lower == 'cancel':
                service.input_processor.cancel_session(current_user)
                accumulated_input = ""; print("✅ 当前报修已取消"); continue

            # Status
            if lower == 'status':
                s = service.input_processor.check_session_status(current_user)
                if s.get("has_session"):
                    print(f"📋 状态: {s['step']} | {s['message']}")
                    if s.get('problem'): print(f"   问题: {s['problem']}")
                    if s.get('address'): print(f"   地址: {s['address']}")
                else: print("📋 没有活跃的报修会话")
                continue

            # List
            if lower == 'list' or lower.startswith('list '):
                _interactive_list(user_input); continue

            # Detail
            if lower.startswith('detail '):
                _interactive_detail(user_input.split(' ', 1)[1].strip()); continue

            # Switch user
            if lower.startswith('switch '):
                current_user = user_input.split(' ', 1)[1].strip()
                accumulated_input = ""; print(f"🔄 已切换到: {current_user}"); continue

            # Test
            if lower == 'test': _interactive_test(service); continue

            # Benchmark
            if lower == 'benchmark': _interactive_benchmark(service); continue

            # ---- Feedback commands ----
            if lower.startswith('feedback-submit'):
                _feedback_submit(user_input); continue

            if lower == 'feedback-list' or lower == 'feedback-list ':
                _feedback_list(); continue

            if lower.startswith('feedback-review'):
                _feedback_review(user_input); continue

            # ---- Address commands ----
            if lower == 'addr-list' or lower == 'addr-list ':
                _addr_list(); continue

            if lower.startswith('addr-add'):
                _addr_add(user_input); continue

            if lower.startswith('addr-modify'):
                _addr_modify(user_input); continue

            if lower.startswith('addr-delete'):
                _addr_delete(user_input); continue

            # Process repair input
            full_input = accumulated_input + " " + user_input if accumulated_input else user_input
            print("⏳ 正在处理您的报修信息...\n")
            result = service.handle_request(current_user, full_input)

            if result['status'] == 'SUCCESS':
                wo = result.get('work_order')
                if wo: print_work_order(wo)
                wi = result.get('details', {}).get('work_order', {})
                if wi:
                    icon = "✅" if wi.get('db_save_status') == 'SUCCESS' else "❌"
                    print(f"  💾 数据库: {icon} {wi.get('db_save_message', '')}")
                print(f"✅ {result['message']}")
                accumulated_input = ""; print("-" * 60)
            elif result['status'] == 'MISS':
                print(f"⚠️  {result['message']}")
                print("💡 请补充缺失信息后继续 (输入 cancel 取消)")
                content = result.get('details', {}).get('input_processor', {}).get('content', '')
                accumulated_input = content if content and content != full_input else full_input
                print("-" * 60)
            else:
                print(f"🔴 {result['message']}")
                accumulated_input = ""; print("-" * 60)
        except KeyboardInterrupt:
            print("\n\n程序已中断"); break
        except Exception as e:
            print(f"\n🔴 系统异常: {e}")
            accumulated_input = ""; print("-" * 60)


# ============================================================
# JSON batch mode
# ============================================================

def json_batch_mode(service, json_file_path: str, output_file: str = None):
    if not os.path.exists(json_file_path):
        print(f"❌ 文件不存在: {json_file_path}"); return
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, list): records = data
    elif isinstance(data, dict): records = data.get('records', [])
    else: records = [data]
    if not records: print("❌ 无数据"); return
    print(f"📊 共 {len(records)} 条记录\n")
    sc = mc = ec = 0
    for i, record in enumerate(records, 1):
        uid = f"batch_{i:03d}"
        text = record if isinstance(record, str) else record.get('input', record.get('user_input', ''))
        try:
            r = service.handle_request(uid, text)
            if r['status'] == 'SUCCESS': sc += 1
            elif r['status'] == 'MISS': mc += 1
            else: ec += 1
            print(f"[{i}/{len(records)}] {r['status']}")
        except Exception as e: ec += 1; print(f"[{i}/{len(records)}] ERROR: {e}")
    print(f"\n✅ {sc}  ⚠️ {mc}  ❌ {ec}")


# ============================================================
# Main entry
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="智能工单系统")
    parser.add_argument('--user', '-u', type=str, default='user001')
    parser.add_argument('--json', '-j', type=str, default=None)
    parser.add_argument('--output', '-o', type=str, default=None)
    parser.add_argument('--rules-dir', type=str, default='data/rules')
    parser.add_argument('--list', action='store_true', default=False)
    parser.add_argument('--detail', type=str, default=None)
    parser.add_argument('--order_no', type=str, default=None)
    parser.add_argument('--sub_category', type=str, default=None)
    parser.add_argument('--property_company', type=str, default=None)
    parser.add_argument('--required_cert', type=str, default=None)
    parser.add_argument('--target_dept_semantic', type=str, default=None)
    parser.add_argument('--priority', type=str, default=None)
    parser.add_argument('--status', type=str, default=None)
    parser.add_argument('--keyword', type=str, default=None)
    parser.add_argument('--start_time', type=str, default=None)
    parser.add_argument('--end_time', type=str, default=None)
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--page', type=int, default=None)
    parser.add_argument('--test', type=int, default=None, help='完整测试条数')
    parser.add_argument('--benchmark', type=int, default=None, help='准确度测试条数')
    args = parser.parse_args()

    if args.list or args.detail:
        db_query_mode(args)
        return

    if not os.environ.get('ds_apikey'):
        print("⚠️  环境变量 ds_apikey 未设置")

    from service import Service
    try:
        print("🔄 正在初始化智能工单系统...")
        service = Service(rules_dir=args.rules_dir)
        print("✅ 系统初始化完成")
    except FileNotFoundError as e:
        print(f"❌ 初始化失败: {e}"); sys.exit(1)
    except Exception as e:
        print(f"❌ 初始化失败: {e}"); sys.exit(1)

    if args.test:
        full_test_mode(service, args.test)
    elif args.benchmark:
        benchmark_mode(service, args.benchmark)
    elif args.json:
        json_batch_mode(service, args.json, args.output)
    else:
        interactive_mode(service, args.user)


if __name__ == "__main__":
    main()