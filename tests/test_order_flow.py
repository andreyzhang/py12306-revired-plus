import unittest
from types import SimpleNamespace
from unittest.mock import patch

from py12306.order.order import Order
from py12306.user.job import UserJob, _parse_js_object


class FakeResponse:
    def __init__(self, payload=None, text='', status_code=200, url='https://kyfw.12306.cn/'):
        self.payload = payload
        self.text = text
        self.status_code = status_code
        self.url = url
        self.headers = {'Content-Type': 'application/json' if payload is not None else 'text/html'}

    def json(self):
        if self.payload is None:
            raise ValueError('not json')
        return self.payload


class OrderFlowTests(unittest.TestCase):
    def make_order(self, payload):
        order = object.__new__(Order)
        order.session = SimpleNamespace(post=lambda *args, **kwargs: FakeResponse(payload))
        order.user_ins = SimpleNamespace(
            global_repeat_submit_token='token',
            ticket_info_for_passenger_form={
                'queryLeftTicketRequestDTO': {
                    'train_no': 'train-no', 'station_train_code': 'D204',
                    'from_station': 'NJH', 'to_station': 'HIK'},
                'leftTicketStr': 'left-ticket', 'purpose_codes': '00',
                'train_location': 'H6', 'key_check_isChange': 'key'})
        order.query_ins = SimpleNamespace(current_order_seat='O', left_date='2026-09-21')
        order.passenger_ticket_str = 'passenger'
        order.old_passenger_str = 'old'
        order.is_slide = False
        order.is_need_auth_code = False
        return order

    def test_check_order_info_reads_nested_plain_dict(self):
        order = self.make_order({'data': {'submitStatus': True, 'ifShowPassCode': 'N'}})
        self.assertTrue(order.check_order_info())
        self.assertFalse(order.is_need_auth_code)

    def test_queue_count_reads_nested_plain_dict(self):
        order = self.make_order({
            'status': True,
            'data': {'ticket': '13,0', 'op_2': 'false', 'countT': '2'}})
        self.assertTrue(order.get_queue_count())

    def test_confirm_queue_reads_nested_plain_dict(self):
        order = self.make_order({'data': {'submitStatus': True}})
        self.assertTrue(order.confirm_single_for_queue())

    def test_query_wait_time_returns_real_order_id(self):
        order = self.make_order({})
        order.session.get = lambda *args, **kwargs: FakeResponse({
            'status': True,
            'data': {'waitTime': -1, 'orderId': 'E123456789'},
        })
        order.max_queue_wait = 3
        order.wait_queue_interval = 3
        self.assertEqual(order.query_order_wait_time(), 'E123456789')

    def test_query_wait_time_keeps_polling_if_order_id_is_delayed(self):
        order = self.make_order({})
        responses = iter([
            FakeResponse({'status': True, 'data': {'waitTime': -1, 'orderId': None}}),
            FakeResponse({'status': True, 'data': {'waitTime': -1, 'orderId': 'E987654321'}}),
        ])
        order.session.get = lambda *args, **kwargs: next(responses)
        order.max_queue_wait = 6
        order.wait_queue_interval = 3
        with patch('py12306.order.order.stay_second'):
            self.assertEqual(order.query_order_wait_time(), 'E987654321')

    def test_login_hook_ignores_html_response(self):
        user = UserJob({'key': 1, 'user_name': 'test', 'password': '', 'type': 'qr'})
        response = FakeResponse(text='<html>order page</html>')
        self.assertIs(user.response_login_check(response), response)

    def test_init_dc_retries_then_parses_order_page(self):
        user = UserJob({'key': 1, 'user_name': 'test', 'password': '', 'type': 'qr'})
        html = """
        <script>
        var globalRepeatSubmitToken = '0123456789abcdef0123456789abcdef';
        var ticketInfoForPassengerForm = {"purpose_codes":"00"};
        var orderRequestDTO = {"station_train_code":"D204"};
        var if_check_slide_passcode = '0';
        </script>
        """
        responses = iter([FakeResponse(text=''), FakeResponse(text=html)])
        user.session.post = lambda *args, **kwargs: next(responses)
        with patch('py12306.user.job.stay_second'):
            ready, slide, _ = user.request_init_dc_page()
        self.assertTrue(ready)
        self.assertFalse(slide)
        self.assertEqual(user.ticket_info_for_passenger_form['purpose_codes'], '00')

    def test_parse_multiline_js_order_form_without_executing_script(self):
        html = r'''
        <script>
        var ticketInfoForPassengerForm = {
            'purpose_codes': '00',
            'queryLeftTicketRequestDTO': {
                'station_train_code': 'D204',
                'flag': true,
                'note': "O'Brien {test}"
            },
            'optional': null
        };
        </script>
        '''
        result = _parse_js_object(html, 'ticketInfoForPassengerForm')
        self.assertEqual(result['queryLeftTicketRequestDTO']['station_train_code'], 'D204')
        self.assertTrue(result['queryLeftTicketRequestDTO']['flag'])
        self.assertEqual(result['queryLeftTicketRequestDTO']['note'], "O'Brien {test}")
        self.assertIsNone(result['optional'])


if __name__ == '__main__':
    unittest.main()
