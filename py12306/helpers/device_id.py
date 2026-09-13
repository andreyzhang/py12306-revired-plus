"""Bounded device identifier initialization, shared by query and login."""
import base64
import json
import re
import time

from requests.exceptions import RequestException


class StartupError(RuntimeError):
    pass


def _valid(device, expiration):
    try:
        return bool(device) and int(expiration) > int(time.time() * 1000)
    except (TypeError, ValueError):
        return False


def _read(session, url, timeout):
    response = session.get(url, timeout=timeout)
    if response.status_code != 200:
        raise ValueError('HTTP {}'.format(response.status_code or '无响应'))
    content = response.text.strip()
    match = re.fullmatch(r'callbackFunction\s*\((.*)\)\s*;?', content, re.S)
    if match:
        content = match.group(1)
    try:
        result = json.loads(content)
    except ValueError:
        raise ValueError('返回了非 JSON/JSONP 内容') from None
    if not isinstance(result, dict):
        raise ValueError('返回格式不正确')
    return result


def load_device_id(session, cfg, url, log, force_renew=False):
    # Explicit browser cache is usable without contacting the helper service.
    if cfg.is_cache_rail_id_enabled():
        if not _valid(cfg.RAIL_DEVICEID, cfg.RAIL_EXPIRATION):
            raise StartupError('浏览器设备标识缓存为空或已过期，请更新 RAIL_DEVICEID 和 RAIL_EXPIRATION')
        session.cookies.update({'RAIL_DEVICEID': str(cfg.RAIL_DEVICEID),
                                'RAIL_EXPIRATION': str(cfg.RAIL_EXPIRATION)})
        return
    if not force_renew and _valid(session.cookies.get('RAIL_DEVICEID'),
                                 session.cookies.get('RAIL_EXPIRATION')):
        return

    # Both the historical helper and 12306's old logdevice endpoint now
    # return an error/HTML page. Skip them immediately and use QR/query APIs.
    if '12306-rail-id-v2.pjialin.com' in url or 'HttpZF/logdevice' in url:
        log('设备标识接口已不可用，将继续使用无设备标识模式')
        return False

    attempts = max(1, min(int(cfg.REQUEST_MAX_RETRY), 3))
    timeout = max(1, min(float(cfg.TIME_OUT_OF_REQUEST), 5))
    for attempt in range(1, attempts + 1):
        log('正在获取设备标识（{}/{}）'.format(attempt, attempts))
        try:
            result = _read(session, url, timeout)
            if 'pjialin' in url:
                target = base64.b64decode(result['id'], validate=True).decode('utf-8')
                result = _read(session, target, timeout)
            if not _valid(result.get('dfp'), result.get('exp')):
                raise ValueError('响应缺少有效设备标识或已过期')
            session.cookies.update({'RAIL_DEVICEID': str(result['dfp']),
                                    'RAIL_EXPIRATION': str(result['exp'])})
            return
        except (RequestException, ValueError, KeyError, TypeError) as exc:
            # Never log response bodies, cookies, or signed URLs.
            detail = type(exc).__name__ if isinstance(exc, RequestException) else str(exc)
            log('设备标识获取失败（{}/{}）：{}'.format(attempt, attempts, detail))
    # Device IDs are an anti-fraud hint. Current 12306 QR and query endpoints
    # can operate without one, so do not block the whole application when the
    # legacy helper service is unavailable.
    log('设备标识服务不可用，将继续使用无设备标识模式')
    return False
