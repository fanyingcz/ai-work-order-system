"""
===========================
JSON-to-DB Migration Tool
===========================
Cleanly imports rules JSON files into MySQL, skipping existing records.

Usage: python tools/migrate_json_to_db.py [--force]

--force : Purge all rule tables first, then re-import clean
"""

import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_db


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', help='Purge all rule tables before import')
    args = parser.parse_args()

    db = get_db()
    conn = db._get_connection()

    if args.force:
        print("[WARN] --force: purging all rule tables...")
        with conn.cursor() as c:
            c.execute("SET FOREIGN_KEY_CHECKS=0")
            for t in ['category_trigger_keywords', 'category_trigger_locations',
                       'address_mappings', 'categories', 'subcategories']:
                try:
                    c.execute(f"TRUNCATE TABLE {t}")
                    print(f"  TRUNCATED {t}")
                except Exception as e:
                    try:
                        c.execute(f"DELETE FROM {t}")
                        print(f"  DELETED from {t}")
                    except Exception as e2:
                        print(f"  SKIP {t}: {e2}")
            c.execute("SET FOREIGN_KEY_CHECKS=1")

    # Step 1: Remove unique index from address_mappings if exists (so INSERT works)
    print("\n[1] Removing unique index from address_mappings (if exists)...")
    with conn.cursor() as c:
        try:
            c.execute("ALTER TABLE address_mappings DROP INDEX uk_addr_unique")
            print("  Dropped uk_addr_unique index")
        except Exception as e:
            print(f"  (no index to drop, OK): {e}")

    # Step 2: Delete duplicate rows from address_mappings (keep min id)
    print("\n[2] Cleaning address_mappings duplicates...")
    with conn.cursor() as c:
        c.execute("""
            DELETE t1 FROM address_mappings t1
            INNER JOIN address_mappings t2 ON
                t1.id > t2.id
                AND t1.community = t2.community
                AND t1.street = t2.street
                AND t1.property_company = t2.property_company
                AND t1.maintenance_unit = t2.maintenance_unit
        """)
        print(f"  Deleted {c.rowcount} duplicate rows")

    # Step 3: Re-add unique index to prevent future duplicates
    print("\n[3] Adding unique constraint to address_mappings...")
    with conn.cursor() as c:
        try:
            c.execute("""
                ALTER TABLE address_mappings
                ADD UNIQUE INDEX uk_addr_unique (community, street, property_company, maintenance_unit)
            """)
            print("  Unique index added")
        except Exception as e:
            if 'Duplicate' in str(e) or 'already exists' in str(e):
                print(f"  Index already exists")
            else:
                print(f"  Warning: {e}")

    # Step 4: Import JSON data using INSERT IGNORE (skip existing)
    print("\n[4] Importing JSON data with INSERT IGNORE (skip existing)...")
    import json

    # Import subcategories (ON DUPLICATE KEY UPDATE)
    sub_file = os.path.join("data", "rules", "subcategories.json")
    if os.path.exists(sub_file):
        with open(sub_file, 'r', encoding='utf-8') as f:
            sub_data = json.load(f)
        sub_count = 0
        with conn.cursor() as c:
            for item in sub_data:
                c.execute(
                    "INSERT INTO subcategories (sub_category, description) VALUES (%s, %s) "
                    "ON DUPLICATE KEY UPDATE description=VALUES(description)",
                    (item.get('subCategory', ''), item.get('description', '')))
                sub_count += 1
        print(f"  subcategories: {sub_count} rows")

    # Import categories (ON DUPLICATE KEY UPDATE)
    cat_file = os.path.join("data", "rules", "category.json")
    if os.path.exists(cat_file):
        with open(cat_file, 'r', encoding='utf-8') as f:
            cat_data = json.load(f)
        cat_count = 0
        kw_count = 0
        loc_count = 0
        with conn.cursor() as c:
            for item in cat_data:
                rule_id = item.get('id', 0)
                # required_cert 在 JSON 中为 List[str]，需转为字符串（用'及'分隔）
                required_cert_raw = item.get('required_cert', '')
                if isinstance(required_cert_raw, list):
                    required_cert_str = '及'.join(required_cert_raw)
                else:
                    required_cert_str = str(required_cert_raw) if required_cert_raw else ''
                c.execute("""
                    INSERT INTO categories (rule_id, category, sub_category, problem,
                        priority, required_cert, target_dept_semantic, description)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        category=VALUES(category), sub_category=VALUES(sub_category),
                        problem=VALUES(problem), priority=VALUES(priority),
                        required_cert=VALUES(required_cert),
                        target_dept_semantic=VALUES(target_dept_semantic),
                        description=VALUES(description)
                """, (rule_id, item.get('category', ''), item.get('subCategory', ''),
                      item.get('problem', ''), item.get('priority', ''),
                      required_cert_str, item.get('target_dept_semantic', ''),
                      item.get('description', '')))
                cat_id = c.lastrowid
                if cat_id == 0:
                    c.execute("SELECT id FROM categories WHERE rule_id=%s", (rule_id,))
                    row = c.fetchone()
                    if row:
                        cat_id = row['id']
                cat_count += 1

                # Delete old keywords/locations and re-insert
                c.execute("DELETE FROM category_trigger_keywords WHERE category_id=%s", (cat_id,))
                c.execute("DELETE FROM category_trigger_locations WHERE category_id=%s", (cat_id,))
                for kw in item.get('trigger_keywords', []):
                    c.execute("INSERT INTO category_trigger_keywords (category_id, keyword) VALUES (%s, %s)",
                              (cat_id, kw))
                    kw_count += 1
                for loc in item.get('trigger_location', []):
                    c.execute("INSERT INTO category_trigger_locations (category_id, location) VALUES (%s, %s)",
                              (cat_id, loc))
                    loc_count += 1
        print(f"  categories: {cat_count}, keywords: {kw_count}, locations: {loc_count}")

    # Import address_mappings (INSERT IGNORE to skip duplicates)
    addr_file = os.path.join("data", "rules", "address_mapping.json")
    if os.path.exists(addr_file):
        with open(addr_file, 'r', encoding='utf-8') as f:
            addr_data = json.load(f)
        am_count = 0
        with conn.cursor() as c:
            for item in addr_data:
                c.execute("""
                    INSERT IGNORE INTO address_mappings
                        (community, street, property_company, maintenance_unit, district, city)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (item.get('community', ''), item.get('street', ''),
                      item.get('property_company', ''), item.get('maintenance_unit', ''),
                      item.get('district', ''), item.get('city', '')))
                am_count += 1
        print(f"  address_mappings: {am_count} rows attempted")

    # Step 5: Final counts
    print("\n[5] Final table counts:")
    with conn.cursor() as c:
        for t in ['subcategories', 'categories', 'category_trigger_keywords',
                   'category_trigger_locations', 'address_mappings']:
            c.execute(f"SELECT COUNT(*) as cnt FROM {t}")
            print(f"  {t}: {c.fetchone()['cnt']}")

    # Verify address_mappings
    with conn.cursor() as c:
        c.execute("SELECT COUNT(*) as cnt FROM address_mappings")
        am_cnt = c.fetchone()['cnt']
        if am_cnt < 35:
            print(f"\n[WARN] address_mappings only has {am_cnt} rows (expected ~40)")
            print("  This is likely due to the unique index blocking INSERT IGNORE for truly duplicate records.")
            print("  However, if the original JSON had 40 unique records, they should all be present.")

    print("\n=== Migration complete ===")


if __name__ == "__main__":
    main()