#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SmartJobHunter 自定义异常类"""


class HunterError(Exception):
    """基础异常类"""
    pass


class ConfigError(HunterError):
    """配置错误"""
    pass


class ProfileNotFoundError(ConfigError):
    """意向配置未找到"""
    pass


class CompanyNotFoundError(ConfigError):
    """公司配置未找到"""
    pass


class CrawlerError(HunterError):
    """爬虫错误"""
    pass


class NetworkError(CrawlerError):
    """网络错误"""
    pass


class ParseError(CrawlerError):
    """解析错误"""
    pass


class CDPError(CrawlerError):
    """CDP 连接错误"""
    pass
