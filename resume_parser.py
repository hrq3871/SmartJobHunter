#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简历解析模块
支持多种格式：txt, md, docx, pdf
"""

import os
from pathlib import Path


def parse_txt(file_path: str) -> str:
    """解析 txt/md 文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def parse_md(file_path: str) -> str:
    """解析 markdown 文件"""
    return parse_txt(file_path)


def parse_docx(file_path: str) -> str:
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


def parse_pdf(file_path: str) -> str:
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


def parse_resume(file_path: str) -> str:
    """
    根据文件扩展名解析简历

    Args:
        file_path: 简历文件路径

    Returns:
        简历文本内容
    """
    if not os.path.exists(file_path):
        return f"[错误] 文件不存在: {file_path}"

    ext = Path(file_path).suffix.lower()

    parsers = {
        '.txt': parse_txt,
        '.md': parse_md,
        '.docx': parse_docx,
        '.pdf': parse_pdf,
    }

    parser = parsers.get(ext)
    if parser:
        return parser(file_path)
    else:
        return f"[错误] 不支持的文件格式: {ext}，支持: {list(parsers.keys())}"


def get_resume_info(file_path: str) -> dict:
    """
    获取简历信息

    Returns:
        {
            'path': 文件路径,
            'format': 文件格式,
            'content': 简历内容,
            'length': 内容长度
        }
    """
    content = parse_resume(file_path)
    ext = Path(file_path).suffix.lower()

    return {
        'path': file_path,
        'format': ext,
        'content': content,
        'length': len(content)
    }


def list_resumes(resume_dir: str = "./resumes") -> list:
    """
    列出简历目录中的所有简历文件

    Returns:
        简历文件列表
    """
    resume_path = Path(resume_dir)
    if not resume_path.exists():
        return []

    supported_ext = ['.txt', '.md', '.docx', '.pdf']
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


if __name__ == "__main__":
    # 测试
    print("支持的简历格式: txt, md, docx, pdf")
    print("\n当前简历列表:")
    for resume in list_resumes():
        print(f"  - {resume['name']} ({resume['format']})")
