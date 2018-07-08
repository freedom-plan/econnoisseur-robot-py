# coding=utf-8
import hashlib
import hmac
import base64
from configparser import ConfigParser

import requests
import time

from logger import TimeLogger
from service.common_service import *
from util.json_util import *

# 设置全局日志类
log = TimeLogger('../logs/kucoin.log').timeLog

cfg = ConfigParser()
cfg.read('../conf/conf.ini')

# 设置全局请求类
http = requests.session()
secret = cfg.get('kucoin', 'secret')
apiKey = cfg.get('kucoin', 'apiKey')
proxy = {"http": "139.162.98.33:3333", "https": "139.162.98.33:3333"}


def get_sign(params, end_point):
    b_secret_key = bytes(secret, encoding='utf8')
    nonce = str(int(round(time.time() * 1000)))
    sign = end_point + "/" + nonce + "/"
    for key in params.keys():
        value = str(params[key])
        sign += key + '=' + value + '&'
    if params:
        b_sign = bytes(sign[:-1], encoding='utf8')
    else:
        b_sign = bytes(sign, encoding='utf8')
    sign_base = base64.b64encode(b_sign)
    my_sign = hmac.new(b_secret_key, sign_base, hashlib.sha256).hexdigest()
    user_agent_header = {
        'KC-API-KEY': apiKey,
        'KC-API-NONCE': nonce,
        'KC-API-SIGNATURE': my_sign
    }
    return user_agent_header


class KuCoinMarketService(MarketService):
    def get_ticker(self, pair: str):
        """
        获取当前价格
        {
            "success": true,
            "code": "OK",
            "msg": "Operation succeeded.",
            "data":{
                "coinType": "KCS",
                "trading": true,
                "lastDealPrice": 5040,
                "buy": 5000,
                "sell": 5040,
                "coinTypePair": "BTC",
                "sort": 0,
                "feeRate": 0.001,
                "volValue": 308140577,
                "high": 6890,
                "datetime": 1506050394000,
                "vol": 5028739175025,
                "low": 5040,
                "changeRate": -0.2642
            }
        }
        :param pair:
        :return:
        """
        url = 'https://api.kucoin.com/v1/open/tick'
        response = http.get(url, params={'symbol': pair}, proxies=proxy)

        repeat_times = 5
        while True:
            try:
                json_result = response.json()
                if json_result['success'] is not True:
                    log(u'请求发送失败: %s' % response.text)
                    if repeat_times < 5:
                        repeat_times += 1
                        continue
                    else:
                        raise RuntimeError(u'尝试5次重新请求，全部失败，请检查网络')

                ts = json_result['data']['datetime']
                sell1 = json_result['data']['sell']
                buy1 = json_result['data']['buy']
                last_price = json_result['data']['lastDealPrice']

                t = Ticker()
                t.pair = pair
                t.sellPrice = Decimal(sell1)
                t.buyPrice = Decimal(buy1)
                t.last = Decimal(last_price)
                t.timestamp = ts
                log(u'卖一: %s, 买一: %s' % (t.sellPrice, t.buyPrice))
                return t
            except(ValueError, TypeError):
                log(u'json 解析失败: %s' % response.text)
                if repeat_times < 5:
                    time.sleep(1)
                    log(u'再次检查盘口状态')
                    repeat_times += 1
                else:
                    raise RuntimeError(u'尝试5次重新请求，全部失败，请检查网络')


