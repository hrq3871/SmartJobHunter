#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Base interface for custom career-site strategies."""

from __future__ import annotations

from typing import Dict, List


class SiteStrategy:
    """Base class for hand-written crawler strategies."""

    company_id: str = ""

    def __init__(self, company_config: Dict):
        self.company_config = company_config
        self.company_id = str(company_config.get("id", ""))

    def crawl(
        self,
        keyword: str,
        max_jobs: int,
        job_type: str,
        headless: bool = True,
    ) -> List[dict]:
        raise NotImplementedError
