"""
地址映射处理器 - 核心匹配逻辑

【文件职责】
实现新的地址映射匹配逻辑，支持三种匹配模式：
1. 街道+小区匹配：当解析结果中街道和小区均有数据时，使用"街道+小区"作为匹配键
2. 小区匹配：当只有小区数据时，使用小区名称匹配
3. 街道匹配：当只有街道数据时，使用街道名称匹配，维修单位为MISS

【匹配优先级】
优先级从高到低：
1. 街道+小区精确匹配（最精确）
2. 小区精确匹配
3. 街道精确匹配（维修单位为MISS）
4. 街道+小区模糊匹配
5. 小区模糊匹配
6. 街道模糊匹配（维修单位为MISS）

【数据结构】
地址映射数据来源于数据库 address_mappings 表或 address_mapping.json，每条记录包含：
- community: 小区名称（可为空）
- street: 街道名称（可为空）
- property_company: 物业公司名称
- maintenance_unit: 维修单位名称（可为"MISS"）
- district: 区县（辅助匹配）
- city: 城市（辅助匹配）

【使用场景】
作为 address_handler 模块的核心匹配引擎，供 AddressHandler 调用
"""

import json
import os
from typing import Optional, Dict, List, Tuple
from .models import AddressMapping, AddressInfo
from db import get_db


