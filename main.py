import asyncio
import aiosqlite
import sqlite3
from agents.supervisor import graph,ask
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

DB_PATH="agent_memory.db"

async def main():
    global agent
    #连接数据库
    conn = await aiosqlite.connect(DB_PATH)
    supervisor = graph.compile(checkpointer=AsyncSqliteSaver(conn))
    user_id = 1
    try:
        while True:
            q = input("================================== Human Message ==================================\n")
            if q == "exit":
                print("期待您的下次使用！")
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
            m = await ask(supervisor,str(user_id), q)
            m.pretty_print()
    finally:
        await conn.close()
if __name__ == "__main__":
    asyncio.run(main())


