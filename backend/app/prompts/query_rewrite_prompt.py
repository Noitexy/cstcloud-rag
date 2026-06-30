QUERY_REWRITE_SYSTEM_PROMPT = """你是企业知识库检索查询改写器。结合对话历史，把用户当前问题改写成一个信息完整、适合向量和关键词检索的独立查询。
只输出改写后的查询，不要解释，不要回答问题，不要添加资料中不存在的事实。"""


def build_query_rewrite_prompt(question: str, history: list[dict[str, str]]) -> str:
    recent = history[-6:]
    history_text = "\n".join(f"{item['role']}: {item['content'][:1000]}" for item in recent) or "（无）"
    return f"对话历史：\n{history_text}\n\n当前问题：{question}\n\n独立检索查询："
