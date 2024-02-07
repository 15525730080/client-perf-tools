# _*_ coding: utf-8 _*_
import os
from builtins import *
from contextlib import contextmanager

from sqlalchemy import create_engine, Column, String, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy_serializer import SerializerMixin

from logzero import logger

logger.info("工作空间{0}".format(os.getcwd()))
db_path = os.path.join(os.getcwd(), "task.sqlite")
logger.info("db path {0}".format(db_path))
engine = create_engine('sqlite:///{0}'.format(db_path))
logger.info("current path {0}".format(os.getcwd()))
Session = sessionmaker(bind=engine)
Base = declarative_base()


@contextmanager
def connect():
    logger.info("begin sql")
    session = Session()
    try:
        yield session
        session.commit()
        logger.info("sql success")
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
        logger.info("sql end")


class Task(Base, SerializerMixin):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True, autoincrement=True)
    host = Column(String(50), default=None)
    port = Column(Integer)
    start_time = Column(DateTime, default=None)
    end_time = Column(DateTime, default=None)
    serialno = Column(String(255), default=None)
    status = Column(Integer)  # 0未开始, 1 执行中 , 2 执行完成 3.暂停
    file_dir = Column(String(255), default=None)  # 存储csv文件的路径
    package = Column(String(255), default=None)  # 测试的app包名
    pid = Column(Integer)  # 当前任务运行的进程pid，任务执行的进程，里面有各个性能指标的线程
    platform = Column(String(50), default="android")  # android | ios 任务


class TaskNameMapper(Base, SerializerMixin):
    __tablename__ = 'task_name_mapper'
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer)


class TaskLabel(Base, SerializerMixin):
    __tablename__ = 'task_label'
    id = Column(Integer, primary_key=True, autoincrement=True)
    end_time = Column(DateTime, default=None)  # 标签开始
    serialno = Column(String(255), default=None)  # 标签结束


Base.metadata.create_all(engine)
