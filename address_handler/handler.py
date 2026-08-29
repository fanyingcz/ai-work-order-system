"""
地址处理模块 - 核心处理逻辑

【文件职责】
实现地址处理的核心逻辑，包括：
1. 从 address_mapping.json 加载地址映射数据
2. 调用腾讯地图API验证地址的真实性和完整性
3. 解析地址字符串，提取各层级地址信息（省、市、区、街道、门牌、小区、楼栋等）
4. 根据小区名称匹配对应的物业公司和维修单位
5. 支持精确匹配和模糊匹配两种方式
6. 返回统一的处理结果（AddressProcessingResult）

【处理流程】
地址字符串 → 腾讯地图API验证 → 解析地址 → 匹配映射 → 返回结果

【关键设计】
- _load_address_mappings(): 加载地址映射数据，构建字典和列表
- _call_tencent_geocoder(): 调用腾讯地图地理编码API
- validate_address(): 使用腾讯地图API验证地址真实性和可信度
- parse_address(): 使用腾讯地图API解析地址，提取各层级信息
- match_mapping(): 优先精确匹配，失败后尝试模糊匹配
- _fuzzy_match(): 模糊匹配算法，支持包含匹配和相似度匹配
- process(): 核心处理方法，协调各步骤完成地址处理

【状态标识规范】
- SUCCESS: 地址验证通过（可信度>=7），成功解析并映射到物业公司和维修单位
- ERROR: 地址验证失败或处理过程中发生错误
- MISS: 地址信息不完整或无法匹配到物业公司/维修单位
- LOW_RELIABILITY: 地址解析可信度较低（<7），需要人工确认

【数据依赖】
- data/rules/address_mapping.json: 地址映射数据，包含小区到物业公司和维修单位的对应关系

【环境变量】
- lbs_key: 腾讯地图API Key
- lbs_ws_sk: 腾讯地图Web Service Secret Key（用于签名）

【使用场景】
- 作为报修流程的第三步，接收地址信息并映射到物业公司和维修单位
- 为工单生成模块提供物业公司和维修单位信息
"""

import json
import os
import requests
import hashlib
import hmac
import base64
from urllib.parse import urlencode
from typing import Optional, List, Dict, Tuple
from .models import AddressInfo, AddressMapping, AddressProcessingResult
from .mapping_handler import MappingHandler


