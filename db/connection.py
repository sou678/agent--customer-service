"""数据访问层：封装数据库连接、查询、修改"""
import json
import pymysql
from contextlib import contextmanager

# TODO 1: 读 db_config.json
with open("config/db_config.json","r",encoding="utf-8") as f:
    DB_CONFIG=json.load(f)


# TODO 2: get_db() 上下文管理器
@contextmanager
def get_db():
    """自动管理连接：正常提交、出错回滚、退出关闭"""
    db = pymysql.connect(database="shop",**DB_CONFIG)
    try:
        yield db.cursor()
        db.commit()      # 正常退出提交
    except Exception:
        db.rollback()    # 出错回滚
        raise
    finally:
        db.close()       # 无论如何关闭

# TODO 3: db_query —— 返回所有行
def db_query(sql, params=()):
    with get_db() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()

# TODO 4: db_query_one —— 返回一行
def db_query_one(sql, params=()):
    with get_db() as cursor:
        cursor.execute(sql,params)
        return cursor.fetchone()


# TODO 5: db_execute —— 增删改
def db_execute(sql, params=()):
    with get_db() as cursor:
        cursor.execute(sql, params)
        return cursor.rowcount