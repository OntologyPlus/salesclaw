"""种子数据服务"""
from database import seed_default_data


def run_seed():
    """执行种子数据初始化"""
    seed_default_data()
