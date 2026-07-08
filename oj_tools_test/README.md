# oj_tools 手动测试辅助

这个文件夹用于手动测试 `oj_tools`。

测试用例文件由你在运行时提供。辅助脚本不会创建、修改或删除你的样例文件。

## 可以看到什么

- `read_problem_file`：从 `.txt`、`.md` 或 `.docx` 读取题目文档。
- `read_code_file`：从 `.py`、`.cpp` 或 `.java` 读取 OJ 代码。
- `run_oj_code`：用你提供的输入运行读取到的代码，并可对比期望输出。

## PowerShell 示例

先设置测试用例输入：

```powershell
$env:OJ_PROBLEM_FILE = "C:\path\to\problem.md"
$env:OJ_CODE_FILE = "C:\path\to\main.py"
$env:OJ_STDIN = @"
1 2
"@
$env:OJ_EXPECTED_OUTPUT = @"
3
"@
```

作为普通脚本运行：

```powershell
python .\oj_tools_test\test_oj_tools_manual.py
```

脚本启动时会把标准输出和标准错误输出配置为 UTF-8，避免中文题目、中文注释和中文提示在 PowerShell 中显示成乱码。

也可以用 `pytest` 运行，并保留打印输出：

```powershell
pytest .\oj_tools_test -s
```

## 可选配置

- `OJ_LANGUAGE`：覆盖自动识别出的语言。支持 `python`、`cpp`、`java`。
- `OJ_STDIN_FILE`：从文件读取标准输入，而不是使用 `OJ_STDIN`。
- `OJ_EXPECTED_OUTPUT_FILE`：从文件读取期望输出，而不是使用 `OJ_EXPECTED_OUTPUT`。
- `OJ_TIMEOUT_MS`：运行超时时间，单位是毫秒。默认值是 `3000`。
- `OJ_REQUIRE_STATUS`：要求运行状态必须等于指定值，否则测试失败，例如 `accepted`。

## 安全提示

`run_oj_code` 会执行你提供的代码。请只使用可信的本地测试用例。
现有工具会把运行过程中的临时文件写到临时目录，而不是项目目录。