class MappingHandler:
    """
    地址映射处理器

    负责加载地址映射数据并执行匹配逻辑。

    Attributes:
        mappings (List[AddressMapping]): 所有映射数据列表
        street_community_map (Dict[str, AddressMapping]): 街道+小区精确匹配字典
        community_map (Dict[str, AddressMapping]): 小区精确匹配字典
        street_map (Dict[str, AddressMapping]): 街道精确匹配字典
    """

    def __init__(self, rules_dir: str = "data/rules"):
        """
        初始化映射处理器

        Args:
            rules_dir: address_mapping.json 文件所在目录
        """
        self.rules_dir = rules_dir
        self.mappings = []
        self.street_community_map = {}
        self.community_map = {}
        self.street_map = {}
        self._db_available = False
        self._load_mappings()

    def _load_mappings(self):
        """
        加载地址映射数据，构建三个匹配字典

        优先从数据库读取，DB 不可用时回退到 JSON 文件。
        构建：
        1. street_community_map: 以"街道+小区"为键的精确匹配字典
        2. community_map: 以小区名称为键的精确匹配字典
        3. street_map: 以街道名称为键的精确匹配字典
        """
        mappings_data = None

        # 优先从数据库加载
        try:
            db = get_db()
            if db.rules_data_exists():
                db_mappings = db.get_all_address_mappings()
                if db_mappings:
                    mappings_data = db_mappings
                    self._db_available = True
                    print(f"[MappingHandler] 从数据库加载地址映射数据")
        except Exception as e:
            print(f"[MappingHandler] 从数据库加载地址映射失败，回退到 JSON: {e}")

        # JSON 回退
        if mappings_data is None:
            mapping_file = os.path.join(self.rules_dir, 'address_mapping.json')
            if not os.path.exists(mapping_file):
                raise FileNotFoundError(f"address_mapping.json 文件不存在: {mapping_file}")

            with open(mapping_file, 'r', encoding='utf-8') as f:
                mappings_data = json.load(f)
            print(f"[MappingHandler] 从 JSON 文件加载地址映射数据")

        for item in mappings_data:
            # 兼容 DB 和 JSON 两种字段命名
            if self._db_available:
                mapping = AddressMapping(
                    community=item.get('community', ''),
                    street=item.get('street'),
                    property_company=item.get('property_company', ''),
                    maintenance_unit=item.get('maintenance_unit', 'MISS'),
                    district=item.get('district'),
                    city=item.get('city')
                )
            else:
                mapping = AddressMapping(
                    community=item.get('community', ''),
                    street=item.get('street'),
                    property_company=item.get('property_company', ''),
                    maintenance_unit=item.get('maintenance_unit', 'MISS'),
                    district=item.get('district'),
                    city=item.get('city')
                )
            self.mappings.append(mapping)

            # 构建精确匹配字典
            if mapping.street and mapping.community:
                key = f"{mapping.street}_{mapping.community}"
                self.street_community_map[key] = mapping

            if mapping.community:
                if mapping.community not in self.community_map:
                    self.community_map[mapping.community] = mapping

            if mapping.street:
                if mapping.street not in self.street_map:
                    self.street_map[mapping.street] = mapping

        print(f"[MappingHandler] 已加载 {len(self.mappings)} 条映射数据")
        print(f"  - 街道+小区映射: {len(self.street_community_map)} 条")
        print(f"  - 小区映射: {len(self.community_map)} 条")
        print(f"  - 街道映射: {len(self.street_map)} 条")

    def match(self, address_info: AddressInfo) -> Optional[AddressMapping]:
        """
        根据解析后的地址信息匹配映射

        匹配逻辑：
        1. 如果有community，优先用community匹配，可以输出完整的property_company和maintenance_unit
        2. 如果只有street（没有community），用street匹配，只输出property_company，maintenance_unit置为空

        匹配优先级（从高到低）：
        1. 小区精确匹配（有community时）
        2. 小区模糊匹配（有community时）
        3. 街道精确匹配（只有street时）
        4. 街道模糊匹配（只有street时）

        Args:
            address_info: 解析后的地址信息

        Returns:
            Optional[AddressMapping]: 匹配到的映射对象，无法匹配返回 None
        """
        street = address_info.street
        community = address_info.community
        district = address_info.district

        if community:
            if community in self.community_map:
                mapping = self.community_map[community]
                if self._check_district_match(mapping, district):
                    return mapping

            result = self._fuzzy_community_match(community, district)
            if result:
                return result

        if street and not community:
            if street in self.street_map:
                mapping = self.street_map[street]
                if self._check_district_match(mapping, district):
                    return AddressMapping(
                        community=mapping.community,
                        street=mapping.street,
                        property_company=mapping.property_company,
                        maintenance_unit="",
                        district=mapping.district,
                        city=mapping.city
                    )

            result = self._fuzzy_street_match(street, district)
            if result:
                return AddressMapping(
                    community=result.community,
                    street=result.street,
                    property_company=result.property_company,
                    maintenance_unit="",
                    district=result.district,
                    city=result.city
                )

        return None

    def _check_district_match(self, mapping: AddressMapping, district: Optional[str]) -> bool:
        """
        检查区县是否匹配

        如果映射中指定了区县，需要验证地址的区县是否匹配；
        如果映射中没有指定区县，则认为匹配。

        Args:
            mapping: 映射对象
            district: 地址的区县

        Returns:
            bool: 匹配返回 True，否则返回 False
        """
        if mapping.district and district:
            return mapping.district in district or district in mapping.district
        return True

    def _fuzzy_street_community_match(self, street: str, community: str,
                                       district: Optional[str]) -> Optional[AddressMapping]:
        """
        街道+小区模糊匹配

        在所有映射中查找街道包含或被包含于输入街道，
        且小区包含或被包含于输入小区的记录。

        Args:
            street: 输入街道
            community: 输入小区
            district: 输入区县

        Returns:
            Optional[AddressMapping]: 匹配到的映射对象
        """
        for mapping in self.mappings:
            if mapping.street and mapping.community:
                street_match = mapping.street in street or street in mapping.street
                community_match = mapping.community in community or community in mapping.community
                if street_match and community_match:
                    if self._check_district_match(mapping, district):
                        return mapping
        return None

    def _fuzzy_community_match(self, community: str, district: Optional[str]) -> Optional[AddressMapping]:
        """
        小区模糊匹配

        在所有映射中查找小区名称包含或被包含于输入小区的记录。

        Args:
            community: 输入小区
            district: 输入区县

        Returns:
            Optional[AddressMapping]: 匹配到的映射对象
        """
        for mapping in self.mappings:
            if mapping.community:
                if mapping.community in community or community in mapping.community:
                    if self._check_district_match(mapping, district):
                        return mapping
        return None

    def _fuzzy_street_match(self, street: str, district: Optional[str]) -> Optional[AddressMapping]:
        """
        街道模糊匹配

        在所有映射中查找街道名称包含或被包含于输入街道的记录。

        Args:
            street: 输入街道
            district: 输入区县

        Returns:
            Optional[AddressMapping]: 匹配到的映射对象
        """
        for mapping in self.mappings:
            if mapping.street:
                if mapping.street in street or street in mapping.street:
                    if self._check_district_match(mapping, district):
                        return mapping
        return None

    def get_mapping_key(self, address_info: AddressInfo) -> str:
        """
        获取地址信息的匹配键

        根据地址信息生成匹配键，用于调试和日志记录。

        Args:
            address_info: 地址信息

        Returns:
            str: 匹配键（街道+小区 / 小区 / 街道）
        """
        if address_info.street and address_info.community:
            return f"{address_info.street}_{address_info.community}"
        elif address_info.community:
            return address_info.community
        elif address_info.street:
            return address_info.street
        return ""