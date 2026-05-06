#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SmartJobHunter 简历文本抽取模块。

本模块只负责从 txt、md、docx、pdf、图片文件中提取原始文本或可交给
Agent 处理的占位信息。结构化候选人画像由当前 Claude/Codex agent 根据
prompts/build_candidate_profile.md 生成，不由 Python 假装完成。
"""

import os
import hashlib
from pathlib import Path
from typing import Dict, Optional


def parse_resume(file_path: str) -> Dict:
    """解析简历文件，返回结构化信息

    Args:
        file_path: 简历文件路径

    Returns:
        {
            'content': 简历文本内容,
            'format': 文件格式,
            'hash': 内容哈希,
            'length': 内容长度
        }
    """
    if not os.path.exists(file_path):
        return {
            'content': f"[错误] 文件不存在: {file_path}",
            'format': None,
            'hash': None,
            'length': 0
        }

    ext = Path(file_path).suffix.lower()
    content = _parse_by_format(file_path, ext)

    if content.startswith("[错误]"):
        return {
            'content': content,
            'format': ext,
            'hash': None,
            'length': 0
        }

    return {
        'content': content,
        'format': ext,
        'hash': hashlib.md5(content.encode()).hexdigest()[:8],
        'length': len(content)
    }


def _parse_by_format(file_path: str, ext: str) -> str:
    """根据格式解析文件

    Args:
        file_path: 文件路径
        ext: 文件扩展名

    Returns:
        文件内容
    """
    parsers = {
        '.txt': _parse_txt,
        '.md': _parse_txt,
        '.docx': _parse_docx,
        '.pdf': _parse_pdf,
        '.png': _parse_image,
        '.jpg': _parse_image,
        '.jpeg': _parse_image,
    }

    parser = parsers.get(ext)
    if parser:
        return parser(file_path)
    else:
        return f"[错误] 不支持的文件格式: {ext}，支持: {list(parsers.keys())}"


def _parse_txt(file_path: str) -> str:
    """解析 txt/md 文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def _parse_docx(file_path: str) -> str:
    """解析 docx 文件"""
    try:
        from docx import Document
        doc = Document(file_path)
        text = []
        for para in doc.paragraphs:
            text.append(para.text)
        return '\n'.join(text)
    except ImportError:
        return "[错误] 需要安装 python-docx: pip install python-docx"
    except Exception as e:
        return f"[错误] 解析docx失败: {e}"


def _parse_pdf(file_path: str) -> str:
    """解析 pdf 文件"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        text = []
        for page in doc:
            text.append(page.get_text())
        return '\n'.join(text)
    except ImportError:
        return "[错误] 需要安装 PyMuPDF: pip install PyMuPDF"
    except Exception as e:
        return f"[错误] 解析pdf失败: {e}"


def _parse_image(file_path: str) -> str:
    """返回图片占位符，实际视觉解析由当前 Agent 平台完成。"""
    try:
        # 读取图片文件并编码
        import base64
        with open(file_path, 'rb') as f:
            image_data = f.read()

        # 返回 base64 编码的图片数据，供 Agent 处理
        encoded = base64.b64encode(image_data).decode('utf-8')
        ext = Path(file_path).suffix.lower()
        mime_type = 'image/png' if ext in ['.png'] else 'image/jpeg'

        return f"[IMAGE:{mime_type}:{encoded[:50]}...]"
    except Exception as e:
        return f"[错误] 读取图片失败: {e}"


def list_resumes(resume_dir: str = "./resumes") -> list:
    """列出简历目录中的所有简历文件

    Args:
        resume_dir: 简历目录路径

    Returns:
        简历文件列表
    """
    resume_path = Path(resume_dir)
    if not resume_path.exists():
        return []

    supported_ext = ['.txt', '.md', '.docx', '.pdf', '.png', '.jpg', '.jpeg']
    resumes = []

    for file in resume_path.iterdir():
        if file.is_file() and file.suffix.lower() in supported_ext:
            # 跳过示例文件
            if file.name.startswith('example_'):
                continue
            resumes.append({
                'name': file.stem,
                'path': str(file),
                'format': file.suffix.lower()
            })

    return resumes


def get_resume_info(file_path: str) -> Dict:
    """获取简历信息

    Args:
        file_path: 简历文件路径

    Returns:
        {
            'path': 文件路径,
            'format': 文件格式,
            'content': 简历内容,
            'length': 内容长度,
            'hash': 内容哈希
        }
    """
    result = parse_resume(file_path)
    result['path'] = file_path
    return result
