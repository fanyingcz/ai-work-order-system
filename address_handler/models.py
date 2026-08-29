"""
地址处理模块 - 数据模型定义

【文件职责】
定义地址处理模块所需的所有数据模型，包括：
1. AddressInfo: 地址信息数据模型，封装解析后的各层级地址
2. AddressMapping: 地址映射数据模型，封装小区到物业公司和维修单位的映射关系
3. AddressProcessingResult: 地址处理结果封装类，统一返回处理状态和结果

【设计说明】
- AddressInfo 采用分层设计，支持省、市、区、街道、小区、楼栋、单元、室号等多级地址
- AddressMapping 以小区名称为核心关键字，同时支持区县和城市作为辅助匹配条件
- AddressProcessingResult 统一封装处理状态和映射结果，便于上层进行异常处理
- 所有模型均提供 to_dict() 方法，便于序列化为字典格式进行存储或传输

【状态标识规范】
- SUCCESS: 地址验证通过，成功解析并映射到物业公司和维修单位
- ERROR: 地址验证失败或处理过程中发生错误
- MISS: 地址信息不完整（如缺少小区名称）或无法匹配到物业公司/维修单位

【使用场景】
- AddressInfo: 封装解析后的地址信息，供地址映射和工单生成使用
- AddressMapping: 封装地址映射数据，供 AddressHandler 加载和匹配使用
- AddressProcessingResult: 统一返回处理状态，便于上层进行异常处理和用户提示
"""

from typing import Optional


class AddressInfo:
    """
    地址信息数据模型

    用于封装从用户输入中提取的地址信息，包括完整地址和解析后的各层级地址。
    通过腾讯地图API解析后，包含 district、street、street_number、reliability 等字段。

    Attributes:
        full_address (str): 完整的地址字符串
        province (Optional[str]): 省份，如"上海市"
        city (Optional[str]): 城市，如"上海市"
        district (Optional[str]): 区县，如"浦东新区"
        street (Optional[str]): 街道/道路，如"沂南路"
        street_number (Optional[str]): 门牌，如"54弄8号603室"
        community (Optional[str]): 小区/社区名称，如"阳光小区"
        building (Optional[str]): 楼栋号，如"1号楼"
        unit (Optional[str]): 单元号，如"2单元"
        room (Optional[str]): 室号，如"301室"
        reliability (Optional[int]): 可信度 1-10，>=7表示解析结果较为准确
        lat (Optional[float]): 纬度
        lng (Optional[float]): 经度
        adcode (Optional[str]): 行政区划代码
    """
    full_address: str
    province: Optional[str]
    city: Optional[str]
    district: Optional[str]
    street: Optional[str]
    street_number: Optional[str]
    community: Optional[str]
    building: Optional[str]
    unit: Optional[str]
    room: Optional[str]
    reliability: Optional[int]
    lat: Optional[float]
    lng: Optional[float]
    adcode: Optional[str]

    def __init__(self, full_address: str, province: Optional[str] = None,
                 city: Optional[str] = None, district: Optional[str] = None,
                 street: Optional[str] = None, street_number: Optional[str] = None,
                 community: Optional[str] = None, building: Optional[str] = None,
                 unit: Optional[str] = None, room: Optional[str] = None,
                 reliability: Optional[int] = None, lat: Optional[float] = None,
                 lng: Optional[float] = None, adcode: Optional[str] = None):
        self.full_address = full_address
        self.province = province
        self.city = city
        self.district = district
        self.street = street
        self.street_number = street_number
        self.community = community
        self.building = building
        self.unit = unit
        self.room = room
        self.reliability = reliability
        self.lat = lat
        self.lng = lng
        self.adcode = adcode

    def to_dict(self):
        """
        将地址信息转换为字典格式

        Returns:
            dict: 包含所有地址字段的字典
        """
        return {
            "full_address": self.full_address,
            "province": self.province,
            "city": self.city,
            "district": self.district,
            "street": self.street,
            "street_number": self.street_number,
            "community": self.community,
            "building": self.building,
            "unit": self.unit,
            "room": self.room,
            "reliability": self.reliability,
            "lat": self.lat,
            "lng": self.lng,
            "adcode": self.adcode
        }


class AddressMapping:
    """
    地址映射数据模型

    用于封装地址到物业公司和维修单位的映射关系。

    Attributes:
        community (str): 小区/社区名称，作为映射的关键字（可为空）
        street (Optional[str]): 街道/道路名称，用于辅助匹配
        property_company (str): 对应的物业公司名称
        maintenance_unit (str): 对应的维修单位名称（可为"MISS"）
        district (Optional[str]): 所属区县，用于辅助匹配
        city (Optional[str]): 所属城市，用于辅助匹配
    """
    community: str
    street: Optional[str]
    property_company: str
    maintenance_unit: str
    district: Optional[str]
    city: Optional[str]

    def __init__(self, community: str, property_company: str,
                 maintenance_unit: str, street: Optional[str] = None,
                 district: Optional[str] = None, city: Optional[str] = None):
        self.community = community
        self.street = street
        self.property_company = property_company
        self.maintenance_unit = maintenance_unit
        self.district = district
        self.city = city

    def to_dict(self):
        """
        将映射数据转换为字典格式

        Returns:
            dict: 包含所有字段的字典
        """
        return {
            "community": self.community,
            "street": self.street,
            "property_company": self.property_company,
            "maintenance_unit": self.maintenance_unit,
            "district": self.district,
            "city": self.city
        }


class AddressProcessingResult:
    """
    地址处理结果封装类

    用于统一封装地址处理的结果，包含解析后的地址信息和映射结果。

    Attributes:
        address_info (AddressInfo): 解析后的地址信息
        property_company (Optional[str]): 匹配到的物业公司名称
        maintenance_unit (Optional[str]): 匹配到的维修单位名称
        status (str): 处理状态，包括：
            - 'SUCCESS': 地址验证通过并成功映射
            - 'ERROR': 地址验证失败或处理过程中发生错误
            - 'MISS': 地址信息不完整或无法匹配到物业公司/维修单位
    """
    address_info: AddressInfo
    property_company: Optional[str]
    maintenance_unit: Optional[str]
    status: str

    def __init__(self, address_info: AddressInfo,
                 property_company: Optional[str] = None,
                 maintenance_unit: Optional[str] = None,
                 status: str = 'SUCCESS'):
        self.address_info = address_info
        self.property_company = property_company
        self.maintenance_unit = maintenance_unit
        self.status = status

    def is_success(self) -> bool:
        """
        判断地址处理是否成功

        Returns:
            bool: 处理成功返回 True，否则返回 False
        """
        return self.status == 'SUCCESS'

    def is_error(self) -> bool:
        """
        判断地址处理是否发生错误

        Returns:
            bool: 发生错误返回 True，否则返回 False
        """
        return self.status == 'ERROR'

    def is_missing(self) -> bool:
        """
        判断地址处理是否缺失信息

        Returns:
            bool: 缺失信息返回 True，否则返回 False
        """
        return self.status == 'MISS'

    def is_low_reliability(self) -> bool:
        """
        判断地址处理是否可信度较低

        Returns:
            bool: 可信度较低返回 True，否则返回 False
        """
        return self.status == 'LOW_RELIABILITY'

    def to_dict(self):
        """
        将处理结果转换为字典格式

        Returns:
            dict: 包含地址信息、物业公司、维修单位和状态的字典
        """
        return {
            "address_info": self.address_info.to_dict(),
            "property_company": self.property_company,
            "maintenance_unit": self.maintenance_unit,
            "status": self.status
        }