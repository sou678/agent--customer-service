"""Agent 主逻辑：LangGraph 编排"""
import json
import operator
import asyncio
import aiosqlite
import sqlite3
from typing import Literal, Annotated, TypedDict
from langchain.chat_models import init_chat_model
from langchain.messages import AnyMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from tools import tools

DB_PATH = "agent_memory.db"
agent=None

# TODO 1: 定义 MessagesState（messages 字段）
class MessagesState(TypedDict):
    messages:Annotated[list[AnyMessage],operator.add]

# TODO 2: 读 config.json，初始化模型，bind_tools
with open("config.json","r",encoding="utf-8") as f:
    config=json.load(f)

model=init_chat_model(
    model=config["model"],
    api_key=config["api_key"],
    base_url=config["base_url"],
    temperature=0  #减少随机性
)

model_with_tool=model.bind_tools(tools)
#包装为tool_node节点
tool_node=ToolNode(tools)

# TODO 3: llm_call 节点（调 LLM）
def llm_call(state):
    #invoke调用
    response=model_with_tool.invoke(state["messages"])
    return {"messages":[response]}

# TODO 4: should_continue（判断是否调工具）
def should_continue(state):
    #取最后一条messasge的tool_call
    if state["messages"][-1].tool_calls:
        return "tool_node"
    return END

# TODO 5: 组装 graph（节点 + 边）
#建graph
graph=StateGraph(MessagesState)
#建node
graph.add_node("llm_call",llm_call)
graph.add_node("tool_node",tool_node)
#建edge
graph.add_edge(START,"llm_call")
graph.add_conditional_edges("llm_call",should_continue,["tool_node",END])
graph.add_edge("tool_node","llm_call")

# TODO 6: ask() 异步函数（供 main 调用）
async def ask(thread_id:str,query:str):
    result = await agent.ainvoke(
        {"messages":[HumanMessage(content=query)]},
        config={"configurable": {"thread_id":thread_id}}
    )
    return result["messages"][-1]

# TODO 7: main() 初始化 + CLI 循环
async def main():
    global agent
    #连接数据库
    conn = await aiosqlite.connect(DB_PATH)
    #编译图，持久化记忆
    agent = graph.compile(checkpointer=AsyncSqliteSaver(conn))
    user_id = 1
    try:
        while True:
            q = input("================================== Human Message ==================================\n")
            if q == "exit":
                break
            elif q == "shift":
                user_id = int(input("请输入用户序号："))
                print(f"已切换至 {user_id} 号用户！")
                continue
            elif q == "show":
                print(f"当前为 {user_id} 号用户！")
                continue
            elif q == "clear":
                sync_conn = sqlite3.connect(DB_PATH)
                with sync_conn:
                    sync_conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (str(user_id),))
                    sync_conn.execute("DELETE FROM writes WHERE thread_id = ?", (str(user_id),))
                sync_conn.close()
                print(f"已清空 {user_id} 号用户的记忆")
                continue
            elif q == "clear_all":
                sync_conn = sqlite3.connect(DB_PATH)
                with sync_conn:
                    sync_conn.execute("DELETE FROM checkpoints")
                    sync_conn.execute("DELETE FROM writes")
                sync_conn.close()
                print("已清空所有用户的记忆")
                continue
            m = await ask(str(user_id), q)
            m.pretty_print()
    finally:
        await conn.close()
if __name__ == "__main__":
    asyncio.run(main())