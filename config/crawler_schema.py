#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SmartJobHunter 爬虫配置 Schema
定义配置驱动的爬虫配置结构
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any


@dataclass
class FieldMapping:
    """字段映射配置

    定义如何从原始数据中提取字段值

    Attributes:
        source: 源字段路径，支持点号访问如 "city_info.name"
        default: 默认值，当源字段不存在时使用
        transform: 转换函数名，如 "timestamp_to_date"
    """
    source: str
    default: Optional[str] = None
    transform: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'source': self.source,
            'default': self.default,
            'transform': self.transform,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'FieldMapping':
        return cls(
            source=data.get('source', ''),
            default=data.get('default'),
            transform=data.get('transform'),
        )


@dataclass
class APIConfig:
    """API 配置

    定义如何从网页中捕获 API 数据

    Attributes:
        pattern: URL 匹配模式，如 "tencentcareer/api/post/Query"
        data_path: 数据提取路径，如 "Data.Posts"
        method: 获取方式 - intercept(拦截) | request(直接请求) | ssr(服务端渲染)
    """
    pattern: str
    data_path: str
    method: str = "intercept"

    def to_dict(self) -> dict:
        return {
            'pattern': self.pattern,
            'data_path': self.data_path,
            'method': self.method,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'APIConfig':
        return cls(
            pattern=data.get('pattern', ''),
            data_path=data.get('data_path', ''),
            method=data.get('type', data.get('method', 'intercept')),
        )


@dataclass
class CompanyCrawlerConfig:
    """公司爬虫完整配置

    Attributes:
        id: 公司唯一标识
        name: 公司名称
        api: API 配置
        field_mappings: 字段映射字典 {目标字段: FieldMapping}
        url_template: 岗位详情页 URL 模板，支持 {id} 占位符
        urls: 不同岗位类型的 URL 模板
        job_type_detection: 岗位类型检测关键词
        enabled: 是否启用
        note: 备注
    """
    id: str
    name: str
    api: APIConfig
    field_mappings: Dict[str, FieldMapping]
    url_template: str
    urls: Dict[str, str] = field(default_factory=dict)
    job_type_detection: Dict[str, List[str]] = field(default_factory=dict)
    enabled: bool = True
    note: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'api': self.api.to_dict(),
            'field_mappings': {k: v.to_dict() for k, v in self.field_mappings.items()},
            'url_template': self.url_template,
            'urls': self.urls,
            'job_type_detection': self.job_type_detection,
            'enabled': self.enabled,
            'note': self.note,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'CompanyCrawlerConfig':
        # 解析 API 配置
        api_data = data.get('api', {})
        api = APIConfig.from_dict(api_data)

        # 解析字段映射
        field_mappings = {}
        for field_name, mapping_data in data.get('field_mappings', {}).items():
            if isinstance(mapping_data, dict):
                field_mappings[field_name] = FieldMapping.from_dict(mapping_data)
            elif isinstance(mapping_data, str):
                # 简化配置：直接写字段名
                field_mappings[field_name] = FieldMapping(source=mapping_data)

        # URL 模板：优先使用 url_template，否则从 urls 推断
        url_template = data.get('url_template', '')
        if not url_template:
            # 尝试从 field_mappings 中推断
            if 'id' in field_mappings:
                url_template = f"https://example.com/job/{{id}}"

        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            api=api,
            field_mappings=field_mappings,
            url_template=url_template,
            urls=data.get('urls', {}),
            job_type_detection=data.get('job_type_detection', {}),
            enabled=data.get('enabled', True),
            note=data.get('note'),
        )


def load_company_configs(yaml_path: str) -> List[CompanyCrawlerConfig]:
    """从 YAML 文件加载所有公司配置

    Args:
        yaml_path: YAML 配置文件路径

    Returns:
        公司配置列表
    """
    import yaml
    from pathlib import Path

    config_path = Path(yaml_path)
    if not config_path.exists():
        return []

    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    configs = []
    for company_data in data.get('companies', []):
        try:
            config = CompanyCrawlerConfig.from_dict(company_data)
            configs.append(config)
        except Exception as e:
            print(f"[Warn] Failed to parse company config: {company_data.get('id', 'unknown')}: {e}")

    return configs


if __name__ == '__main__':
    # 测试加载配置
    import sys
    from pathlib import Path

    config_file = Path(__file__).parent.parent / 'companies.yaml'
    if config_file.exists():
        configs = load_company_configs(str(config_file))
        print(f"Loaded {len(configs)} company configs")
        for config in configs:
            if config.enabled and config.field_mappings:
                print(f"  - {config.name}: {len(config.field_mappings)} field mappings")
    else:
        print(f"Config file not found: {config_file}")
