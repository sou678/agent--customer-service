"""工具定义：Agent 可调用的工具"""
import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
from langchain.tools import tool
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from db.connection import db_query_one
from langchain_community.tools import TavilySearchResults
import json

with open("data/messages.txt", "r", encoding="UTF-8") as f:
    raw = f.read()
KNOWLEDGE=[line.strip() for line in raw.split("\n") if line.strip()]

with open("config/config.json","r",encoding="utf-8") as f:
    config=json.load(f)

# 联网搜索工具
search_web = TavilySearchResults(
    max_results=3,
    tavily_api_key=config["tavily_api_key"],   # 建议放 config 或环境变量
)

embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-zh-v1.5")
# 建向量库（内存版，每次运行重建）
vectorstore = Chroma.from_texts(
    texts=KNOWLEDGE,
    embedding=embeddings,
    collection_name="company_kb",
)

# TODO 1: query_order —— 查订单
@tool
def query_order(order_id: str) -> str:
    """查询订单"""          
    return db_query_one("select * from orders where order_id=%s",(order_id,))      # 用 db_query_one 查 orders 表

# TODO 2: search_knowledge —— RAG 检索
@tool
def search_knowledge(query: str) -> str:
    """搜索用户个人信息，如性别，联系方式等等"""
    docs = vectorstore.similarity_search(query, k=3)
    if not docs:
        return "知识库中未找到相关内容。"
    return "\n\n---\n\n".join(d.page_content for d in docs)


# 工具列表（导出）
tools = [query_order, search_knowledge, search_web]

