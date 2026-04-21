from langchain_core.documents import Document

from backend.doc_pipeline import DocPipeline


def test_is_resume_doc_detects_extended_keywords():
    pipeline = DocPipeline()

    text = """
    候选人信息
    项目介绍 负责智能体平台的需求分析与交付
    技能证书 拥有 PMP 与软考证书
    """

    assert pipeline._is_resume_doc(text) is True


def test_smart_split_handles_inline_resume_sections():
    pipeline = DocPipeline()
    resume_text = """
    张三 | 13800000000 | zhangsan@example.com
    5 年后端开发经验，求职方向为 AI 应用开发

    工作经历 2022.03-至今 就职于某科技公司，负责 AI 智能体平台研发。
    项目介绍 智能问答系统，面向企业知识库提供检索增强问答能力。
    项目职责 负责文档解析、向量索引、召回链路与接口设计。
    项目结果 检索召回率提升 20%，回答时延下降 30%。
    技能证书 熟悉 Python、FastAPI、LangChain，持有软考中级证书。
    自我评价 沟通顺畅，推动力强，能够独立负责复杂项目。
    """.strip()

    chunks = pipeline._smart_split(
        [Document(page_content=resume_text, metadata={"source": "resume.docx"})]
    )

    assert len(chunks) >= 6
    assert chunks[0].metadata["chunk_type"] == "resume_header"
    assert all(
        chunk.metadata["chunk_type"] == "resume_section" for chunk in chunks[1:]
    )
    section_starts = [chunk.page_content.splitlines()[0] for chunk in chunks[1:]]

    assert any(text.startswith("项目介绍") for text in section_starts)
    assert any(text.startswith("技能证书") for text in section_starts)
    assert any(text.startswith("自我评价") for text in section_starts)
    assert not any(text.startswith("证书") for text in section_starts)
