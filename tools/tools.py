"""工具定义：Agent 可调用的工具"""
import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
from langchain.tools import tool
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from db.connection import db_query_one
from langchain_community.tools import TavilySearchResults
from db.connection import db_query_one, db_execute
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
# ===== 订单 CRUD 工具 =====
@tool
def query_order(order_id: str) -> str:
    """根据订单号查询订单信息，包括客户名、商品、金额、状态、下单日期。"""
    row = db_query_one(
        "SELECT customer_name, product, amount, status, created_at FROM orders WHERE order_id = %s",
        (order_id,),
    )
    if not row:
        return f"未找到订单 {order_id}"
    name, product, amount, status, date = row
    return f"订单{order_id}：客户={name}，商品={product}，金额={amount}元，状态={status}，下单日期={date}"
@tool
def create_order(order_id: str, customer_name: str, product: str, amount: float, status: str) -> str:
    """创建新订单，记录订单号、客户名、商品、金额、状态。"""
    rows = db_execute(
        "INSERT INTO orders (order_id, customer_name, product, amount, status, created_at) VALUES (%s, %s, %s, %s, %s, NOW())",
        (order_id, customer_name, product, amount, status),
    )
    if rows:
        return f"订单 {order_id} 创建成功"
    return "创建失败"
@tool
def update_order(order_id: str, customer_name: str = None, product: str = None, amount: float = None, status: str = None) -> str:
    """修改订单信息。可修改客户名、商品、金额、状态，传哪些字段就改哪些。"""
    updates = []
    params = []
    if customer_name:
        updates.append("customer_name = %s")
        params.append(customer_name)
    if product:
        updates.append("product = %s")
        params.append(product)
    if amount is not None:
        updates.append("amount = %s")
        params.append(amount)
    if status:
        updates.append("status = %s")
        params.append(status)
    if not updates:
        return "没有提供要修改的字段"
    params.append(order_id)
    sql = f"UPDATE orders SET {', '.join(updates)} WHERE order_id = %s"
    rows = db_execute(sql, tuple(params))
    if rows:
        return f"订单 {order_id} 修改成功"
    return f"未找到订单 {order_id}"
@tool
def delete_order(order_id: str) -> str:
    """删除指定订单。此操作不可恢复，需谨慎。"""
    rows = db_execute(
        "DELETE FROM orders WHERE order_id = %s",
        (order_id,),
    )
    if rows:
        return f"订单 {order_id} 已删除"
    return f"未找到订单 {order_id}"

# TODO 2: search_knowledge —— RAG 检索
@tool
def search_knowledge(query: str) -> str:
    """搜索用户个人相关信息，如性别，姓名，联系方式等等"""
    docs = vectorstore.similarity_search(query, k=3)
    if not docs:
        return "知识库中未找到相关内容。"
    return "\n\n---\n\n".join(d.page_content for d in docs)


# 工具列表（导出）
tools = [query_order, create_order, update_order, delete_order, search_knowledge, search_web]

