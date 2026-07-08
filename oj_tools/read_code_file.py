"""
读取完整 OJ 代码。

支持两种来源：
- 直接粘贴完整代码。
- 从 .py / .cpp / .java 文件读取代码。
"""

from __future__ import annotations

from pathlib import Path
import json


SUPPORTED_CODE_EXTENSIONS = {".py", ".cpp", ".java"}
TEXT_ENCODINGS = ("utf-8", "utf-8-sig", "gb18030")
LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".cpp": "cpp",
    ".java": "java",
}
LANGUAGE_ALIASES = {
    "py": "python",
    "python": "python",
    "python3": "python",
    "cpp": "cpp",
    "c++": "cpp",
    "java": "java",
}


def read_code(code_text: str = "", file_path: str = "", language: str = "") -> str:
    """从粘贴文本或受支持的本地文件读取完整 OJ 代码。

    code_text 和 file_path 二选一即可。粘贴代码会以结构化文本返回，不会写入项目文件。
    """
    has_text = bool(code_text.strip())
    has_file = bool(file_path.strip())

    if has_text and has_file:
        return "错误：code_text 和 file_path 只能提供其中一个。"
    if has_text:
        normalized_language = _normalize_language(language)
        return _format_code_result(
            code=_normalize_code(code_text),
            language=normalized_language or "未知",
            source="粘贴文本",
            file_path="",
        )
    if has_file:
        return read_code_file(file_path)
    return "错误：请提供 code_text 或 file_path。"


def read_code_file(file_path: str) -> str:
    """从 .py、.cpp 或 .java 文件读取完整 OJ 代码，并根据扩展名推断语言。"""
    path = Path(file_path).expanduser()
    error = _validate_code_path(path)
    if error:
        return error

    code, read_error = _read_text_file(path)
    if read_error:
        return read_error

    return _format_code_result(
        code=code,
        language=LANGUAGE_BY_EXTENSION[path.suffix.lower()],
        source="文件",
        file_path=str(path),
    )


def _validate_code_path(path: Path) -> str:
    if not path.exists():
        return f"错误：文件不存在：{path}"
    if not path.is_file():
        return f"错误：路径不是文件：{path}"
    if path.suffix.lower() not in SUPPORTED_CODE_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_CODE_EXTENSIONS))
        return f"错误：不支持的代码文件类型 '{path.suffix}'。支持：{allowed}"
    return ""


def _read_text_file(path: Path) -> tuple[str, str]:
    last_error: Exception | None = None
    for encoding in TEXT_ENCODINGS:
        try:
            return _normalize_code(path.read_text(encoding=encoding)), ""
        except UnicodeDecodeError as exc:
            last_error = exc
    return "", f"错误：代码文件解码失败：{path}。原因：{last_error}"


def _normalize_language(language: str) -> str:
    return LANGUAGE_ALIASES.get(language.strip().lower(), "")


def _normalize_code(code: str) -> str:
    normalized = code.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.strip("\ufeff\n")


def _format_code_result(code: str, language: str, source: str, file_path: str) -> str:
    payload = {
        "source": source,
        "file_path": file_path,
        "language": language,
        "code": code,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
