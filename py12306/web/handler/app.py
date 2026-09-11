import json
import re

from flask import Blueprint, request, send_file
import threading
import datetime
from os import path
from flask.json import jsonify
from flask_jwt_extended import (jwt_required)

from py12306.config import Config, EnvLoader
from py12306.query.query import Query
from py12306.user.user import User

app = Blueprint('app', __name__)

CONFIG_META = {
 'USER_ACCOUNTS': ('12306账号','账号列表（默认扫码登录）','accounts'), 'QUERY_JOBS': ('购票任务','出发日期、车站、乘客和座席','jobs'),
 'QUERY_INTERVAL': ('查询间隔','两次查询之间的秒数，建议不低于1秒','number'), 'REQUEST_MAX_RETRY': ('请求重试次数','网络失败时自动重试次数','number'),
 'USER_HEARTBEAT_INTERVAL': ('登录检查间隔','检查账号状态的秒数','number'), 'AUTO_CODE_PLATFORM': ('验证码方式','免费验证码服务或自定义服务','select'),
 'NOTIFICATION_BY_VOICE_CODE': ('语音通知','下单成功后拨打电话通知','boolean'), 'DINGTALK_ENABLED': ('钉钉通知','发送消息到钉钉机器人','boolean'),
 'TELEGRAM_ENABLED': ('Telegram通知','发送消息到 Telegram','boolean'), 'SERVERCHAN_ENABLED': ('微信通知','通过 ServerChan 推送消息','boolean'),
 'PUSHBEAR_ENABLED': ('PushBear通知','通过 PushBear 推送消息','boolean'), 'BARK_ENABLED': ('Bark通知','推送到 iPhone Bark','boolean'),
 'EMAIL_ENABLED': ('邮件通知','发送邮件通知','boolean'), 'CLUSTER_ENABLED': ('分布式集群','只有使用 Redis 多节点时开启','boolean'),
 'WEB_ENABLE': ('开启管理页面','提供 Web 管理服务','boolean'), 'WEB_PORT': ('管理端口','本机 Web 服务端口','number'), 'CDN_ENABLED': ('CDN查询','使用备用查询节点','boolean'),
}
SENSITIVE_KEYS={'PASSWORD','WEB_USER','AUTO_CODE_ACCOUNT','DINGTALK_WEBHOOK','TELEGRAM_BOT_API_URL','SERVERCHAN_KEY','PUSHBEAR_KEY','BARK_PUSH_URL','NOTIFICATION_API_APP_CODE','RAIL_DEVICEID','RAIL_EXPIRATION'}

def config_keys(cfg):
    """Return only public settings documented by env.py.example plus local additions."""
    documented = {k for k, _ in EnvLoader.load_with_file(path.join(cfg.PROJECT_DIR, 'env.py.example'))}
    current = {k for k, _ in getattr(cfg, 'envs', [])}
    return sorted((documented | current) - DISPLAY_EXCLUDE)

KEY_LABELS = {
 'REDIS_HOST':'Redis 主机','REDIS_PORT':'Redis 端口','REDIS_PASSWORD':'Redis 密码','NODE_NAME':'节点名称',
 'NODE_IS_MASTER':'作为主节点','NODE_SLAVE_CAN_BE_MASTER':'允许从节点接管','OUT_PUT_LOG_TO_FILE_ENABLED':'写入日志文件',
 'OUT_PUT_LOG_TO_FILE_PATH':'日志文件位置','CACHE_RAIL_ID_ENABLED':'使用浏览器缓存标识','RAIL_EXPIRATION':'RailExpiration','RAIL_DEVICEID':'RailDeviceId',
 'API_USER_CODE_QCR_API':'自定义验证码接口','AUTO_CODE_ACCOUNT':'验证码平台账号','NOTIFICATION_VOICE_CODE_TYPE':'语音服务商',
 'NOTIFICATION_API_APP_CODE':'语音服务 AppCode','NOTIFICATION_VOICE_CODE_PHONE':'接收通知的手机号','DINGTALK_WEBHOOK':'钉钉机器人地址',
 'TELEGRAM_BOT_API_URL':'Telegram Bot 地址','SERVERCHAN_KEY':'ServerChan 密钥','PUSHBEAR_KEY':'PushBear 密钥','BARK_PUSH_URL':'Bark 推送地址',
 'EMAIL_SENDER':'发件邮箱','EMAIL_RECEIVER':'收件邮箱','EMAIL_SERVER_HOST':'邮箱服务器','EMAIL_SERVER_USER':'邮箱账号','EMAIL_SERVER_PASSWORD':'邮箱密码',
 'CDN_CHECK_TIME_OUT':'CDN 检测超时（秒）','CACHE_RAIL_ID_ENABLED':'使用浏览器缓存标识','QUERY_JOB_THREAD_ENABLED':'每个任务单独运行线程','AUTO_CODE_PLATFORM':'验证码方式','NOTIFICATION_BY_VOICE_CODE':'电话语音通知','NOTIFICATION_VOICE_CODE_TYPE':'语音服务商','TELEGRAM_ENABLED':'Telegram 通知','SERVERCHAN_ENABLED':'微信 ServerChan 通知','PUSHBEAR_ENABLED':'微信 PushBear 通知','BARK_ENABLED':'Bark 通知','EMAIL_ENABLED':'邮件通知','WEB_ENABLE':'开启 Web 管理','CDN_ENABLED':'使用备用查询节点','CDN_CHECK_TIME_OUT':'CDN 检测超时（秒）','API_USER_CODE_QCR_API':'自定义验证码接口','REQUEST_MAX_RETRY':'网络重试次数','QUERY_INTERVAL':'余票查询间隔（秒）','USER_HEARTBEAT_INTERVAL':'账号状态检查间隔（秒）','OUT_PUT_LOG_TO_FILE_ENABLED':'保存日志到文件','OUT_PUT_LOG_TO_FILE_PATH':'日志文件位置'
}

