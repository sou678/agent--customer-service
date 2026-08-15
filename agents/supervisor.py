"""Agent 主逻辑：LangGraph 编排"""
import json
import operator
import aiosqlite
from langchain.tools import tool
from typing import Literal, Annotated, TypedDict
from langchain.chat_models import init_chat_model
from langchain.messages import AnyMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from agents.sub_agents import order_agent, knowledge_agent, search_agent
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

DB_PATH = "agent_memory.db"

# TODO 1: 定义 MessagesState（messages 字段）
class SupervisorState(TypedDict):
    messages:Annotated[list[AnyMessage],operator.add]

# TODO 2: 读 config.json，初始化模型，bind_tools
with open("config/config.json","r",encoding="utf-8") as f:
    config=json.load(f)

model=init_chat_model(
    model=config["model"],
    api_key=config["api_key"],
    base_url=config["base_url"],
    temperature=0  #减少随机性
)

# TODO 3: 三个路由工具
@tool
def route_to_order(question: str) -> str:
    """订单相关问题，转给订单专家。"""
    return "order_agent"
@tool
def route_to_knowledge(question: str) -> str:
    """公司政策、产品信息问题，转给知识专家。"""
    return "knowledge_agent"
@tool
def route_to_search(question: str) -> str:
    """实时信息、新闻等问题，转给搜索专家。"""
    return "search_agent"

# TODO 4: Supervisor 节点（LLM + 路由工具）
async def supervisor_node(state):
    supervisor_llm=model.bind_tools([route_to_order,route_to_knowledge,route_to_search])
    response=await supervisor_llm.ainvoke(state["messages"])
    return {"messages":[response]}

# TODO 5: 条件路由
def route(state):
    last = state["messages"][-1]
    if last.tool_calls:
        tool_name = last.tool_calls[0]["name"]
        if tool_name == "route_to_order":
            return "order_agent"
        elif tool_name == "route_to_knowledge":
            return "knowledge_agent"
        elif tool_name == "route_to_search":
            return "search_agent"
    return END

# TODO 6: 组装 graph（节点 + 边）
#建graph
graph = StateGraph(SupervisorState)
#建node
graph.add_node("supervisor_node",supervisor_node)
graph.add_node("order_agent",order_agent)
graph.add_node("knowledge_agent",knowledge_agent)
graph.add_node("search_agent",search_agent)
#建edge
graph.add_edge(START,"supervisor_node")
graph.add_conditional_edges("supervisor_node",route,{
    "order_agent":"order_agent",
    "knowledge_agent":"knowledge_agent",
    "search_agent":"search_agent",
    END:END
    }
)
graph.add_edge("order_agent", END)
graph.add_edge("knowledge_agent", END)
graph.add_edge("search_agent", END)

async def init_supervisor():
    conn = await aiosqlite.connect(DB_PATH)
    return graph.compile(checkpointer=AsyncSqliteSaver(conn)), conn

# TODO 6: ask() 异步函数（供 main 调用）
async def ask(supervisor,thread_id:str,query:str):
    result = await supervisor.ainvoke(
        {"messages":[HumanMessage(content=query)]},
        config={"configurable": {"thread_id": thread_id}},
    )
    return result["messages"][-1]