class AddressHandler:
    """
    地址处理器

    负责处理用户输入的地址信息，包括：
    1. 调用腾讯地图API验证地址的真实性和完整性
    2. 解析地址，提取各层级信息（省、市、区、街道、门牌、小区、楼栋等）
    3. 根据解析后的小区名称，映射到对应的物业公司和维修单位

    地址映射数据来源于 data/rules/address_mapping.json 文件，该文件包含小区名称
    到物业公司和维修单位的对应关系。

    处理状态说明：
    - SUCCESS: 地址验证通过（可信度>=7），成功解析并映射到物业公司和维修单位
    - ERROR: 地址验证失败或处理过程中发生错误
    - MISS: 地址信息不完整或无法匹配到物业公司/维修单位
    - LOW_RELIABILITY: 地址解析可信度较低（<7），需要人工确认

    Attributes:
        address_mappings (Dict[str, AddressMapping]): 地址映射字典，以小区名称为键
        mapping_list (List[AddressMapping]): 地址映射列表，用于模糊匹配
        lbs_key (str): 腾讯地图API Key
        lbs_ws_sk (str): 腾讯地图Web Service Secret Key
    """

    def __init__(self, rules_dir: str = "data/rules"):
        """
        初始化地址处理器

        Args:
            rules_dir: address_mapping.json 文件所在目录，默认为 "data/rules"
        """
        self.rules_dir = rules_dir
        self.mapping_handler = MappingHandler(rules_dir=rules_dir)
        
        self.lbs_key = os.environ.get('lbs_key', '')
        self.lbs_ws_sk = os.environ.get('lbs_ws_sk', '')
        
        if not self.lbs_key:
            print("[警告] 环境变量 lbs_key 未设置，请设置腾讯地图API Key")
            print("[提示] 可通过 set lbs_key=your_key_here 设置")

    def _generate_signature(self, params: dict) -> str:
        """
        生成腾讯地图API签名

        签名算法(根据腾讯地图官方文档):
        1. 对参数按key进行ASCII升序排序（不含sig参数）
        2. 参数值使用原始数据，不进行任何编码
        3. 拼接为 key=value&key=value 格式
        4. 格式：请求路径+"?"+请求参数+SK
        5. 使用MD5计算拼接后字符串的哈希值，即为签名(sig)

        API文档: https://lbs.qq.com/FAQ/server_faq.html

        Args:
            params: API请求参数字典（不含sig参数）

        Returns:
            str: 生成的签名
        """
        path = "/ws/geocoder/v1"
        
        sorted_params = sorted(params.items(), key=lambda x: x[0])
        query_string = '&'.join(f"{k}={v}" for k, v in sorted_params)
        
        string_to_sign = f"{path}?{query_string}{self.lbs_ws_sk}"
        
        return hashlib.md5(string_to_sign.encode('utf-8')).hexdigest()

    def _call_tencent_geocoder(self, address: str) -> Optional[dict]:
        """
        调用腾讯地图地理编码API

        规则:
        - 默认所有地址加入"上海市"前缀
        - 使用policy=1（宽松模式）
        - 地址参数需要进行URL编码

        Args:
            address: 待解析的地址字符串

        Returns:
            Optional[dict]: API返回的JSON数据，解析失败返回None

        API文档: https://lbs.qq.com/service/webService/webServiceGuide/webServiceGeocoder
        """
        from urllib.parse import quote
        
        if not self.lbs_key or not address:
            return None

        if not address.startswith('上海市') and not address.startswith('上海'):
            address = f"上海市{address}"

        url = "https://apis.map.qq.com/ws/geocoder/v1"
        
        raw_params = {
            "address": address,
            "key": self.lbs_key,
            "policy": 1
        }

        sig = None
        if self.lbs_ws_sk:
            sig = self._generate_signature(raw_params)

        encoded_params = []
        for k, v in sorted(raw_params.items(), key=lambda x: x[0]):
            if isinstance(v, str):
                encoded_value = quote(v, encoding='utf-8', safe='')
                encoded_value = encoded_value.replace('+', '%20')
            else:
                encoded_value = str(v)
            encoded_params.append(f"{k}={encoded_value}")
        
        if sig:
            encoded_params.append(f"sig={sig}")
        
        full_url = f"{url}?{'&'.join(encoded_params)}"

        try:
            response = requests.get(full_url, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get('status') == 0:
                return result
            else:
                print(f"[AddressHandler] 腾讯地图API返回错误(status={result.get('status')}): {result.get('message', '未知错误')}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"[AddressHandler] 调用腾讯地图API失败: {e}")
            return None

    def validate_address(self, address: str) -> Tuple[bool, Optional[dict]]:
        """
        使用腾讯地图API验证地址的真实性和完整性

        调用腾讯地图地理编码API，检查地址是否可解析以及解析可信度。

        Args:
            address: 待验证的地址字符串

        Returns:
            Tuple[bool, Optional[dict]]: 
                - bool: 地址验证通过返回True，否则返回False
                - dict: API返回的完整结果，用于后续解析
        """
        if not address or not isinstance(address, str):
            return False, None

        address = address.strip()
        if len(address) < 5:
            return False, None

        api_result = self._call_tencent_geocoder(address)
        if api_result is None:
            return False, None

        result_data = api_result.get('result', {})
        reliability = result_data.get('reliability', 0)

        if reliability >= 7:
            return True, api_result
        elif reliability > 0:
            return True, api_result
        else:
            return False, None

    def parse_address(self, address: str, api_result: Optional[dict] = None) -> AddressInfo:
        """
        使用腾讯地图API解析地址字符串，提取各层级信息

        将完整的地址字符串解析为结构化的 AddressInfo 对象，提取省、市、区、
        街道、门牌、小区、楼栋、单元、室号等信息。

        社区(community)提取策略：
        1. 优先从API返回的 title 字段提取有命名的社区名（如"示例小区"、"示例花园一期"）
        2. 如果title中提取不到，再从原始地址中提取
        3. 同时尝试两个来源，选择更具体的（更长）结果
        4. 如果以上都无法提取到有命名的社区名，使用API title作为后备标识
           （如"示例路41弄"、"示例路1299号"本身没有命名，但作为地址定位符同样有效）

        Args:
            address: 完整的地址字符串
            api_result: 腾讯地图API返回的结果（可选，避免重复调用）

        Returns:
            AddressInfo: 解析后的地址信息对象
        """
        address_info = AddressInfo(full_address=address)

        if api_result is None:
            api_result = self._call_tencent_geocoder(address)

        if api_result is None:
            return address_info

        result_data = api_result.get('result', {})
        location = result_data.get('location', {})
        address_components = result_data.get('address_components', {})
        ad_info = result_data.get('ad_info', {})

        address_info.province = address_components.get('province')
        address_info.city = address_components.get('city')
        address_info.district = address_components.get('district')
        address_info.street = address_components.get('street')
        address_info.street_number = address_components.get('street_number')
        
        address_info.reliability = result_data.get('reliability')
        address_info.lat = location.get('lat')
        address_info.lng = location.get('lng')
        address_info.adcode = ad_info.get('adcode')

        # 获取API返回的地址级别，用于判断地址类型
        # level 含义: 9=POI点, 10=区县, 11=街道, 12=路口, 19=门牌, 20=小区, 24=楼栋, 25=POI兴趣点
        api_level = result_data.get('level', 0)

        # ============================================================
        # 社区名提取策略：
        # 1. 同时从 API title 和原始地址尝试提取有命名的社区名
        # 2. 选择更具体（更长）的那一个
        # 3. 如果都没提取到，用 API title 作为后备标识
        # ============================================================
        api_title = result_data.get('title', '')

        # 步骤1: 使用 address_mapping.json 中的数据预先判断 API title 是否为已知社区名
        known_community = None
        cleaned_api_title = ''
        if api_title:
            cleaned_api_title = self._clean_api_title(api_title)
        
        if cleaned_api_title and cleaned_api_title.endswith('里'):
            # 去掉 "三里桥" → "三里" 的长度限制，已经是标准的 "里" 后缀
            pass

        # 步骤1: 从清理后的 API title 和原始地址分别提取社区名
        community_from_title = self._extract_community(cleaned_api_title, api_level) if cleaned_api_title else None
        community_from_address = self._extract_community(address, api_level)

        # 步骤2: 选择更具体的那一个（更长的通常更具体）
        if community_from_title and community_from_address:
            # 优先选择更长的（更具体），如果一样长优先选原始地址的（可能包含"一期"等后缀）
            if len(community_from_address) > len(community_from_title):
                address_info.community = community_from_address
            else:
                address_info.community = community_from_title
        elif community_from_title:
            address_info.community = community_from_title
        elif community_from_address:
            address_info.community = community_from_address

        # 步骤3: 后备方案——对于没有命名的地址（如"示例路41弄"、"示例路1299号"）
        # 使用 API title 或原始地址作为 community 标识
        if not address_info.community:
            # 优先尝试从API title清理
            if api_title:
                cleaned_title = self._clean_api_title(api_title)
                if cleaned_title:
                    address_info.community = cleaned_title
            
            # 如果API title也不可用（是POI被丢弃了），从原始地址提取
            if not address_info.community:
                # 从原始地址提取"路名+弄号"或"路名+门牌号"作为标识
                self._extract_unnamed_community(address, address_info)

        # 当 street_number 为空时，从原始地址中提取楼栋/室号信息
        street_number = address_info.street_number or ''
        if not street_number:
            self._parse_street_number(address, address_info)
        else:
            self._parse_street_number(street_number, address_info)

        return address_info

    def _extract_community(self, text: str, api_level: int = 0) -> Optional[str]:
        """
        从地址文本中提取小区/社区名称

        使用正则匹配常见的小区命名模式：
        - xxx新村（如"示例小区"）
        - xxx花园（如"海洲桃花园"）
        - xxx小区（如"阳光小区"）
        - xxx家园（如"锦绣家园"）
        - xxx里（如"幸福里"）
        - xxx苑、xxx公寓、xxx城、xxx山庄等
        - 含特殊字符的复合名（如"示例·云顶花园"）

        利用API返回的 level 字段辅助判断：
        - level >= 20（小区/楼栋级别）: 优先从title提取小区名
        - level < 20（街道/门牌级别）: 仅通过标准后缀匹配，避免将路名误提取

        Args:
            text: 地址文本（API返回的title或原始地址）
            api_level: API返回的地址级别（用于辅助判断地址类型）

        Returns:
            Optional[str]: 提取到的小区名称，未找到返回None
        """
        import re

        # 黑名单：以这些结尾的文本不是小区名（通常是路名、单位名）
        non_community_suffixes = [
            '路', '街', '大道', '大街', '巷', '弄',
            '大厦', '广场', '中心', '大楼', '办公楼', '写字楼',
            '酒店', '饭店', '宾馆', '商场', '超市', '市场',
            '医院', '学校', '银行', '公司', '集团', '工厂',
            '馆', '院', '所', '社', '部', '局', '处',
        ]

        # 行政区域前缀：匹配时会从结果中剥离
        admin_prefixes = ['浦东新区', '上海', '上海市', '示例镇', '航头镇', '张江镇']

        # 如果 level < 20（街道/门牌/POI级别），说明地址不是小区级别
        # 此时只通过标准后缀匹配，不使用后备提取逻辑
        is_community_level = api_level >= 20

        # 模式1: 带连接符的复合小区名（优先匹配，如"示例·云顶花园"）
        match = re.search(r'([\u4e00-\u9fa5]+[·\.][\u4e00-\u9fa5]+)', text)
        if match:
            candidate = match.group(1)
            # 反复剥离行政前缀（如"浦东新区示例镇示例·云顶花园" → "示例·云顶花园"）
            cleaned = candidate
            while True:
                stripped = False
                for prefix in admin_prefixes:
                    if cleaned.startswith(prefix):
                        cleaned = cleaned[len(prefix):]
                        stripped = True
                        break
                if not stripped:
                    break
            # 检查是否以黑名单后缀结尾
            if not any(cleaned.endswith(suffix) for suffix in non_community_suffixes):
                return cleaned

        # 模式2: 标准后缀匹配（按优先级从高到低）
        patterns = [
            r'([\u4e00-\u9fa5]+新村)',       # xxx新村
            r'([\u4e00-\u9fa5]+花园[\u4e00-\u9fa5]*期?)',  # xxx花园 / xxx花园一期
            r'([\u4e00-\u9fa5]+小区)',       # xxx小区
            r'([\u4e00-\u9fa5]+家园)',       # xxx家园
            r'([\u4e00-\u9fa5]+[苑里])(?!\s*(路|街|东路|南路|西路|北路|中路))',  # xxx苑/里（但不能是路名的一部分如"昌里东路"）
            r'([\u4e00-\u9fa5]+公寓)',       # xxx公寓
            r'([\u4e00-\u9fa5]+[城山庄])',   # xxx城 / xxx山庄
            r'([\u4e00-\u9fa5]+[村弄])(?!\s*(路|街|东路|南路|西路|北路|中路))',  # xxx村/弄（但不能是路名的一部分）
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                candidate = match.group(1)
                # 剥离行政前缀
                cleaned = candidate
                for prefix in admin_prefixes:
                    if cleaned.startswith(prefix):
                        cleaned = cleaned[len(prefix):]
                        break
                if not any(cleaned.endswith(suffix) for suffix in non_community_suffixes):
                    return cleaned

        # 模式3: 仅当 level >= 20（小区/楼栋级别）时，才使用后备提取逻辑
        if is_community_level:
            # 去除省市区路街道门牌号等常见前缀后，剩下的可能就是小区名
            cleaned = re.sub(r'[省市]|浦东新区|街道|镇|路\d+弄|弄\d+号|号\d+室|期.*', '', text)
            cleaned_match = re.search(r'([\u4e00-\u9fa5]{3,})', cleaned)
            if cleaned_match:
                candidate = cleaned_match.group(1)
                # 黑名单过滤
                common_prefixes = ['浦东新区', '上海', '示例镇', '航头镇']
                if candidate not in common_prefixes:
                    if not any(candidate.endswith(suffix) for suffix in non_community_suffixes):
                        return candidate

        return None

    def _clean_api_title(self, title: str) -> Optional[str]:
        """
        清理API返回的title字段，去除楼栋/室号/POI名称等多余信息

        例如：
        - "示例路451弄-38号" → "示例路451弄"
        - "浦东大道290弄-13号楼" → "浦东大道290弄"
        - "东方有线示例路街道有线管理站" → 丢弃（POI名称，不是地址标识）

        Args:
            title: API返回的title

        Returns:
            Optional[str]: 清理后的地址标识
        """
        import re

        # 如果title包含POI特征词（不是地址标识），丢弃
        poi_keywords = ['有线', '管理站', '公司', '集团', '中心', '大厦', '广场',
                        '酒店', '饭店', '学校', '医院', '银行', '超市', '商场',
                        '中共', '党委', '总支', '支部', '居委会', '委员会',
                        '服务站', '工作站', '管理处', '停车场', '物业处',
                        '办事处', '政府', '街道办', '社区服务中心',
                        '地面停车', '地下车库', '垃圾站', '公厕']
        for kw in poi_keywords:
            if kw in title and not any(suffix in title for suffix in ['新村', '小区', '花园', '家园', '苑', '里', '村', '弄']):
                # 是POI名称，不是地址标识，丢弃
                return None

        # 去除末尾的楼栋/室号后缀：
        # 1. 带连接符的："-38号"、"-13号楼"
        cleaned = re.sub(r'(?:-|—|－)\d+(?:号楼|号|室|幢)?$', '', title)
        # 2. 弄/村/苑/里 后的号+室："弄13号102" → "弄"
        #    但不影响"路1299号"（路不是社区后缀）
        cleaned = re.sub(r'(弄|村|苑|里|居|坊|城)\d+号\d*室?$', r'\1', cleaned)
        # 3. 去除"弄小区"中的冗余"小区"后缀
        #    "张杨路370弄小区-16号" → step1/2 → "张杨路370弄小区" → "张杨路370弄"
        cleaned = re.sub(r'(弄)小区$', r'\1', cleaned)
        # 4. 去除末尾的纯数字（如 "2507" 室号）
        cleaned = re.sub(r'\d+$', '', cleaned)
        # 5. 去除末尾的"室"后缀
        cleaned = re.sub(r'室$', '', cleaned)

        # 如果清理后太短（<3个字符），丢弃
        if len(cleaned) < 3:
            return None

        return cleaned

    def _extract_unnamed_community(self, address: str, address_info: AddressInfo):
        """
        从原始地址中提取无名地址的社区标识

        对于没有命名小区的地址（如"浦三路277弄1号"），
        提取"路名+弄号"或"路名+门牌号"作为社区标识。

        Args:
            address: 原始地址字符串
            address_info: 地址信息对象，用于设置community字段
        """
        import re

        # 如果已经有community了，跳过
        if address_info.community:
            return

        # 模式1: 提取 "xxx路xxx弄" 或 "xxx街xxx弄"
        match = re.search(r'([\u4e00-\u9fa5]+[路街][\d]+弄)', address)
        if match:
            address_info.community = match.group(1)
            return

        # 模式2: 提取 "xxx路xxx号"（当没有"弄"时）
        match = re.search(r'([\u4e00-\u9fa5]+[路街][\d]+号)', address)
        if match:
            address_info.community = match.group(1)
            return

        # 模式3: 提取 "xxx路xxx"（纯路名+数字）
        match = re.search(r'([\u4e00-\u9fa5]+[路街]\d+)', address)
        if match:
            address_info.community = match.group(1)
            return

    def _parse_street_number(self, street_number: str, address_info: AddressInfo):
        """
        从门牌号码中提取楼栋、单元、室号信息

        Args:
            street_number: 门牌号码字符串
            address_info: 地址信息对象，用于设置提取的字段
        """
        import re

        room_match = re.search(r'(\d+)\s*室', street_number)
        if room_match:
            address_info.room = room_match.group(0)

        unit_match = re.search(r'(\d+)\s*单元', street_number)
        if unit_match:
            address_info.unit = unit_match.group(0)

        building_match = re.search(r'(\d+)\s*号', street_number)
        if building_match:
            address_info.building = building_match.group(0)

    def match_mapping(self, address_info: AddressInfo) -> Optional[AddressMapping]:
        """
        根据解析后的地址信息匹配物业公司和维修单位

        使用 MappingHandler 进行匹配，支持三种匹配模式：
        1. 街道+小区匹配（最精确）
        2. 小区匹配
        3. 街道匹配（维修单位为MISS）

        Args:
            address_info: 解析后的地址信息对象

        Returns:
            Optional[AddressMapping]: 匹配到的地址映射对象，无法匹配时返回 None
        """
        return self.mapping_handler.match(address_info)

    def process(self, address: str) -> AddressProcessingResult:
        """
        处理地址信息，完成验证、解析和映射

        处理流程：
        1. 调用腾讯地图API验证地址真实性
        2. 解析地址，提取各层级信息（district、street、street_number、reliability等）
        3. 根据小区名称匹配物业公司和维修单位
        4. 返回处理结果

        Args:
            address: 用户输入的地址字符串

        Returns:
            AddressProcessingResult: 地址处理结果，包含解析后的地址信息和映射结果

        状态说明：
        - SUCCESS: 地址验证通过，成功解析并映射到物业公司和维修单位
        - ERROR: 地址验证失败或处理过程中发生错误
        - MISS: 地址信息不完整或无法匹配到物业公司/维修单位
        - LOW_RELIABILITY: 地址解析可信度较低（<7），需要人工确认
        """
        try:
            valid, api_result = self.validate_address(address)
            
            if not valid:
                address_info = AddressInfo(full_address=address)
                return AddressProcessingResult(
                    address_info=address_info,
                    status='ERROR'
                )

            address_info = self.parse_address(address, api_result)

            if address_info.reliability and address_info.reliability < 7:
                mapping = self.match_mapping(address_info)
                return AddressProcessingResult(
                    address_info=address_info,
                    property_company=mapping.property_company if mapping else None,
                    maintenance_unit=mapping.maintenance_unit if mapping else None,
                    status='LOW_RELIABILITY'
                )

            mapping = self.match_mapping(address_info)

            if not mapping:
                return AddressProcessingResult(
                    address_info=address_info,
                    status='MISS'
                )

            return AddressProcessingResult(
                address_info=address_info,
                property_company=mapping.property_company,
                maintenance_unit=mapping.maintenance_unit,
                status='SUCCESS'
            )

        except Exception as e:
            print(f"[AddressHandler] 处理异常: {e}")
            address_info = AddressInfo(full_address=address)
            return AddressProcessingResult(
                address_info=address_info,
                status='ERROR'
            )