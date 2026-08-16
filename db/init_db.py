"""初始化数据库：建库、建表、插入测试数据"""
import json
import pymysql
from db.connection import db_query,db_query_one

# TODO 1: 读 db_config.json
with open("config/db_config.json","r",encoding="utf-8") as f:
    DB_CONFIG=json.load(f)


def init_db():
    # TODO 2: 建数据库（CREATE DATABASE IF NOT EXISTS shop）
    db = pymysql.connect(**DB_CONFIG)
    cursor = db.cursor()
    create_tb = """create database if not exists shop default charset utf8mb4"""
    cursor.execute(create_tb)
    db.commit()
    db.close()

    # TODO 3: 建 orders 表（字段：order_id, customer_name, product, amount, status, created_at）
    db = pymysql.connect(database="shop", **DB_CONFIG)
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id VARCHAR(20) PRIMARY KEY,
            customer_name VARCHAR(50),
            product VARCHAR(100),
            amount DECIMAL(10, 2),
            status VARCHAR(20),
            created_at DATE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # TODO 4: 插入测试数据（4 条订单）
    cursor.execute("SELECT COUNT(*) FROM orders")
    if cursor.fetchone()[0] == 0:
        test_data = [
            ("ORD1001", "张三", "Pro版年费会员", 999.00, "已发货", "2026-08-10"),
        ]
        cursor.executemany(
            "INSERT INTO orders VALUES (%s, %s, %s, %s, %s, %s)", test_data
        )
    db.commit()
    db.close()
    print("MySQL 数据库初始化完成")

