#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SmartJobHunter 配置驱动爬虫测试
"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.crawler_factory import (
    get_company_config,
    create_crawler,
    get_enabled_companies,
    crawl_company,
    select_strategy_type,
)
from src.config_crawler import ConfigCrawler
from src.base_crawler import BaseCrawler, InterceptCrawler
from src.exceptions import CompanyNotFoundError


class TestCompanyConfig:
    """测试公司配置"""

    def test_get_tencent_config(self):
        """测试获取腾讯配置"""
        config = get_company_config('tencent')
        assert config is not None
        assert config['name'] == '腾讯'
        assert 'field_mappings' in config
        assert 'api' in config

    def test_get_bytedance_config(self):
        """测试获取字节跳动配置"""
        config = get_company_config('bytedance')
        assert config is not None
        assert config['name'] == '字节跳动'
        assert 'field_mappings' in config

    def test_get_meituan_config(self):
        """测试获取美团配置"""
        config = get_company_config('meituan')
        assert config is not None
        assert 'field_mappings' in config

    def test_get_invalid_config(self):
        """测试获取不存在的公司配置"""
        config = get_company_config('invalid_company')
        assert config is None

    def test_get_enabled_companies(self):
        """测试获取启用的公司列表"""
        companies = get_enabled_companies()
        assert len(companies) >= 3  # 至少有腾讯、字节、美团

        # 检查所有返回的公司都有 field_mappings
        for company in companies:
            if 'field_mappings' in company:
                assert company['enabled'] == True

    def test_get_enabled_companies_skips_strategy_problem_ids(self, monkeypatch):
        monkeypatch.setenv("SMARTHUNTER_SKIP_COMPANIES", "tencent,meituan")

        companies = get_enabled_companies("social")
        company_ids = {company.get("id") for company in companies}

        assert "tencent" not in company_ids
        assert "meituan" not in company_ids


class TestCrawlerCreation:
    """测试爬虫创建"""

    def test_create_tencent_crawler(self):
        """测试创建腾讯爬虫"""
        crawler = create_crawler('tencent')
        assert crawler is not None
        assert isinstance(crawler, ConfigCrawler)
        assert crawler.company_name == '腾讯'

    def test_create_bytedance_crawler(self):
        """测试创建字节跳动爬虫"""
        crawler = create_crawler('bytedance')
        assert crawler is not None
        assert crawler.company_name == '字节跳动'

    def test_create_meituan_crawler(self):
        """测试创建美团爬虫"""
        crawler = create_crawler('meituan')
        assert crawler is not None
        assert crawler.company_name == '美团'

    def test_create_invalid_crawler(self):
        """测试创建无效公司的爬虫"""
        with pytest.raises(CompanyNotFoundError):
            create_crawler('invalid_company')

    def test_config_intercept_strategy_uses_config_crawler(self):
        company = {
            "strategy": {"type": "config_intercept"},
            "api": {"type": "intercept"},
        }

        assert select_strategy_type(company) == "config"

    def test_legacy_python_strategy_is_preserved(self):
        company = {"strategy": {"type": "legacy_python"}}

        assert select_strategy_type(company) == "legacy_python"

    def test_custom_python_strategy_is_routed(self):
        company = {"id": "special", "strategy": {"type": "custom_python", "module": "special"}}

        assert select_strategy_type(company) == "custom_python"


class TestFieldParsing:
    """测试字段解析"""

    def test_parse_simple_field(self):
        """测试解析简单字段"""
        config = get_company_config('tencent')
        crawler = create_crawler('tencent')

        item = {'RecruitPostName': '产品经理', 'LocationName': '深圳'}
        mapping = {'source': 'RecruitPostName'}

        result = crawler.parse_field(item, mapping)
        assert result == '产品经理'

    def test_parse_nested_field(self):
        """测试解析嵌套字段"""
        config = get_company_config('bytedance')
        crawler = create_crawler('bytedance')

        item = {
            'city_info': {'name': '北京'},
            'job_category': {'name': '产品'}
        }

        result = crawler.parse_field(item, {'source': 'city_info.name'})
        assert result == '北京'

    def test_parse_missing_field_with_default(self):
        """测试解析缺失字段使用默认值"""
        config = get_company_config('tencent')
        crawler = create_crawler('tencent')

        item = {}
        mapping = {'source': 'NonExistent', 'default': '默认值'}

        result = crawler.parse_field(item, mapping)
        assert result == '默认值'


class TestJobTypeDetection:
    """测试岗位类型检测"""

    def test_detect_internship(self):
        """测试检测实习岗位"""
        config = get_company_config('tencent')
        crawler = create_crawler('tencent')

        assert crawler.detect_job_type('产品实习生') == 'internship'
        assert crawler.detect_job_type('Intern产品') == 'internship'

    def test_detect_campus(self):
        """测试检测校招岗位"""
        config = get_company_config('tencent')
        crawler = create_crawler('tencent')

        assert crawler.detect_job_type('校招产品经理') == 'campus'
        assert crawler.detect_job_type('应届生产品') == 'campus'

    def test_detect_social(self):
        """测试检测社招岗位"""
        config = get_company_config('tencent')
        crawler = create_crawler('tencent')

        assert crawler.detect_job_type('高级产品经理') == 'social'
        assert crawler.detect_job_type('产品总监') == 'social'


class TestCrawlIntegration:
    """集成测试 - 需要网络连接"""

    @pytest.mark.integration
    def test_crawl_tencent(self):
        """测试爬取腾讯岗位"""
        jobs = crawl_company('tencent', '产品经理', max_jobs=5)
        assert len(jobs) > 0
        assert jobs[0]['company'] == '腾讯'
        assert jobs[0]['title'] != ''
        assert jobs[0]['url'] != ''

    @pytest.mark.integration
    def test_crawl_bytedance(self):
        """测试爬取字节跳动岗位"""
        jobs = crawl_company('bytedance', '产品经理', max_jobs=5, job_type='campus')
        assert len(jobs) > 0
        assert jobs[0]['company'] == '字节跳动'

    @pytest.mark.integration
    def test_crawl_meituan(self):
        """测试爬取美团岗位"""
        jobs = crawl_company('meituan', '产品经理', max_jobs=5)
        assert len(jobs) > 0
        assert jobs[0]['company'] == '美团'


if __name__ == '__main__':
    # 运行测试
    pytest.main([__file__, '-v', '--tb=short'])