# Internal paths and derived constants are implementation details, not user settings.
DISPLAY_EXCLUDE={'PROJECT_DIR','RUNTIME_DIR','QUERY_DATA_DIR','USER_DATA_DIR','STATION_FILE','CONFIG_FILE','WEB_ENTER_HTML_PATH','CDN_ITEM_FILE','CDN_ENABLED_AVAILABLE_ITEM_FILE','SEAT_TYPES','ORDER_SEAT_TYPES'}

def validate_config(values, cfg):
    errors=[]; accounts=values.get('USER_ACCOUNTS', cfg.USER_ACCOUNTS) or []; jobs=values.get('QUERY_JOBS', cfg.QUERY_JOBS) or []
    keys=[str(a.get('key')) for a in accounts if isinstance(a,dict)]
    if len(keys)!=len(set(keys)): errors.append('账号 key 不能重复')
    if values.get('QUERY_INTERVAL',cfg.QUERY_INTERVAL) < 0.5: errors.append('查询间隔不能小于 0.5 秒')
    if not isinstance(jobs,list): errors.append('购票任务必须是列表')
    for i,job in enumerate(jobs):
        if not isinstance(job,dict): errors.append('任务 %d 格式错误'%(i+1)); continue
        if not job.get('left_dates'): errors.append('任务 %d 未设置出发日期'%(i+1))
        for d in job.get('left_dates',[]):
            try:
                day=datetime.datetime.strptime(str(d),'%Y-%m-%d').date()
                if day < datetime.date.today(): errors.append('任务 %d 包含过去日期'%(i+1))
            except ValueError: errors.append('任务 %d 日期格式应为 YYYY-MM-DD'%(i+1))
        st=job.get('stations',{}); sts=st if isinstance(st,list) else [st]
        from py12306.helpers.station import Station
        for pair in sts:
            if not isinstance(pair,dict) or not Station.get_station_by_name(pair.get('left','')): errors.append('任务 %d 出发站不存在'%(i+1))
            if not isinstance(pair,dict) or not Station.get_station_by_name(pair.get('arrive','')): errors.append('任务 %d 到达站不存在'%(i+1))
        if job.get('train_numbers') and job.get('except_train_numbers'): errors.append('任务 %d 不能同时设置允许和排除车次'%(i+1))
    for k in ('WEB_PORT','REQUEST_MAX_RETRY','USER_HEARTBEAT_INTERVAL'):
        if k in values and (not isinstance(values[k],int) or values[k] <= 0): errors.append('%s 必须是正整数'%k)
    return errors


@app.route('/', methods=['GET', 'POST'])
def index():
    file = Config().WEB_ENTER_HTML_PATH
    result = ''
    with open(file, 'r', encoding='utf-8') as f:
        result = f.read()
        config = {
            'API_BASE_URL': ''  # TODO 自定义 Host
        }
        result = re.sub(r'<script>[\s\S]*?<\/script>', '<script>window.config={}</script>'.format(json.dumps(config)),
                        result)

    return result


