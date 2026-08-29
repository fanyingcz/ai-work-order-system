"""
地址处理模块 - 包初始化文件

【模块职责】
负责处理用户输入的地址信息，包括地址验证、解析和映射到物业公司及维修单位。

【核心功能】
1. 调用腾讯地图API验证地址的真实性和完整性
2. 解析地址字符串，提取省、市、区、街道、门牌、小区、楼栋等层级信息
3. 根据解析后的小区名称，映射到对应的物业公司和维修单位
4. 支持精确匹配和模糊匹配两种地址映射方式

【模块结构】
├── models.py      # 数据模型定义（AddressInfo, AddressMapping, AddressProcessingResult）
├── handler.py     # 核心处理逻辑（AddressHandler 类）
└── __init__.py    # 模块导出声明

【对外接口】
- AddressInfo: 地址信息数据模型（包含 district、street、street_number、reliability 等字段）
- AddressMapping: 地址映射数据模型
- AddressProcessingResult: 地址处理结果封装类
- AddressHandler: 地址处理器，提供 process() 方法

【状态标识】
- SUCCESS: 地址验证通过（可信度>=7），成功解析并映射到物业公司和维修单位
- ERROR: 地址验证失败或处理过程中发生错误
- MISS: 地址信息不完整或无法匹配到物业公司/维修单位
- LOW_RELIABILITY: 地址解析可信度较低（<7），需要人工确认

【数据依赖】
- data/rules/address_mapping.json: 地址映射数据，包含小区到物业公司和维修单位的对应关系

【环境变量】
- lbs_key: 腾讯地图API Key
- lbs_ws_sk: 腾讯地图Web Service Secret Key
"""

from .models import AddressInfo, AddressMapping, AddressProcessingResult
from .handler import AddressHandler

__all__ = ['AddressInfo', 'AddressMapping', 'AddressProcessingResult', 'AddressHandler']