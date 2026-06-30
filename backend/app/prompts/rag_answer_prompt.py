RAG_SYSTEM_PROMPT = """你是一个严谨的企业知识库问答助手。
你必须只根据给定资料回答问题。如果资料中没有足够依据，请明确回答：“知识库中没有找到足够依据，无法确认。”
不要编造时间、数字、政策、人名、文件名。回答应结构清晰，涉及关键结论时必须引用资料编号，如 [1]。
最后必须输出“参考来源”，且只列出实际使用过的资料。"""

RAG_USER_TEMPLATE = """{context}

用户问题：
{question}

请按以下格式回答：
直接回答：
...

依据说明：
...

参考来源：
[1] 文件名，第 x 页
"""


def build_rag_prompt(question: str, sources: list[dict]) -> str:
    blocks: list[str] = []
    for index, source in enumerate(sources, 1):
        page = source.get("page")
        page_text = f"第 {page} 页" if page else "页码未知"
        blocks.append(
            f"【资料 {index}】\n来源：{source['file_name']}，{page_text}，chunk_id={source['chunk_id']}\n"
            f"内容：{source['content']}"
        )
    return RAG_USER_TEMPLATE.format(context="\n\n".join(blocks), question=question)
