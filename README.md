# 智能客服_多智能体系统

基于 LangGraph 构建的 Supervisor 多智能体客服系统，实现订单管理（增删改查）、知识库检索、联网搜索的智能路由与协同。

## 架构

```
用户请求
  ↓
Supervisor（主 Agent，路由决策）
  ├── 订单 Agent → 订单 CRUD → MySQL
  ├── 知识 Agent → search_knowledge → RAG 向量检索
  └── 搜索 Agent → search_web → Tavily 联网搜索
  ↓
多用户隔离（thread_id + Checkpointer）
```

### Supervisor 多智能体模式

- **Supervisor**：只做路由，根据用户意图分发到对应子 Agent
- **订单 Agent**：订单完整 CRUD（创建、查询、修改、删除），MySQL 存储
- **知识 Agent**：RAG 检索公司知识库（BGE 中文向量模型 + Chroma）
- **搜索 Agent**：联网搜索实时信息（Tavily）

## 功能特性

- **多智能体路由**：Supervisor 自主判断问题类型，分发到对应专家
- **订单 CRUD**：创建、查询、修改、删除订单，参数化查询防 SQL 注入
- **多数据源**：MySQL 订单 + RAG 知识库 + 联网搜索
- **多轮对话记忆**：Checkpointer 持久化，多用户 thread_id 隔离
- **流式输出**：SSE 逐字推送（打字机效果）
- **双重接口**：CLI 交互 + FastAPI REST API

## 技术栈

- **LangGraph**：多智能体编排（StateGraph + 子图嵌套 + Checkpointer）
- **LangChain**：LLM 调用、工具绑定、Embedding
- **MySQL**：订单数据存储（pymysql + 参数化查询 + 事务）
- **ChromaDB**：向量数据库（BGE 中文 embedding）
- **Tavily**：联网搜索
- **FastAPI**：REST API + SSE 流式
- **SQLite**：对话记忆持久化（Checkpointer）

## 目录结构

```
agent--customer service/
├── config/
│   ├── config.json          # LLM 配置（API key、模型）
│   └── db_config.json       # MySQL 配置
├── data/
│   └── messages.txt         # 知识库文档
├── db/
│   ├── __init__.py
│   ├── connection.py        # 数据访问层（连接封装、查询、事务）
│   └── init_db.py           # 数据库初始化（建库建表）
├── tools/
│   ├── __init__.py
│   └── tools.py             # 工具定义（订单 CRUD / 知识检索 / 联网搜索）
├── agents/
│   ├── __init__.py
│   ├── sub_agents.py        # 三个子 Agent（工厂函数创建）
│   └── supervisor.py        # Supervisor 主 Agent（路由编排）
├── main.py                  # CLI 交互入口
├── server.py                # FastAPI 服务入口
└── .gitignore
```

## 快速开始

### 1. 安装依赖

```bash
pip install langgraph langchain langchain-anthropic langchain-chroma langchain-huggingface langchain-community fastapi uvicorn pymysql aiosqlite tavily-python
```

### 2. 配置

创建 `config/config.json`：

```json
{
    "api_key": "你的LLM API key",
    "model": "claude-sonnet-4-6",
    "base_url": "你的API地址",
    "tavily_api_key": "你的Tavily key"
}
```

创建 `config/db_config.json`：

```json
{
    "host": "localhost",
    "user": "root",
    "password": "你的密码",
    "port": 3306,
    "charset": "utf8mb4",
    "database": "shop"
}
```

### 3. 初始化数据库

```bash
python db/init_db.py
```

### 4. 运行 CLI

```bash
python main.py
```

### 5. 运行 HTTP 服务

```bash
python server.py
# 打开 http://localhost:8000/docs 查看接口文档
```

## 使用示例

### CLI 订单 CRUD

```
请输入问题：
创建订单 ORD2001，客户张三，商品年费会员，金额999，状态待付款   → create_order
查询订单 ORD2001                                                → query_order
把订单 ORD2001 状态改成已发货                                   → update_order
删除订单 ORD2001                                                → delete_order
```

### CLI 多智能体路由

```
请输入问题：
退换货政策是什么？            → 知识 Agent 检索 RAG
最近有什么 AI 新闻？          → 搜索 Agent 联网搜索
```

### HTTP API

```bash
# 非流式
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "message": "我的订单 ORD1001 到哪了？"}'

# 流式
curl -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "message": "最近有什么新闻？"}'

# 查历史
curl http://localhost:8000/history/1
```

## 核心设计

### 数据访问层（事务 + 回滚）

```python
# db/connection.py 封装连接生命周期，工具层不碰连接细节
@contextmanager
def get_db():
    conn = pymysql.connect(**DB_CONFIG)
    try:
        yield conn.cursor()
        conn.commit()      # 正常提交
    except Exception:
        conn.rollback()    # 出错回滚
        raise
    finally:
        conn.close()       # 无论如何关闭
```

### 子 Agent 工厂（DRY 原则）

```python
# agents/sub_agents.py 用工厂函数创建子 Agent，避免重复
def make_sub_agent(tools, system_prompt):
    # 每个子 Agent 是独立的 ReAct 循环
    ...
```

### Supervisor 路由（子图作为节点）

```python
# agents/supervisor.py 用 route 工具分发
@tool
def route_to_order(question: str) -> str:
    """订单相关问题，转给订单专家。"""
    return "order_agent"
```

## 要点

1. **多智能体 vs 单智能体**：工具多时单 Agent 的 LLM 易乱选，Supervisor 模式让每个子 Agent 专精一件事，独立 prompt + 独立工具集
2. **数据层设计**：参数化查询防注入、事务回滚、上下文管理器管理连接
3. **订单 CRUD**：动态拼接 UPDATE 语句，支持灵活修改；删除操作考虑软删除
4. **RAG 检索**：中文 BGE embedding + Chroma 向量库，语义匹配
5. **多用户隔离**：thread_id + Checkpointer，天然支持并发
