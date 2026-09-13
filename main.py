# -*- coding: utf-8 -*-
import sys

try:
    from py12306.app import *
except ModuleNotFoundError as exc:
    # Give a useful startup error instead of a long import traceback.
    print('启动失败：缺少运行依赖 %s。请执行 python -m pip install -r requirements.txt' % exc.name)
    print('如果当前网络无法访问 PyPI，请先配置可用的 pip 镜像或离线 wheel。')
    raise SystemExit(2)
from py12306.helpers.cdn import Cdn
from py12306.log.common_log import CommonLog
from py12306.query.query import Query
from py12306.user.user import User
from py12306.web.web import Web
from py12306.helpers.device_id import StartupError


def main():
    load_argvs()
    CommonLog.print_welcome()
    App.run()
    CommonLog.print_configs()
    App.did_start()

    # Start the management page before network-heavy query initialization.
    # Otherwise a slow 12306 request prevents port 8008 from opening.
    Web.run()

    App.run_check()
    CommonLog.add_quick_log('正在初始化查询任务...').flush()
    try:
        Query.check_before_run()
    except StartupError as exc:
        CommonLog.add_quick_log('抢票初始化失败：{}'.format(exc)).flush()
        if Config().WEB_ENABLE and not Config().is_slave() and not Const.IS_TEST:
            CommonLog.add_quick_log('Web 后台仍可访问；修正配置或网络后请重启服务。').flush()
            while True:
                sleep(1)
        raise SystemExit(1)

    ####### 运行任务
    Cdn.run()
    User.run()
    Query.run()
    if not Const.IS_TEST:
        while True:
            sleep(10000)
    else:
        if Config().is_cluster_enabled(): stay_second(5)  # 等待接受完通知
    CommonLog.print_test_complete()


def test():
    """
    功能检查
    包含：
        账号密码验证 (打码)
        座位验证
        乘客验证
        语音验证码验证
        通知验证
    :return:
    """
    Const.IS_TEST = True
    Config.OUT_PUT_LOG_TO_FILE_ENABLED = False
    if '--test-notification' in sys.argv or '-n' in sys.argv:
        Const.IS_TEST_NOTIFICATION = True
    pass


def load_argvs():
    if '--test' in sys.argv or '-t' in sys.argv: test()
    config_index = None

    if '--config' in sys.argv: config_index = sys.argv.index('--config')
    if '-c' in sys.argv: config_index = sys.argv.index('-c')
    if config_index:
        Config.CONFIG_FILE = sys.argv[config_index + 1:config_index + 2].pop()


if __name__ == '__main__':
    main()