class KuCoinOrderService(OrderService):
    def __init__(self, account):
        super().__init__(account)
        # 请按照 OrderStatus 的顺序进行映射
        self.order_status = ['not_deal', 'part_deal', 'done', 'cancel']

    def _order(self, params, pair):
        """
        通用交易提交
        :param params:
        :param pair:
        :return:
        """
        url = 'https://api.kucoin.com/v1/order?symbol=%s' % pair

        auth_header = get_sign(params, '/v1/order')
        response = http.post(url, json=params, headers=auth_header)

        repeat_times = 0
        max_try_times = 1
        time_interval = 1
        while True:
            try:
                json_result = response.json()
                if json_result['success'] is not True:
                    log(u'下单成功, op: buy,\t currency_pair:%s,\t count: %s' % (pair, str(params['amount'])))
                    order_id = json_result['data']['orderOid']
                    return order_id
                else:
                    log(u'接口返回code异常 %s' % response.text)
                    return ''
            except(ValueError, TypeError):
                log(u'json 解析失败: %s' % response.text)
                if repeat_times < max_try_times:
                    time.sleep(time_interval)
                    log(u'尝试再次提交买单(最多尝试 [%s] 次)...' % max_try_times)
                    repeat_times += 1
                else:
                    raise RuntimeError(u'尝试提交买单失败，请检查网络')

    def buy(self, order: Order) -> Order:
        """
        提交订单
        :param type
        :param order:
        :return:
        """
        params = {
            'type': 'BUY',
            'amount': str(order.amount),
            'price': str(order.price),
        }
        return self._order(params, order.pair)

    def sell(self, order: Order) -> Order:
        """
        提交订单
        :param type
        :param order:
        :return:
        """
        params = {
            'type': 'SELL',
            'amount': str(order.amount),
            'price': str(order.price),
        }
        return self._order(params, order.pair)

    def cancel(self, order_id: str, pair='', type='') -> bool:
        """
        取消单笔订单
        :param order_id:
        :param pair:
        :param type:
        :return:
        """
        url = 'https://api.kucoin.com/v1/cancel-order?symbol=%s' % pair
        params = {
            'orderOid': str(order_id),
            'type': type,
        }

        auth_header = get_sign(params, '/v1/cancel-order')
        response = http.post(url, params=params, headers=auth_header)

        repeat_times = 0
        max_try_times = 2
        time_interval = 1
        while True:
            try:
                json_result = response.json()
                if json_result['success'] is True:
                    log(u'取消订单成功, order_id:%s,\t currency_pair:%s' % (order_id, pair))
                    return True
                else:
                    log(u'接口返回code异常 %s' % response.text)
                    return False
            except(ValueError, KeyError, TypeError):
                log(u'json 解析失败: %s' % response.text)
                if repeat_times < max_try_times:
                    time.sleep(time_interval)
                    log(u'尝试再次撤销订单(最多尝试 [%s] 次)...' % max_try_times)
                    repeat_times += 1
                else:
                    raise RuntimeError(u'尝试撤销订单失败，请检查网络')

    def status(self, order_id: str, pair='', type=''):
        """
        查看订单状态
        :param order_id:
        :param pair:
        :param type:
        :return:
        """
        url = 'https://api.kucoin.com/v1/order/detail'
        params = {
            'orderOid': str(order_id),
            'symbol': pair,
            'type': type
        }

        response = http.get(url, params=params, headers=get_sign(params, '/v1/order/detail'))

        repeat_times = 0
        max_try_times = 5
        time_interval = 0.5
        while True:
            try:
                json_result = response.json()
                if json_result['success'] is True:
                    if json_result['data']['isActive']:
                        return OrderStatus(0)
                    else:
                        return OrderStatus(2)
                else:
                    log(u'接口返回code异常 %s' % response.text)
                    return False
            except(ValueError, KeyError, TypeError):
                log(u'json 解析失败: %s' % response.text)
                if repeat_times < max_try_times:
                    time.sleep(time_interval)
                    log(u'尝试再次检查订单(最多尝试 [%s] 次)...' % max_try_times)
                    repeat_times += 1
                else:
                    raise RuntimeError(u'尝试检查订单失败，请检查网络')


class KuCoinAccountService(AccountService):
    def __init__(self, account):
        super().__init__(account)

    def get_balance_by_coins(self, coins):
        """

        :param coins:
        :return:
        """
        url = 'https://api.kucoin.com/v1/account/%s/balance' % coins

        auth_header = get_sign({}, '/v1/account/%s/balance' % coins)

        response = http.get(url=url, headers=auth_header, proxies=proxy)
        print(response.text)

        repeat_times = 0
        max_try_times = 5
        time_interval = 0.5
        while True:
            try:
                json_result = response.json()
                if json_result.get('success') is True:
                    ret = json_result['data']
                    r = {}
                    if ret and type(ret) is dict and len(ret) > 0:
                        filtered = {k.upper(): v for k, v in ret.items() if k in coins}
                        for k, v in filtered.items():
                            b = Balance()
                            b.symbol = k
                            b.available = Decimal(v.get('available'))
                            b.freeze = Decimal(v.get('frozen'))
                            b.total = b.available + b.freeze
                            r.update({k: b})
                    else:
                        log(u'未获取到正确的余额信息: %s' % response.text)
                    return r
                else:
                    log(u'接口返回code异常 %s' % response.text)
            except(ValueError, TypeError):
                log(u'json 解析失败: %s' % response.text)
                if repeat_times < max_try_times:
                    time.sleep(time_interval)
                    log(u'尝试再次查询余额(最多尝试 [%s] 次)...' % max_try_times)
                    repeat_times += 1
                else:
                    raise RuntimeError(u'尝试查询余额失败，请检查网络')




if __name__ == '__main__':
    log(u'主函数启动...')
    PAIR = 'DAG-ETH'
    target = 'DAG'
    base = 'ETH'

    # marketService = KuCoinMarketService()
    # print(marketService.get_ticker(PAIR))
    Account = Account('account', apiKey, secret)
    AccountService = KuCoinAccountService(Account)
    AccountService.get_balance_by_coins('BTC')