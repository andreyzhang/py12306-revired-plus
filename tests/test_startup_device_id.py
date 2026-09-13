import base64
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from py12306.helpers.device_id import StartupError, load_device_id


class DeviceIdTests(unittest.TestCase):
    def setUp(self):
        self.expiration = str(int(time.time() * 1000) + 60000)
        self.cfg = SimpleNamespace(
            REQUEST_MAX_RETRY=100, TIME_OUT_OF_REQUEST=5,
            is_cache_rail_id_enabled=lambda: False,
            RAIL_DEVICEID='cached-device', RAIL_EXPIRATION=self.expiration)
        self.session = Mock(cookies=requests.cookies.RequestsCookieJar())
        self.logs = []

    def load(self, url='https://example.org/device', force=False):
        return load_device_id(self.session, self.cfg, url, self.logs.append, force)

    def test_network_failures_stop_after_three_attempts(self):
        self.session.get.side_effect = requests.exceptions.ProxyError('private proxy details')
        self.assertFalse(self.load())
        self.assertEqual(self.session.get.call_count, 3)
        self.assertNotIn('private proxy details', '\n'.join(self.logs))
        self.session.get.assert_called_with('https://example.org/device', timeout=5)

    def test_html_200_is_not_success(self):
        self.session.get.return_value = SimpleNamespace(status_code=200, text='<html>challenge</html>')
        self.assertFalse(self.load())
        self.assertEqual(self.session.get.call_count, 3)
        self.assertFalse(self.session.cookies)

    def test_valid_cache_does_not_need_network_even_on_refresh(self):
        self.cfg.is_cache_rail_id_enabled = lambda: True
        self.load(force=True)
        self.session.get.assert_not_called()
        self.assertEqual(self.session.cookies.get('RAIL_DEVICEID'), 'cached-device')

    def test_expired_cache_is_rejected(self):
        self.cfg.is_cache_rail_id_enabled = lambda: True
        self.cfg.RAIL_EXPIRATION = '0'
        with self.assertRaises(StartupError):
            self.load()
        self.session.get.assert_not_called()

    def test_helper_then_valid_jsonp(self):
        import json
        target = 'https://example.org/device'
        self.session.get.side_effect = [
            SimpleNamespace(status_code=200, text=json.dumps({'id': base64.b64encode(target.encode()).decode()})),
            SimpleNamespace(status_code=200, text='callbackFunction(\n' + json.dumps({'dfp': 'new-device', 'exp': self.expiration}) + '\n);')]
        self.load('https://helper.pjialin.com/')
        self.assertEqual(self.session.get.call_count, 2)
        self.assertEqual(self.session.cookies.get('RAIL_DEVICEID'), 'new-device')

    def test_missing_device_values_do_not_succeed(self):
        self.session.get.return_value = SimpleNamespace(status_code=200, text='callbackFunction({});')
        self.assertFalse(self.load())
        self.assertFalse(self.session.cookies)

    def test_query_url_success_does_not_fetch_device_again(self):
        from py12306.query.query import Query
        q = Query()
        response = SimpleNamespace(status_code=200, text='var CLeftTicketUrl = "leftTicket/queryG";')
        with patch.object(q, 'api_type', None), patch.object(q.session, 'get', return_value=response), patch.object(q, 'request_device_id') as device:
            self.assertEqual(q.get_query_api_type(), 'leftTicket/queryG')
            device.assert_not_called()

    def test_query_url_failure_is_bounded(self):
        from py12306.query.query import Query
        q = Query()
        response = SimpleNamespace(status_code=200, text='<html>No query URL</html>')
        with patch.object(q, 'api_type', None), patch.object(q.session, 'get', return_value=response) as get:
            with self.assertRaises(StartupError):
                q.get_query_api_type()
            self.assertLessEqual(get.call_count, 3)


if __name__ == '__main__':
    unittest.main()



