"""FastAPI 部署：把 Agent 包装成 HTTP 服务"""
import json
import operator
import asyncio
import aiosqlite
from contextlib import asynccontextmanager
from typing import Literal, Annotated, TypedDict
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain.chat_models import init_chat_model
from langchain.messages import AnyMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from tools import tools

DB_PATH = "agent_memory.db"
agent=None

# TODO 1: 定义状态 + 初始化模型 + 组装图
# MessagesState / model / bind_tools / llm_call / should_continue / graph

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

def llm_call(state):
    #invoke调用
    response=model_with_tool.invoke(state["messages"])
    return {"messages":[response]}

def should_continue(state):
    #取最后一条messasge的tool_call
    if state["messages"][-1].tool_calls:
        return "tool_node"
    return END

#建graph
graph=StateGraph(MessagesState)
#建node
graph.add_node("llm_call",llm_call)
graph.add_node("tool_node",tool_node)
#建edge
graph.add_edge(START,"llm_call")
graph.add_conditional_edges("llm_call",should_continue,["tool_node",END])
graph.add_edge("tool_node","llm_call")

# TODO 2: lifespan —— 启动时初始化 agent，关闭时关连接
@asynccontextmanager
async def lifespan(app):
    global agent
    conn = await aiosqlite.connect(DB_PATH)
    agent = graph.compile(checkpointer=AsyncSqliteSaver(conn))
    yield
    await conn.close()

app = FastAPI(lifespan=lifespan)

# TODO 3: 请求模型
class ChatRequest(BaseModel):
    user_id: int
    message: str

# TODO 4: /chat 非流式端点
@app.post("/chat")
async def chat(req: ChatRequest):
    result =await agent.ainvoke(
        {"messages":[HumanMessage(req.message)]},
        config={"configurable":{
            "thread_id":str(req.user_id)
        }}
    )
    return {"reply": result["messages"][-1].content}

# TODO 5: /chat/stream 流式端点（SSE）
@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    async def event_stream():
        config = {"configurable": {"thread_id": str(req.user_id)}}
        input_data = {"messages": [HumanMessage(content=req.message)]}
        async for event in agent.astream_events(input_data, config=config, version="v2"):
            if event["event"] == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    yield f"data: {json.dumps({'text': content}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")
    

# TODO 6: /history 查历史
@app.get("/history/{user_id}")
async def history(user_id: int):
    config = {"configurable": {"thread_id": str(user_id)}}
    state = await agent.aget_state(config)
    messages = state.values.get("messages", []) if state.values else []
    return {
        "user_id": user_id,
        "history": [{"type": m.type, "content": m.content} for m in messages],
    }


# TODO 7: 启动
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)