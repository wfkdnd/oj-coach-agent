"""第4章 测试：Memory"""

import sys
import os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm import LLMClient
from memory import Memory


def test_add_and_search():
    llm = LLMClient()
    mem = Memory(llm=llm)

    mem.add("用户喜欢吃辣，不吃鱼")
    mem.add("用户下周去杭州出差")
    mem.add("用户对花粉过敏")

    results = mem.search("饮食偏好", k=2)
    assert len(results) == 2, f"应该返回 2 条，实际: {len(results)}"
    assert results[0][0] >= results[1][0], "应该按相似度降序"
    # 最相关的应该是饮食相关
    assert "辣" in results[0][1] or "鱼" in results[0][1], (
        f"饮食查询应该匹配饮食记忆，实际: {results[0][1]!r}"
    )


def test_cosine_similarity():
    llm = LLMClient()
    mem = Memory(llm=llm)

    sim = mem._cosine_similarity([1, 0, 0], [1, 0, 0])
    assert abs(sim - 1.0) < 0.01, f"相同向量应该是 1，实际: {sim}"

    sim2 = mem._cosine_similarity([1, 0], [0, 1])
    assert abs(sim2) < 0.01, f"正交向量应该是 0，实际: {sim2}"


def test_save_load():
    llm = LLMClient()
    mem = Memory(llm=llm)
    mem.add("测试记忆")

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()

    try:
        mem.save(tmp.name)
        assert os.path.exists(tmp.name), "文件应该被创建"

        mem2 = Memory(llm=llm)
        mem2.load(tmp.name)
        assert len(mem2._entries) == 1, "加载后应该有 1 条记忆"
        assert mem2._entries[0][0] == "测试记忆", "文本应该保持一致"
    finally:
        os.unlink(tmp.name)


if __name__ == "__main__":
    test_cosine_similarity()
    print("  ✓ test_cosine_similarity")
    test_add_and_search()
    print("  ✓ test_add_and_search")
    test_save_load()
    print("  ✓ test_save_load")
    print("\n✅ 第4章 Memory 全部测试通过")
