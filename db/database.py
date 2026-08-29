"""
数据库模块 - MySQL 连接管理与 CRUD 操作

【文件职责】
1. 管理 MySQL 数据库连接（连接池）
2. 自动建表（work_orders 表、规则表、地址映射表）
3. 提供工单的增删改查（CRUD）操作
4. 支持多种筛选查询：工单号、sub_category、property_company、required_cert、target_dept_semantic 等
5. 提供规则数据查询（替代原有的 JSON 文件读取）

【数据库信息】
- 数据库: AI_Work_Order
- 编码: utf8mb4

【表结构说明】
- work_orders: 工单信息主表
- subcategories: 报修子类别定义
- categories: 维修分类规则
- category_trigger_keywords: 分类触发关键词（1:N）
- category_trigger_locations: 分类触发位置（1:N）
- address_mappings: 地址到物业/维修单位的映射
"""

import json
import os
import pymysql
from pymysql.cursors import DictCursor
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager


class WorkOrderDB:
    """
    工单数据库管理类

    负责 MySQL 数据库连接管理、建表和工单 CRUD 操作，
    同时管理规则表和地址映射表。

    Attributes:
        host (str): 数据库主机地址
        port (int): 数据库端口
        user (str): 数据库用户名
        password (str): 数据库密码
        database (str): 数据库名称
        charset (str): 字符集
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        """单例模式，确保全局只有一个数据库连接管理器"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, host: str = 'localhost', port: int = 3306,
                 user: str = 'root', password: str = 'Qazplm147369#',
                 database: str = 'AI_Work_Order', charset: str = 'utf8mb4'):
        if self._initialized:
            return
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.charset = charset
        self._connection = None
        self._initialized = True

        # 自动创建数据库和表，并迁移已有表结构
        self._ensure_database()
        self._create_table_if_not_exists()
        self._migrate_work_orders_table()
        self._create_rules_tables_if_not_exists()

    def _get_raw_connection(self):
        """获取原始数据库连接（用于创建数据库等操作）"""
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            charset=self.charset,
            cursorclass=DictCursor
        )

    def _get_connection(self):
        """获取到目标数据库的连接"""
        if self._connection is None or not self._connection.open:
            self._connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset=self.charset,
                cursorclass=DictCursor,
                autocommit=True
            )
        return self._connection

    def _ensure_database(self):
        """确保数据库 AI_Work_Order 存在，不存在则创建"""
        try:
            conn = self._get_raw_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{self.database}` "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            conn.close()
        except Exception as e:
            print(f"[WorkOrderDB] 创建数据库失败: {e}")
            raise

    def _create_table_if_not_exists(self):
        """确保 work_orders 表存在，不存在则创建"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS `work_orders` (
            `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
            `order_no` VARCHAR(30) NOT NULL COMMENT '维修单号',
            `accept_time` DATETIME NOT NULL COMMENT '受理时间',
            `user_input` TEXT COMMENT '报修概述',
            `sub_category` VARCHAR(100) COMMENT '报修类型',
            `problem` VARCHAR(200) COMMENT '报修项目',
            `property_company` VARCHAR(100) COMMENT '物业公司',
            `maintenance_unit` VARCHAR(100) COMMENT '维修单位',
            `priority` VARCHAR(50) COMMENT '优先级',
            `required_cert` VARCHAR(200) COMMENT '所需资质证书',
            `target_dept_semantic` VARCHAR(100) COMMENT '目标维修部门',
            `status` VARCHAR(30) DEFAULT 'PENDING' COMMENT '工单状态',
            `address` VARCHAR(500) COMMENT '报修地址',
            `reporter_name` VARCHAR(100) COMMENT '报修人姓名',
            `reporter_phone` VARCHAR(30) COMMENT '报修人联系电话',
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
            `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
            UNIQUE KEY `uk_order_no` (`order_no`),
            INDEX `idx_sub_category` (`sub_category`),
            INDEX `idx_property_company` (`property_company`),
            INDEX `idx_required_cert` (`required_cert`),
            INDEX `idx_target_dept_semantic` (`target_dept_semantic`),
            INDEX `idx_status` (`status`),
            INDEX `idx_accept_time` (`accept_time`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='工单信息表';
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(create_table_sql)
        except Exception as e:
            print(f"[WorkOrderDB] 创建表失败: {e}")
            raise

    def _migrate_work_orders_table(self):
        """对已存在但缺少新列的 work_orders 表自动追加列（向后兼容）"""
        migrations = [
            ("reporter_name", "VARCHAR(100) COMMENT '报修人姓名'"),
            ("reporter_phone", "VARCHAR(30) COMMENT '报修人联系电话'"),
        ]
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                # 查询现有列名
                cursor.execute("SHOW COLUMNS FROM `work_orders`")
                existing_cols = {row['Field'] for row in cursor.fetchall()}
                for col_name, col_def in migrations:
                    if col_name not in existing_cols:
                        cursor.execute(f"ALTER TABLE `work_orders` ADD COLUMN `{col_name}` {col_def}")
                        print(f"[WorkOrderDB] 迁移: 添加列 {col_name} 到 work_orders 表")
        except Exception as e:
            print(f"[WorkOrderDB] 迁移 work_orders 表失败 (可忽略): {e}")

    # ==================== 规则表 ====================

    def _create_rules_tables_if_not_exists(self):
        """确保规则相关表存在，不存在则创建"""
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                # subcategories 表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS `subcategories` (
                        `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
                        `sub_category` VARCHAR(50) NOT NULL COMMENT '子类别名称',
                        `description` TEXT COMMENT '子类别描述',
                        `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
                        `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
                        UNIQUE KEY `uk_sub_category` (`sub_category`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报修子类别定义表';
                """)

                # categories 表（主表）
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS `categories` (
                        `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
                        `rule_id` INT NOT NULL COMMENT '原始规则ID',
                        `category` VARCHAR(50) NOT NULL COMMENT '维修类别（应急维修/日常维修）',
                        `sub_category` VARCHAR(50) NOT NULL COMMENT '维修子类别',
                        `problem` VARCHAR(200) NOT NULL COMMENT '问题描述',
                        `priority` VARCHAR(50) COMMENT '优先级',
                        `required_cert` VARCHAR(200) COMMENT '所需资质证书',
                        `target_dept_semantic` VARCHAR(100) COMMENT '目标维修部门',
                        `description` TEXT COMMENT '详细描述',
                        `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
                        `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
                        UNIQUE KEY `uk_rule_id` (`rule_id`),
                        INDEX `idx_sub_category` (`sub_category`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='维修分类规则表';
                """)

                # category_trigger_keywords 表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS `category_trigger_keywords` (
                        `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
                        `category_id` INT NOT NULL COMMENT '关联的 categories.id',
                        `keyword` VARCHAR(200) NOT NULL COMMENT '触发关键词',
                        `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
                        INDEX `idx_category_id` (`category_id`),
                        CONSTRAINT `fk_keywords_category` FOREIGN KEY (`category_id`) 
                            REFERENCES `categories`(`id`) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='分类触发关键词表';
                """)

                # category_trigger_locations 表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS `category_trigger_locations` (
                        `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
                        `category_id` INT NOT NULL COMMENT '关联的 categories.id',
                        `location` VARCHAR(200) NOT NULL COMMENT '触发位置',
                        `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
                        INDEX `idx_category_id` (`category_id`),
                        CONSTRAINT `fk_locations_category` FOREIGN KEY (`category_id`) 
                            REFERENCES `categories`(`id`) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='分类触发位置表';
                """)

                # address_mappings 表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS `address_mappings` (
                        `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
                        `community` VARCHAR(100) DEFAULT '' COMMENT '小区名称',
                        `street` VARCHAR(100) DEFAULT '' COMMENT '街道名称',
                        `property_company` VARCHAR(200) NOT NULL COMMENT '物业公司',
                        `maintenance_unit` VARCHAR(200) DEFAULT '' COMMENT '维修单位',
                        `district` VARCHAR(50) DEFAULT '' COMMENT '区县',
                        `city` VARCHAR(50) DEFAULT '' COMMENT '城市',
                        `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
                        `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
                        INDEX `idx_community` (`community`),
                        INDEX `idx_street` (`street`),
                        INDEX `idx_street_community` (`street`, `community`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='地址映射表';
                """)
        except Exception as e:
            print(f"[WorkOrderDB] 创建规则表失败: {e}")
            raise

    # ==================== 规则数据导入 ====================

    def init_rules_from_json(self, rules_dir: str = "data/rules") -> Dict[str, Any]:
        """
        从 JSON 文件导入规则数据到数据库

        导入数据源：
        - subcategories.json → subcategories 表
        - category.json → categories + category_trigger_keywords + category_trigger_locations 表
        - address_mapping.json → address_mappings 表

        Args:
            rules_dir: JSON 文件所在目录，默认 "data/rules"

        Returns:
            Dict: 导入结果统计
        """
        result = {
            'subcategories': 0,
            'categories': 0,
            'keywords': 0,
            'locations': 0,
            'address_mappings': 0,
            'errors': []
        }

        try:
            # 1. 导入 subcategories
            sub_file = os.path.join(rules_dir, 'subcategories.json')
            if os.path.exists(sub_file):
                with open(sub_file, 'r', encoding='utf-8') as f:
                    sub_data = json.load(f)
                result['subcategories'] = self._import_subcategories(sub_data)

            # 2. 导入 categories（含 keywords 和 locations）
            cat_file = os.path.join(rules_dir, 'category.json')
            if os.path.exists(cat_file):
                with open(cat_file, 'r', encoding='utf-8') as f:
                    cat_data = json.load(f)
                counts = self._import_categories(cat_data)
                result['categories'] = counts['categories']
                result['keywords'] = counts['keywords']
                result['locations'] = counts['locations']

            # 3. 导入 address_mappings
            addr_file = os.path.join(rules_dir, 'address_mapping.json')
            if os.path.exists(addr_file):
                with open(addr_file, 'r', encoding='utf-8') as f:
                    addr_data = json.load(f)
                result['address_mappings'] = self._import_address_mappings(addr_data)

            print(f"[WorkOrderDB] 规则数据导入完成: {result}")
        except Exception as e:
            result['errors'].append(str(e))
            print(f"[WorkOrderDB] 规则数据导入失败: {e}")

        return result

    def _import_subcategories(self, data: List[dict]) -> int:
        """导入 subcategories 数据"""
        conn = self._get_connection()
        count = 0
        sql = """
        INSERT INTO `subcategories` (`sub_category`, `description`)
        VALUES (%(sub_category)s, %(description)s)
        ON DUPLICATE KEY UPDATE `description` = VALUES(`description`)
        """
        try:
            with conn.cursor() as cursor:
                for item in data:
                    cursor.execute(sql, {
                        'sub_category': item.get('subCategory', ''),
                        'description': item.get('description', '')
                    })
                    count += 1
        except Exception as e:
            print(f"[WorkOrderDB] 导入 subcategories 失败: {e}")
        return count

    def _import_categories(self, data: List[dict]) -> Dict[str, int]:
        """导入 categories 数据（含 keywords 和 locations）"""
        conn = self._get_connection()
        counts = {'categories': 0, 'keywords': 0, 'locations': 0}

        cat_sql = """
        INSERT INTO `categories` (`rule_id`, `category`, `sub_category`, `problem`, 
            `priority`, `required_cert`, `target_dept_semantic`, `description`)
        VALUES (%(rule_id)s, %(category)s, %(sub_category)s, %(problem)s,
            %(priority)s, %(required_cert)s, %(target_dept_semantic)s, %(description)s)
        ON DUPLICATE KEY UPDATE 
            `category` = VALUES(`category`),
            `sub_category` = VALUES(`sub_category`),
            `problem` = VALUES(`problem`),
            `priority` = VALUES(`priority`),
            `required_cert` = VALUES(`required_cert`),
            `target_dept_semantic` = VALUES(`target_dept_semantic`),
            `description` = VALUES(`description`)
        """
        kw_sql = """
        INSERT INTO `category_trigger_keywords` (`category_id`, `keyword`)
        VALUES (%(category_id)s, %(keyword)s)
        """
        loc_sql = """
        INSERT INTO `category_trigger_locations` (`category_id`, `location`)
        VALUES (%(category_id)s, %(location)s)
        """

        try:
            with conn.cursor() as cursor:
                for item in data:
                    rule_id = item.get('id', 0)
                    # required_cert 在 JSON 中为 List[str]，需转为字符串（用'及'分隔）
                    required_cert_raw = item.get('required_cert', '')
                    if isinstance(required_cert_raw, list):
                        required_cert_str = '及'.join(required_cert_raw)
                    else:
                        required_cert_str = str(required_cert_raw) if required_cert_raw else ''
                    params = {
                        'rule_id': rule_id,
                        'category': item.get('category', ''),
                        'sub_category': item.get('subCategory', ''),
                        'problem': item.get('problem', ''),
                        'priority': item.get('priority', ''),
                        'required_cert': required_cert_str,
                        'target_dept_semantic': item.get('target_dept_semantic', ''),
                        'description': item.get('description', '')
                    }
                    cursor.execute(cat_sql, params)
                    category_id = cursor.lastrowid
                    if category_id == 0:
                        # ON DUPLICATE KEY UPDATE 返回0，需要重新查询
                        cursor.execute(
                            "SELECT `id` FROM `categories` WHERE `rule_id` = %s", (rule_id,))
                        row = cursor.fetchone()
                        if row:
                            category_id = row['id']

                    counts['categories'] += 1

                    # 删除旧的 keywords 和 locations，重新插入
                    cursor.execute(
                        "DELETE FROM `category_trigger_keywords` WHERE `category_id` = %s", (category_id,))
                    cursor.execute(
                        "DELETE FROM `category_trigger_locations` WHERE `category_id` = %s", (category_id,))

                    # 插入 keywords
                    for kw in item.get('trigger_keywords', []):
                        cursor.execute(kw_sql, {
                            'category_id': category_id,
                            'keyword': kw
                        })
                        counts['keywords'] += 1

                    # 插入 locations
                    for loc in item.get('trigger_location', []):
                        cursor.execute(loc_sql, {
                            'category_id': category_id,
                            'location': loc
                        })
                        counts['locations'] += 1
        except Exception as e:
            print(f"[WorkOrderDB] 导入 categories 失败: {e}")

        return counts

    def _import_address_mappings(self, data: List[dict]) -> int:
        """导入 address_mappings 数据"""
        conn = self._get_connection()
        count = 0
        sql = """
        INSERT INTO `address_mappings` (`community`, `street`, `property_company`, 
            `maintenance_unit`, `district`, `city`)
        VALUES (%(community)s, %(street)s, %(property_company)s, 
            %(maintenance_unit)s, %(district)s, %(city)s)
        """
        try:
            with conn.cursor() as cursor:
                for item in data:
                    cursor.execute(sql, {
                        'community': item.get('community', ''),
                        'street': item.get('street', ''),
                        'property_company': item.get('property_company', ''),
                        'maintenance_unit': item.get('maintenance_unit', ''),
                        'district': item.get('district', ''),
                        'city': item.get('city', '')
                    })
                    count += 1
        except Exception as e:
            print(f"[WorkOrderDB] 导入 address_mappings 失败: {e}")
        return count

    # ==================== 规则数据查询 ====================

    def get_all_subcategories(self) -> List[Dict[str, Any]]:
        """
        获取所有 subCategory 数据

        Returns:
            List[Dict]: 每个元素包含 id, sub_category, description
        """
        sql = "SELECT `id`, `sub_category`, `description` FROM `subcategories` ORDER BY `id`"
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql)
                return cursor.fetchall()
        except Exception as e:
            print(f"[WorkOrderDB] 查询 subcategories 失败: {e}")
            return []

    def get_all_categories(self) -> List[Dict[str, Any]]:
        """
        获取所有分类规则（含 keywords 和 locations）

        Returns:
            List[Dict]: 每个元素包含完整规则字段（与原 category.json 格式一致）
        """
        # 先查询所有 categories
        cat_sql = "SELECT * FROM `categories` ORDER BY `rule_id`"
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(cat_sql)
                categories = cursor.fetchall()

                # 为每个 category 填充 keywords 和 locations
                for cat in categories:
                    cat_id = cat['id']

                    # 查询 keywords
                    cursor.execute(
                        "SELECT `keyword` FROM `category_trigger_keywords` WHERE `category_id` = %s",
                        (cat_id,))
                    cat['trigger_keywords'] = [row['keyword']
                                               for row in cursor.fetchall()]

                    # 查询 locations
                    cursor.execute(
                        "SELECT `location` FROM `category_trigger_locations` WHERE `category_id` = %s",
                        (cat_id,))
                    cat['trigger_location'] = [row['location']
                                               for row in cursor.fetchall()]

                return categories
        except Exception as e:
            print(f"[WorkOrderDB] 查询 categories 失败: {e}")
            return []

    def get_trigger_data_by_subcategories(self, subcategories: List[str]) -> Dict[str, dict]:
        """
        根据 subCategory 列表获取对应的 trigger_keywords 和 trigger_locations

        Args:
            subcategories: subCategory 名称列表

        Returns:
            dict: {
                "subCategory1": {
                    "trigger_keywords": [...],
                    "trigger_locations": [...]
                },
                ...
            }
        """
        if not subcategories:
            return {}

        result = {}
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                # 使用参数化查询获取匹配的 category IDs
                placeholders = ','.join(['%s'] * len(subcategories))
                cat_sql = f"SELECT `id`, `sub_category` FROM `categories` WHERE `sub_category` IN ({placeholders})"
                cursor.execute(cat_sql, subcategories)
                matched_cats = cursor.fetchall()

                for cat in matched_cats:
                    sub = cat['sub_category']
                    cat_id = cat['id']

                    if sub not in result:
                        result[sub] = {
                            'trigger_keywords': [],
                            'trigger_locations': []
                        }

                    # 查询 keywords
                    cursor.execute(
                        "SELECT `keyword` FROM `category_trigger_keywords` WHERE `category_id` = %s",
                        (cat_id,))
                    for row in cursor.fetchall():
                        result[sub]['trigger_keywords'].append(row['keyword'])

                    # 查询 locations
                    cursor.execute(
                        "SELECT `location` FROM `category_trigger_locations` WHERE `category_id` = %s",
                        (cat_id,))
                    for row in cursor.fetchall():
                        result[sub]['trigger_locations'].append(row['location'])

        except Exception as e:
            print(f"[WorkOrderDB] 查询 trigger_data 失败: {e}")

        return result

    def get_problem_subcategory_map(self) -> Dict[str, str]:
        """
        获取 problem 到 subCategory 的映射

        Returns:
            Dict[str, str]: problem → subCategory 映射
        """
        sql = "SELECT `problem`, `sub_category` FROM `categories`"
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql)
                result = {}
                for row in cursor.fetchall():
                    problem = row.get('problem', '')
                    if problem:
                        result[problem] = row.get('sub_category', '')
                return result
        except Exception as e:
            print(f"[WorkOrderDB] 查询 problem_subcategory_map 失败: {e}")
            return {}

    def get_all_address_mappings(self) -> List[Dict[str, Any]]:
        """
        获取所有地址映射数据

        Returns:
            List[Dict]: 地址映射列表
        """
        sql = "SELECT * FROM `address_mappings` ORDER BY `id`"
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql)
                return cursor.fetchall()
        except Exception as e:
            print(f"[WorkOrderDB] 查询 address_mappings 失败: {e}")
            return []

    def get_address_mapping_by_community(self, community: str) -> Optional[Dict[str, Any]]:
        """
        按小区名称精确查询地址映射

        Args:
            community: 小区名称

        Returns:
            Optional[Dict]: 匹配的地址映射，未找到返回 None
        """
        sql = "SELECT * FROM `address_mappings` WHERE `community` = %s LIMIT 1"
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql, (community,))
                return cursor.fetchone()
        except Exception as e:
            print(f"[WorkOrderDB] 按小区查询地址映射失败: {e}")
            return None

    def get_address_mapping_by_street(self, street: str) -> Optional[Dict[str, Any]]:
        """
        按街道名称精确查询地址映射

        Args:
            street: 街道名称

        Returns:
            Optional[Dict]: 匹配的地址映射，未找到返回 None
        """
        sql = "SELECT * FROM `address_mappings` WHERE `street` = %s LIMIT 1"
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql, (street,))
                return cursor.fetchone()
        except Exception as e:
            print(f"[WorkOrderDB] 按街道查询地址映射失败: {e}")
            return None

    def get_address_mapping_by_street_community(self, street: str, community: str) -> Optional[Dict[str, Any]]:
        """
        按街道+小区精确查询地址映射

        Args:
            street: 街道名称
            community: 小区名称

        Returns:
            Optional[Dict]: 匹配的地址映射，未找到返回 None
        """
        sql = "SELECT * FROM `address_mappings` WHERE `street` = %s AND `community` = %s LIMIT 1"
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql, (street, community))
                return cursor.fetchone()
        except Exception as e:
            print(f"[WorkOrderDB] 按街道+小区查询地址映射失败: {e}")
            return None

    def fuzzy_community_match(self, community: str, district: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        小区模糊匹配：查找社区名包含或被包含于输入社区名的记录

        Args:
            community: 输入的小区名称
            district: 可选区县过滤

        Returns:
            List[Dict]: 匹配的地址映射列表
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                sql = "SELECT * FROM `address_mappings` WHERE `community` != '' AND (INSTR(%s, `community`) > 0 OR INSTR(`community`, %s) > 0)"
                params = [community, community]
                if district:
                    sql += " AND (INSTR(%s, `district`) > 0 OR INSTR(`district`, %s) > 0)"
                    params.extend([district, district])
                cursor.execute(sql, params)
                return cursor.fetchall()
        except Exception as e:
            print(f"[WorkOrderDB] 小区模糊匹配失败: {e}")
            return []

    def fuzzy_street_match(self, street: str, district: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        街道模糊匹配：查找街道名包含或被包含于输入街道名的记录

        Args:
            street: 输入的街道名称
            district: 可选区县过滤

        Returns:
            List[Dict]: 匹配的地址映射列表
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                sql = "SELECT * FROM `address_mappings` WHERE `street` != '' AND (INSTR(%s, `street`) > 0 OR INSTR(`street`, %s) > 0)"
                params = [street, street]
                if district:
                    sql += " AND (INSTR(%s, `district`) > 0 OR INSTR(`district`, %s) > 0)"
                    params.extend([district, district])
                cursor.execute(sql, params)
                return cursor.fetchall()
        except Exception as e:
            print(f"[WorkOrderDB] 街道模糊匹配失败: {e}")
            return []

    def fuzzy_street_community_match(self, street: str, community: str, district: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        街道+小区模糊匹配

        Args:
            street: 输入的街道名称
            community: 输入的小区名称
            district: 可选区县过滤

        Returns:
            List[Dict]: 匹配的地址映射列表
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                sql = (
                    "SELECT * FROM `address_mappings` "
                    "WHERE `street` != '' AND `community` != '' "
                    "AND (INSTR(%s, `street`) > 0 OR INSTR(`street`, %s) > 0) "
                    "AND (INSTR(%s, `community`) > 0 OR INSTR(`community`, %s) > 0)"
                )
                params = [street, street, community, community]
                if district:
                    sql += " AND (INSTR(%s, `district`) > 0 OR INSTR(`district`, %s) > 0)"
                    params.extend([district, district])
                cursor.execute(sql, params)
                return cursor.fetchall()
        except Exception as e:
            print(f"[WorkOrderDB] 街道+小区模糊匹配失败: {e}")
            return []

    # ==================== 规则表 CRUD 操作 ====================

    # --- subcategories CRUD ---

    def add_subcategory(self, sub_category: str, description: str) -> int:
        """新增子类别"""
        sql = "INSERT INTO `subcategories` (`sub_category`, `description`) VALUES (%s, %s)"
        conn = self._get_connection()
        with conn.cursor() as cursor:
            cursor.execute(sql, (sub_category, description))
            return cursor.lastrowid

    def update_subcategory(self, record_id: int, sub_category: str, description: str) -> int:
        """更新子类别"""
        sql = "UPDATE `subcategories` SET `sub_category`=%s, `description`=%s WHERE `id`=%s"
        conn = self._get_connection()
        with conn.cursor() as cursor:
            return cursor.execute(sql, (sub_category, description, record_id))

    def delete_subcategory(self, record_id: int) -> int:
        """删除子类别"""
        sql = "DELETE FROM `subcategories` WHERE `id`=%s"
        conn = self._get_connection()
        with conn.cursor() as cursor:
            return cursor.execute(sql, (record_id,))

    # --- categories CRUD ---

    def add_category(self, data: dict) -> int:
        """新增分类规则"""
        sql = """
        INSERT INTO `categories` (`rule_id`, `category`, `sub_category`, `problem`,
            `priority`, `required_cert`, `target_dept_semantic`, `description`)
        VALUES (%(rule_id)s, %(category)s, %(sub_category)s, %(problem)s,
            %(priority)s, %(required_cert)s, %(target_dept_semantic)s, %(description)s)
        """
        conn = self._get_connection()
        with conn.cursor() as cursor:
            cursor.execute(sql, data)
            return cursor.lastrowid

    def update_category(self, record_id: int, data: dict) -> int:
        """更新分类规则"""
        fields = {k: v for k, v in data.items() if k not in ('id', 'created_at')}
        if not fields:
            return 0
        set_clause = ", ".join([f"`{k}` = %s" for k in fields.keys()])
        values = list(fields.values()) + [record_id]
        sql = f"UPDATE `categories` SET {set_clause} WHERE `id` = %s"
        conn = self._get_connection()
        with conn.cursor() as cursor:
            return cursor.execute(sql, values)

    def delete_category(self, record_id: int) -> int:
        """删除分类规则（级联删除 keywords 和 locations）"""
        sql = "DELETE FROM `categories` WHERE `id`=%s"
        conn = self._get_connection()
        with conn.cursor() as cursor:
            return cursor.execute(sql, (record_id,))

    def get_category_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """按 ID 获取单个分类规则（含 keywords 和 locations）"""
        conn = self._get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM `categories` WHERE `id`=%s", (record_id,))
            cat = cursor.fetchone()
            if cat:
                cursor.execute("SELECT `keyword` FROM `category_trigger_keywords` WHERE `category_id`=%s", (record_id,))
                cat['trigger_keywords'] = [r['keyword'] for r in cursor.fetchall()]
                cursor.execute("SELECT `location` FROM `category_trigger_locations` WHERE `category_id`=%s", (record_id,))
                cat['trigger_location'] = [r['location'] for r in cursor.fetchall()]
            return cat

    # --- keywords CRUD ---

    def add_keyword(self, category_id: int, keyword: str) -> int:
        """新增触发关键词"""
        sql = "INSERT INTO `category_trigger_keywords` (`category_id`, `keyword`) VALUES (%s, %s)"
        conn = self._get_connection()
        with conn.cursor() as cursor:
            cursor.execute(sql, (category_id, keyword))
            return cursor.lastrowid

    def delete_keyword(self, record_id: int) -> int:
        """删除触发关键词"""
        sql = "DELETE FROM `category_trigger_keywords` WHERE `id`=%s"
        conn = self._get_connection()
        with conn.cursor() as cursor:
            return cursor.execute(sql, (record_id,))

    def update_keyword(self, record_id: int, keyword: str) -> int:
        """更新触发关键词"""
        sql = "UPDATE `category_trigger_keywords` SET `keyword`=%s WHERE `id`=%s"
        conn = self._get_connection()
        with conn.cursor() as cursor:
            return cursor.execute(sql, (keyword, record_id))

    def get_all_keywords_flat(self) -> List[Dict[str, Any]]:
        """获取所有关键词（扁平列表，含关联的 category 信息）"""
        sql = """
        SELECT k.`id`, k.`keyword`, k.`category_id`, c.`sub_category`, c.`problem`
        FROM `category_trigger_keywords` k
        LEFT JOIN `categories` c ON k.`category_id` = c.`id`
        ORDER BY k.`id`
        """
        conn = self._get_connection()
        with conn.cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchall()

    # --- locations CRUD ---

    def add_location(self, category_id: int, location: str) -> int:
        """新增触发位置"""
        sql = "INSERT INTO `category_trigger_locations` (`category_id`, `location`) VALUES (%s, %s)"
        conn = self._get_connection()
        with conn.cursor() as cursor:
            cursor.execute(sql, (category_id, location))
            return cursor.lastrowid

    def delete_location(self, record_id: int) -> int:
        """删除触发位置"""
        sql = "DELETE FROM `category_trigger_locations` WHERE `id`=%s"
        conn = self._get_connection()
        with conn.cursor() as cursor:
            return cursor.execute(sql, (record_id,))

    def update_location(self, record_id: int, location: str) -> int:
        """更新触发位置"""
        sql = "UPDATE `category_trigger_locations` SET `location`=%s WHERE `id`=%s"
        conn = self._get_connection()
        with conn.cursor() as cursor:
            return cursor.execute(sql, (location, record_id))

    def get_all_locations_flat(self) -> List[Dict[str, Any]]:
        """获取所有位置（扁平列表，含关联的 category 信息）"""
        sql = """
        SELECT l.`id`, l.`location`, l.`category_id`, c.`sub_category`, c.`problem`
        FROM `category_trigger_locations` l
        LEFT JOIN `categories` c ON l.`category_id` = c.`id`
        ORDER BY l.`id`
        """
        conn = self._get_connection()
        with conn.cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchall()

    def rules_data_exists(self) -> bool:
        """
        检查规则数据是否已导入数据库

        Returns:
            bool: 至少有一张规则表有数据返回 True
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                # 检查 categories 表（最重要的规则表）
                cursor.execute("SELECT COUNT(*) AS cnt FROM `categories`")
                row = cursor.fetchone()
                if row and row['cnt'] > 0:
                    return True
                # 也检查 address_mappings
                cursor.execute("SELECT COUNT(*) AS cnt FROM `address_mappings`")
                row = cursor.fetchone()
                return row['cnt'] > 0 if row else False
        except Exception as e:
            print(f"[WorkOrderDB] 检查规则数据失败: {e}")
            return False

    # ==================== Create（新增） ====================

    def insert(self, work_order_dict: Dict[str, Any]) -> int:
        """
        插入一条工单记录

        Args:
            work_order_dict: 工单字典，字段名需与表列名一致

        Returns:
            int: 新插入记录的自增 ID

        Raises:
            pymysql.err.IntegrityError: 工单号重复时抛出
        """
        sql = """
        INSERT INTO `work_orders` 
            (`order_no`, `accept_time`, `user_input`, `sub_category`, `problem`,
             `property_company`, `maintenance_unit`, `priority`, `required_cert`,
             `target_dept_semantic`, `status`, `address`, `reporter_name`, `reporter_phone`)
        VALUES 
            (%(order_no)s, %(accept_time)s, %(user_input)s, %(sub_category)s, %(problem)s,
             %(property_company)s, %(maintenance_unit)s, %(priority)s, %(required_cert)s,
             %(target_dept_semantic)s, %(status)s, %(address)s,
             %(reporter_name)s, %(reporter_phone)s)
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql, work_order_dict)
                return cursor.lastrowid
        except Exception as e:
            print(f"[WorkOrderDB] 插入工单失败: {e}")
            raise

    def save(self, work_order_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        保存工单（INSERT OR UPDATE）
        
        如果 order_no 已存在则更新，否则插入新记录。

        Args:
            work_order_dict: 工单字典

        Returns:
            Dict: 包含 status、message 和 id 的结果
        """
        try:
            existing = self.get_by_order_no(work_order_dict.get('order_no', ''))
            if existing:
                self.update_by_order_no(work_order_dict['order_no'], work_order_dict)
                return {
                    'status': 'SUCCESS',
                    'message': f"工单 {work_order_dict['order_no']} 已更新",
                    'id': existing['id'],
                    'action': 'update'
                }
            else:
                new_id = self.insert(work_order_dict)
                return {
                    'status': 'SUCCESS',
                    'message': f"工单 {work_order_dict['order_no']} 已保存",
                    'id': new_id,
                    'action': 'insert'
                }
        except Exception as e:
            print(f"[WorkOrderDB] 保存工单失败: {e}")
            return {
                'status': 'ERROR',
                'message': f'保存工单失败: {str(e)}'
            }

    # ==================== Read（查询） ====================

    def get_by_order_no(self, order_no: str) -> Optional[Dict[str, Any]]:
        """
        根据工单号查询工单

        Args:
            order_no: 维修单号

        Returns:
            Optional[Dict]: 工单字典，未找到返回 None
        """
        sql = "SELECT * FROM `work_orders` WHERE `order_no` = %s"
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql, (order_no,))
                return cursor.fetchone()
        except Exception as e:
            print(f"[WorkOrderDB] 查询工单失败: {e}")
            raise

    def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """
        根据自增 ID 查询工单

        Args:
            record_id: 记录 ID

        Returns:
            Optional[Dict]: 工单字典，未找到返回 None
        """
        sql = "SELECT * FROM `work_orders` WHERE `id` = %s"
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql, (record_id,))
                return cursor.fetchone()
        except Exception as e:
            print(f"[WorkOrderDB] 查询工单失败: {e}")
            raise

    def search(self,
               order_no: Optional[str] = None,
               sub_category: Optional[str] = None,
               property_company: Optional[str] = None,
               required_cert: Optional[str] = None,
               target_dept_semantic: Optional[str] = None,
               problem: Optional[str] = None,
               priority: Optional[str] = None,
               maintenance_unit: Optional[str] = None,
               status: Optional[str] = None,
               keyword: Optional[str] = None,
               worker_id: Optional[int] = None,
               start_time: Optional[str] = None,
               end_time: Optional[str] = None,
               limit: int = 100,
               offset: int = 0) -> List[Dict[str, Any]]:
        """
        多条件组合查询工单

        支持按工单号、sub_category、property_company、required_cert、
        target_dept_semantic、problem、priority、maintenance_unit、status、关键词、
        工人ID以及时间范围进行筛选。

        Args:
            order_no: 工单号（精确匹配）
            sub_category: 报修类型（精确匹配）
            property_company: 物业公司（精确匹配）
            required_cert: 所需资质证书（模糊匹配）
            target_dept_semantic: 目标维修部门（精确匹配）
            problem: 报修项目（模糊匹配）
            priority: 优先级（精确匹配）
            maintenance_unit: 维修单位（精确匹配）
            status: 工单状态（精确匹配）
            keyword: 关键词，在 user_input 和 address 中模糊搜索
            worker_id: 指派工人ID（精确匹配）
            start_time: 开始时间（ISO 格式字符串）
            end_time: 结束时间（ISO 格式字符串）
            limit: 返回记录数上限，默认 100
            offset: 偏移量，默认 0

        Returns:
            List[Dict]: 工单列表
        """
        conditions = []
        params = []

        if order_no:
            conditions.append("`order_no` = %s")
            params.append(order_no)
        if worker_id is not None:
            conditions.append("`worker_id` = %s")
            params.append(worker_id)
        if sub_category:
            conditions.append("`sub_category` = %s")
            params.append(sub_category)
        if property_company:
            conditions.append("`property_company` = %s")
            params.append(property_company)
        if required_cert:
            conditions.append("`required_cert` LIKE %s")
            params.append(f"%{required_cert}%")
        if target_dept_semantic:
            conditions.append("`target_dept_semantic` = %s")
            params.append(target_dept_semantic)
        if problem:
            conditions.append("`problem` LIKE %s")
            params.append(f"%{problem}%")
        if priority:
            conditions.append("`priority` = %s")
            params.append(priority)
        if maintenance_unit:
            conditions.append("`maintenance_unit` = %s")
            params.append(maintenance_unit)
        if status:
            conditions.append("`status` = %s")
            params.append(status)
        if keyword:
            conditions.append("(`user_input` LIKE %s OR `address` LIKE %s)")
            params.append(f"%{keyword}%")
            params.append(f"%{keyword}%")
        if start_time:
            conditions.append("`accept_time` >= %s")
            params.append(start_time)
        if end_time:
            conditions.append("`accept_time` <= %s")
            params.append(end_time)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        sql = f"SELECT * FROM `work_orders` {where_clause} ORDER BY `accept_time` DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()
        except Exception as e:
            print(f"[WorkOrderDB] 搜索工单失败: {e}")
            raise

    def search_count(self,
                     order_no: Optional[str] = None,
                     sub_category: Optional[str] = None,
                     property_company: Optional[str] = None,
                     required_cert: Optional[str] = None,
                     target_dept_semantic: Optional[str] = None,
                     problem: Optional[str] = None,
                     priority: Optional[str] = None,
                     maintenance_unit: Optional[str] = None,
                     status: Optional[str] = None,
                     keyword: Optional[str] = None,
                     worker_id: Optional[int] = None,
                     start_time: Optional[str] = None,
                     end_time: Optional[str] = None) -> int:
        """
        查询符合条件的工单总数（用于分页）

        参数同 search() 方法。

        Returns:
            int: 符合条件的记录总数
        """
        conditions = []
        params = []

        if order_no:
            conditions.append("`order_no` = %s")
            params.append(order_no)
        if worker_id is not None:
            conditions.append("`worker_id` = %s")
            params.append(worker_id)
        if sub_category:
            conditions.append("`sub_category` = %s")
            params.append(sub_category)
        if property_company:
            conditions.append("`property_company` = %s")
            params.append(property_company)
        if required_cert:
            conditions.append("`required_cert` LIKE %s")
            params.append(f"%{required_cert}%")
        if target_dept_semantic:
            conditions.append("`target_dept_semantic` = %s")
            params.append(target_dept_semantic)
        if problem:
            conditions.append("`problem` LIKE %s")
            params.append(f"%{problem}%")
        if priority:
            conditions.append("`priority` = %s")
            params.append(priority)
        if maintenance_unit:
            conditions.append("`maintenance_unit` = %s")
            params.append(maintenance_unit)
        if status:
            conditions.append("`status` = %s")
            params.append(status)
        if keyword:
            conditions.append("(`user_input` LIKE %s OR `address` LIKE %s)")
            params.append(f"%{keyword}%")
            params.append(f"%{keyword}%")
        if start_time:
            conditions.append("`accept_time` >= %s")
            params.append(start_time)
        if end_time:
            conditions.append("`accept_time` <= %s")
            params.append(end_time)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        sql = f"SELECT COUNT(*) AS total FROM `work_orders` {where_clause}"

        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                result = cursor.fetchone()
                return result['total'] if result else 0
        except Exception as e:
            print(f"[WorkOrderDB] 统计工单数量失败: {e}")
            raise

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        获取所有工单（分页）

        Args:
            limit: 每页条数
            offset: 偏移量

        Returns:
            List[Dict]: 工单列表
        """
        sql = "SELECT * FROM `work_orders` ORDER BY `accept_time` DESC LIMIT %s OFFSET %s"
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql, (limit, offset))
                return cursor.fetchall()
        except Exception as e:
            print(f"[WorkOrderDB] 获取所有工单失败: {e}")
            raise

    # ==================== Update（更新） ====================

    def update_by_order_no(self, order_no: str, update_data: Dict[str, Any]) -> int:
        """
        根据工单号更新工单信息

        Args:
            order_no: 维修单号
            update_data: 需要更新的字段字典

        Returns:
            int: 受影响的行数
        """
        if not update_data:
            return 0

        # 过滤掉不应该更新的字段
        skip_fields = {'id', 'order_no', 'created_at'}
        fields = {k: v for k, v in update_data.items() if k not in skip_fields}

        if not fields:
            return 0

        set_clause = ", ".join([f"`{k}` = %s" for k in fields.keys()])
        values = list(fields.values()) + [order_no]

        sql = f"UPDATE `work_orders` SET {set_clause} WHERE `order_no` = %s"

        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                affected = cursor.execute(sql, values)
                return affected
        except Exception as e:
            print(f"[WorkOrderDB] 更新工单失败: {e}")
            raise

    def update_by_id(self, record_id: int, update_data: Dict[str, Any]) -> int:
        """
        根据 ID 更新工单信息

        Args:
            record_id: 记录 ID
            update_data: 需要更新的字段字典

        Returns:
            int: 受影响的行数
        """
        if not update_data:
            return 0

        skip_fields = {'id', 'order_no', 'created_at'}
        fields = {k: v for k, v in update_data.items() if k not in skip_fields}

        if not fields:
            return 0

        set_clause = ", ".join([f"`{k}` = %s" for k in fields.keys()])
        values = list(fields.values()) + [record_id]

        sql = f"UPDATE `work_orders` SET {set_clause} WHERE `id` = %s"

        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                affected = cursor.execute(sql, values)
                return affected
        except Exception as e:
            print(f"[WorkOrderDB] 更新工单失败: {e}")
            raise

    # ==================== Delete（删除） ====================

    def delete_by_order_no(self, order_no: str) -> int:
        """
        根据工单号删除工单

        Args:
            order_no: 维修单号

        Returns:
            int: 受影响的行数（0 表示工单不存在）
        """
        sql = "DELETE FROM `work_orders` WHERE `order_no` = %s"
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                affected = cursor.execute(sql, (order_no,))
                return affected
        except Exception as e:
            print(f"[WorkOrderDB] 删除工单失败: {e}")
            raise

    def delete_by_id(self, record_id: int) -> int:
        """
        根据 ID 删除工单

        Args:
            record_id: 记录 ID

        Returns:
            int: 受影响的行数
        """
        sql = "DELETE FROM `work_orders` WHERE `id` = %s"
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                affected = cursor.execute(sql, (record_id,))
                return affected
        except Exception as e:
            print(f"[WorkOrderDB] 删除工单失败: {e}")
            raise

    # ==================== 批量操作 ====================

    def insert_batch(self, work_order_list: List[Dict[str, Any]]) -> int:
        """
        批量插入工单

        Args:
            work_order_list: 工单字典列表

        Returns:
            int: 成功插入的记录数
        """
        if not work_order_list:
            return 0

        sql = """
        INSERT INTO `work_orders` 
            (`order_no`, `accept_time`, `user_input`, `sub_category`, `problem`,
             `property_company`, `maintenance_unit`, `priority`, `required_cert`,
             `target_dept_semantic`, `status`, `address`)
        VALUES 
            (%(order_no)s, %(accept_time)s, %(user_input)s, %(sub_category)s, %(problem)s,
             %(property_company)s, %(maintenance_unit)s, %(priority)s, %(required_cert)s,
             %(target_dept_semantic)s, %(status)s, %(address)s)
        """
        count = 0
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                for wo in work_order_list:
                    try:
                        cursor.execute(sql, wo)
                        count += 1
                    except pymysql.err.IntegrityError:
                        print(f"[WorkOrderDB] 工单 {wo.get('order_no', 'unknown')} 已存在，跳过")
                        continue
            return count
        except Exception as e:
            print(f"[WorkOrderDB] 批量插入工单失败: {e}")
            raise

    def get_worker_by_id(self, worker_id: int) -> Optional[Dict[str, Any]]:
        """
        根据 worker_id 查询工人信息（姓名、电话等）

        Args:
            worker_id: 工人 ID

        Returns:
            Optional[Dict]: 工人信息字典，未找到返回 None
        """
        sql = "SELECT `id`, `name`, `phone`, `company`, `department`, `certs` FROM `workers` WHERE `id` = %s"
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql, (worker_id,))
                return cursor.fetchone()
        except Exception as e:
            print(f"[WorkOrderDB] 查询工人信息失败: {e}")
            return None

    def get_total_count(self) -> int:
        """
        获取工单总数量

        Returns:
            int: 工单总数
        """
        sql = "SELECT COUNT(*) AS total FROM `work_orders`"
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql)
                result = cursor.fetchone()
                return result['total'] if result else 0
        except Exception as e:
            print(f"[WorkOrderDB] 获取工单总数失败: {e}")
            raise

    # ==================== 连接管理 ====================

    # ==================== workers CRUD 操作 ====================

    def get_all_workers(self) -> List[Dict[str, Any]]:
        """获取所有工人"""
        sql = "SELECT `id`, `name`, `phone`, `company`, `department`, `certs` FROM `workers` ORDER BY `id`"
        conn = self._get_connection()
        with conn.cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchall()

    def add_worker(self, data: dict) -> int:
        """新增工人"""
        sql = """
        INSERT INTO `workers` (`name`, `phone`, `company`, `department`, `certs`)
        VALUES (%(name)s, %(phone)s, %(company)s, %(department)s, %(certs)s)
        """
        conn = self._get_connection()
        with conn.cursor() as cursor:
            cursor.execute(sql, data)
            return cursor.lastrowid

    def update_worker(self, record_id: int, data: dict) -> int:
        """更新工人"""
        fields = {k: v for k, v in data.items() if k in ('name', 'phone', 'company', 'department', 'certs')}
        if not fields:
            return 0
        set_clause = ", ".join([f"`{k}` = %s" for k in fields.keys()])
        values = list(fields.values()) + [record_id]
        sql = f"UPDATE `workers` SET {set_clause} WHERE `id` = %s"
        conn = self._get_connection()
        with conn.cursor() as cursor:
            return cursor.execute(sql, values)

    def delete_worker(self, record_id: int) -> int:
        """删除工人"""
        sql = "DELETE FROM `workers` WHERE `id`=%s"
        conn = self._get_connection()
        with conn.cursor() as cursor:
            return cursor.execute(sql, (record_id,))

    def create_sequence_table(self):
        """创建工单序号表（如不存在）"""
        conn = self._get_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `work_order_sequence` (
                    `date_key` DATE NOT NULL PRIMARY KEY COMMENT '日期键，格式YYYY-MM-DD',
                    `last_seq` INT NOT NULL DEFAULT 0 COMMENT '当日最新序号'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                COMMENT='工单序号表，记录每日最新工单序号'
            """)

    def get_next_order_sequence(self) -> int:
        """
        获取下一条工单序号（原子操作，支持高并发）

        通过 INSERT ... ON DUPLICATE KEY UPDATE 实现：
        - 当日首条 → INSERT 后 last_seq = 1
        - 后续调用 → UPDATE last_seq = last_seq + 1 并返回新值

        Returns:
            int: 当日最新序号（从 1 开始自增）
        """
        today = datetime.now().strftime("%Y-%m-%d")
        sql = """
        INSERT INTO `work_order_sequence` (`date_key`, `last_seq`)
        VALUES (%s, 1)
        ON DUPLICATE KEY UPDATE `last_seq` = `last_seq` + 1
        """
        conn = self._get_connection()
        with conn.cursor() as cursor:
            cursor.execute(sql, (today,))
            # 获取更新后的值
            cursor.execute("SELECT `last_seq` FROM `work_order_sequence` WHERE `date_key` = %s", (today,))
            row = cursor.fetchone()
            return row['last_seq'] if row else 1

    def close(self):
        """关闭数据库连接"""
        if self._connection and self._connection.open:
            self._connection.close()
            self._connection = None

    def __del__(self):
        """析构时自动关闭连接"""
        self.close()


def get_db(host: str = 'localhost', port: int = 3306,
           user: str = 'root', password: str = 'Qazplm147369#',
           database: str = 'AI_Work_Order') -> WorkOrderDB:
    """
    获取 WorkOrderDB 单例实例

    Args:
        host: 数据库主机
        port: 数据库端口
        user: 用户名
        password: 密码
        database: 数据库名

    Returns:
        WorkOrderDB: 数据库管理实例
    """
    return WorkOrderDB(host=host, port=port, user=user, password=password, database=database)