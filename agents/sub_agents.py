"""子 Agent"""
import json
from typing import Literal, Annotated, TypedDict
import operator
from langchain.chat_models import init_chat_model
from langchain.messages import AnyMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from tools.tools import query_order, search_knowledge, search_web

# TODO 1: 读 config.json，初始化 LLM
with open("config/config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

model = init_chat_model(
    config["model"], 
    temperature=0,
    api_key=config["api_key"], 
    base_url=config["base_url"],
)

class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]


#函数工厂
def make_sub_agent(tools,system_prompt):
    model_with_tools=model.bind_tools(tools)
    tool_node=ToolNode(tools)

    async def llm_call(state):
        response=await model_with_tools.ainvoke(
            [SystemMessage(content=system_prompt)]+state["messages"]
        )
        return {"messages":[response]}

    def should_continue(state):
        if state["messages"][-1].tool_calls:
            return "tool_node"
        return END

    #构建，编译图
    graph=StateGraph(MessagesState)

    graph.add_node("llm_call",llm_call)
    graph.add_node("tool_node",tool_node)

    graph.add_edge(START,"llm_call")
    graph.add_conditional_edges("llm_call",should_continue,["tool_node",END])
    graph.add_edge("tool_node","llm_call")

    return graph.compile()
    
# TODO 2: 订单子 Agent（tools=[query_order]，prompt="订单专家"）
order_agent = make_sub_agent(
    tools=[query_order],
    system_prompt="你是订单查询专家，只处理订单相关问题。",
)
# TODO 3: 知识子 Agent（tools=[search_knowledge]，prompt="政策专家"）
knowledge_agent = make_sub_agent(
    tools=[search_knowledge],
    system_prompt="你是公司政策专家，只处理公司知识库问题。",
)
# TODO 4: 搜索子 Agent（tools=[search_web]，prompt="搜索专家"）
search_agent = make_sub_agent(
    tools=[search_web],
    system_prompt="你是联网搜索专家，处理实时信息查询。",
)