@app.route('/app/menus', methods=['GET'])
@jwt_required()
def menus():
    """
    菜单列表
    """
    menus = [
        {"id": 10, "name": "首页", "url": "/", "icon": "fa fa-tachometer-alt"},
        {"id": 20, "name": "用户管理", "url": "/user", "icon": "fa fa-user"},
        {"id": 30, "name": "查询任务", "url": "/query", "icon": "fa fa-infinity"},
        {"id": 40, "name": "实时日志", "url": "/log/realtime", "icon": "fa fa-signature"},
        {"id": 50, "name": "帮助", "url": "/help", "icon": "fa fa-search"}
        ,{"id": 60, "name": "配置中心", "url": "/static/config.html?v=20260912", "icon": "fa fa-sliders-h"}
    ]
    return jsonify(menus)


@app.route('/app/actions', methods=['GET'])
@jwt_required()
def actions():
    """
    操作列表
    """
    from py12306.app import App
    running = App.TICKETING_STATUS in ('starting', 'running')
    actions = [
        {"text": "停止抢票" if running else "开始抢票", "key": 'stop_ticketing' if running else 'start_ticketing', "link": "", "icon": "fa fa-stop" if running else "fa fa-play"},
        {"text": "退出登录", "key": 'logout', "link": "", "icon": "fa fa-sign-out-alt"}
    ]
    return jsonify(actions)

@app.route('/app/ticketing/start', methods=['POST'])
@jwt_required()
def start_ticketing():
    from py12306.app import App
    errors=validate_config({}, Config())
    if errors: App.TICKETING_STATUS='failed'; App.TICKETING_ERROR='；'.join(errors); return jsonify({'started':False,'errors':errors}),400
    if not App.TICKETING_THREADS_STARTED:
        App.TICKETING_STATUS='starting'
        App.TICKETING_STARTED = True
        App.TICKETING_THREADS_STARTED = True
        from py12306.user.user import User
        from py12306.query.query import Query
        threading.Thread(target=User.run, daemon=True).start()
        threading.Thread(target=Query.run, daemon=True).start()
        App.TICKETING_STATUS='running'
    return jsonify({'started': True, 'status': App.TICKETING_STATUS})

@app.route('/app/ticketing/status', methods=['GET'])
@jwt_required()
def ticketing_status():
    from py12306.app import App
    return jsonify({'status':App.TICKETING_STATUS,'error':App.TICKETING_ERROR,'started_at':App.TICKETING_STARTED_AT})

@app.route('/app/ticketing/stop', methods=['POST'])
@jwt_required()
def stop_ticketing():
    from py12306.app import App
    App.TICKETING_STARTED=False; App.TICKETING_STATUS='idle'; App.TICKETING_ERROR=''
    try:
        for job in list(Query().jobs): job.destroy()
        for user in list(User().users): user.destroy()
    except Exception:
        pass
    return jsonify({'stopped':True,'status':'idle'})

@app.route('/app/config', methods=['GET', 'PUT'])
@jwt_required()
def config_api():
    cfg = Config()
    all_keys = [k for k in config_keys(cfg) if k not in DISPLAY_EXCLUDE]
    if request.method == 'GET':
        return jsonify({k: ('••••••' if k in SENSITIVE_KEYS and getattr(cfg,k) else getattr(cfg,k)) for k in all_keys})
    values = request.get_json(silent=True) or {}
    allowed = {k for k in all_keys if k not in cfg.disallow_update_configs and k not in {'PROJECT_DIR'}}
    for key, value in values.items():
        if key in SENSITIVE_KEYS and value == '••••••': continue
        if key in allowed:
            setattr(cfg, key, value)
    # Persist edits as simple assignments; Config's watcher reloads them.
    try:
        # Rewrite all known assignments as valid Python so nested/multiline
        # values such as USER_ACCOUNTS and QUERY_JOBS remain consistent.
        lines = ['# Generated by py12306 Web 配置中心\n']
        for key in all_keys:
            lines.append(key + ' = ' + repr(getattr(cfg, key)) + '\n')
        with open(cfg.CONFIG_FILE, 'w', encoding='utf-8') as f: f.writelines(lines)
    except OSError:
        pass
    return jsonify({'saved': sorted(set(values) & allowed), 'hot_loaded': True})

@app.route('/app/config/schema', methods=['GET'])
@jwt_required()
def config_schema():
    cfg=Config(); result=[]
    for key in config_keys(cfg):
        if key in DISPLAY_EXCLUDE: continue
        title,help_text,kind=CONFIG_META.get(key,(KEY_LABELS.get(key, key.replace('_',' ').title()),'高级配置项，通常无需修改','advanced'))
        result.append({'key':key,'title':title,'help':help_text,'type':kind,'value':getattr(cfg,key)})
    return jsonify(result)

@app.route('/app/config/validate', methods=['POST'])
@jwt_required()
def validate_config_api():
    values=request.get_json(silent=True) or {}; errors=validate_config(values,Config())
    return jsonify({'valid':not errors,'errors':errors})




