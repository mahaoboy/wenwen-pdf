"""Prompt 模板：幻觉闸第一道防线——强制文档内作答。"""

SYSTEM_PROMPT = """你是「文问」，一个严谨的文档问答助手。规则：
1. 仅基于提供的【检索片段】回答，禁止使用任何文档外知识。
2. 每个关键结论后必须标注来源，格式：[来源:完整chunk_id]。chunk_id 见每个片段标题「【片段 4-c1｜第3页】」中的 "4-c1" 部分，必须一字不差地完整复制（含横杠前缀），例如 [来源:4-c1]。禁止只写编号。
3. 若检索片段不足以回答，必须回复"文档中未找到相关内容"，不得编造。
4. 回答用简体中文，简洁、准确、引用充分。"""


def build_messages(
    question: str,
    chunks: list[dict],
    history: list[tuple[str, str]],
) -> list[dict]:
    """组装多轮对话消息。history 为 [(user_msg, assistant_msg), ...]，仅取最近 3 轮。"""
    context = "\n\n".join(
        f"【片段 {c['chunk_id']}｜第{c['page']}页】\n{c['text']}" for c in chunks
    )
    msgs: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for user_msg, assistant_msg in history[-3:]:
        msgs.append({"role": "user", "content": user_msg})
        msgs.append({"role": "assistant", "content": assistant_msg})
    msgs.append(
        {
            "role": "user",
            "content": f"【检索片段】\n{context}\n\n【问题】\n{question}",
        }
    )
    return msgs
