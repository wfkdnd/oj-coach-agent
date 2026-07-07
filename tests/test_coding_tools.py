"""第5章 测试：Coding Tools"""

import sys
import os
import tempfile
import shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from coding_tools.read import read_file
from coding_tools.write import write_file
from coding_tools.edit import edit_file
from coding_tools.list_dir import list_dir
from coding_tools.bash import bash


def test_read_file():
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
    tmp.write("line1\nline2\nline3\n")
    tmp.close()

    try:
        content = read_file(tmp.name)
        assert "1:" in content and "line1" in content, "应该有行号和内容"

        partial = read_file(tmp.name, offset=2, limit=1)
        assert "line2" in partial, "offset=2 应该从第二行开始"

        err = read_file("/nonexistent")
        assert "❌" in err or "不存在" in err, "不存在应该报错"
    finally:
        os.unlink(tmp.name)


def test_write_file():
    test_dir = tempfile.mkdtemp()
    try:
        path = os.path.join(test_dir, "test.txt")
        result = write_file(path, "hello")
        assert "✅" in result, "写新文件应该成功"
        assert open(path).read() == "hello"

        result = write_file(path, "new")
        assert "❌" in result or "已存在" in result, "默认不覆盖"

        result = write_file(path, "new", overwrite=True)
        assert "✅" in result, "overwrite=True 应该成功"
    finally:
        shutil.rmtree(test_dir)


def test_edit_file():
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
    tmp.write("def hello():\n    return 'world'\n")
    tmp.close()

    try:
        result = edit_file(tmp.name, "return 'world'", "return 'hello'")
        assert "✅" in result or "成功" in result, f"编辑应该成功: {result}"
        assert "hello" in open(tmp.name).read(), "内容应该被替换"

        result = edit_file(tmp.name, "not_exist_content", "new")
        assert "❌" in result or "未找到" in result, "找不到应该报错"
    finally:
        os.unlink(tmp.name)


def test_list_dir():
    test_dir = tempfile.mkdtemp()
    try:
        open(os.path.join(test_dir, "a.txt"), "w").close()
        os.mkdir(os.path.join(test_dir, "subdir"))

        result = list_dir(test_dir)
        assert "a.txt" in result, "应该列出文件"
        assert "subdir" in result, "应该列出目录"
    finally:
        shutil.rmtree(test_dir)


def test_bash():
    result = bash("echo hello")
    assert "hello" in result, f"echo 应该输出 hello: {result}"

    result = bash("rm -rf /")
    assert "❌" in result or "拒绝" in result, "危险命令应该被拦截"

    result = bash("sleep 100", timeout=1)
    assert "❌" in result or "超时" in result, "应该超时"


if __name__ == "__main__":
    test_read_file()
    print("  ✓ test_read_file")
    test_write_file()
    print("  ✓ test_write_file")
    test_edit_file()
    print("  ✓ test_edit_file")
    test_list_dir()
    print("  ✓ test_list_dir")
    test_bash()
    print("  ✓ test_bash")
    print("\n✅ 第5章 Coding Tools 全部测试通过")
