# coding=utf-8
import hashlib
import time
from functools import *

import requests

from logger import log
from service.common_service import *
from util.json_util import *

# 设置全局请求类
http = requests.session()
user_agent_header = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36'
}
http.headers.update(user_agent_header)


def generate_auth(params, secret):
    sorted_items = sorted(params.items())
    plain_text = reduce(lambda x, y: x + '&' + y, list(map(lambda x: x[0] + '=' + x[1], sorted_items))) + '&secret_key=' + secret
    md5_text = hashlib.md5(plain_text.encode(encoding='utf-8')).hexdigest().upper()
    return {'authorization': md5_text}


class CoinExMarketService(MarketService):
    def get_ticker(self, pair: str):
        url = 'https://api.coinex.com/v1/market/ticker'
        response = http.get(url, params={'market': pair})

        repeat_times = 0
        while True:
            try:
                json_result = response.json()
                ts = json_result['data']['date']
                sell1 = json_result['data']['ticker']['sell']
                buy1 = json_result['data']['ticker']['buy']
                last_price = json_result['data']['ticker']['last']

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


class CoinExOrderService(OrderService):
    def __init__(self, account):
        super().__init__(account)
        # 请按照 OrderStatus 的顺序进行映射
        self.order_status = ['not_deal', 'part_deal', 'done', 'cancel']

    def buy(self, order: Order):
        url = 'https://api.coinex.com/v1/order/limit'
        params = {
            'access_id': self._apiKey,
            'market': order.pair,
            'type': 'buy',
            'amount': str(order.amount),
            'price': str(order.price),
            'tonce': str(int(round(time.time() * 1000)))
        }

        auth_header = generate_auth(params, self._secretKey)
        response = http.post(url, json=params, headers=auth_header)

        repeat_times = 0
        max_try_times = 1
        time_interval = 1
        while True:
            try:
                json_result = response.json()
                if json_result.get('code') == 0:
                    log(u'下单成功, op: buy,\t currency_pair:%s,\t count: %s' % (order.pair, str(order.amount)))
                    order_id = json_result['data']['id']
                    return order_id
                else:
                    log(u'接口返回code异常 %s' % json.dumps(json_result))
            except(ValueError, TypeError):
                log(u'json 解析失败: %s' % response.text)
                if repeat_times < max_try_times:
                    time.sleep(time_interval)
                    log(u'尝试再次提交买单(最多尝试 [%s] 次)...' % max_try_times)
                    repeat_times += 1
                else:
                    raise RuntimeError(u'尝试提交买单失败，请检查网络')

    def sell(self, order: Order):
        url = 'https://api.coinex.com/v1/order/limit'
        params = {
            'access_id': self._apiKey,
            'market': order.pair,
            'type': 'sell',
            'amount': str(order.amount),
            'price': str(order.price),
            'tonce': str(int(round(time.time() * 1000)))
        }

        auth_header = generate_auth(params, self._secretKey)
        response = http.post(url, json=params, headers=auth_header)

        repeat_times = 0
        max_try_times = 1
        time_interval = 1
        while True:
            try:
                json_result = response.json()
                if json_result.get('code') == 0:
                    log(u'下单成功, op: sell,\t currency_pair:%s,\t count: %s' % (order.pair, str(order.amount)))
                    order_id = json_result['data']['id']
                    return order_id
                else:
                    log(u'接口返回code异常 %s' % json.dumps(json_result))
            except(ValueError, KeyError, TypeError):
                log(u'json 解析失败: %s' % response.text)
                if repeat_times < max_try_times:
                    time.sleep(time_interval)
                    log(u'尝试再次提交卖单(最多尝试 [%s] 次)...' % max_try_times)
                    repeat_times += 1
                else:
                    raise RuntimeError(u'尝试提交卖单失败，请检查网络')

    def cancel(self, order_id: str, pair='') -> bool:
        url = 'https://api.coinex.com/v1/order/pending'
        params = {
            'access_id': self._apiKey,
            'id': str(order_id),
            'market': pair,
            'tonce': str(int(round(time.time() * 1000)))
        }

        auth_header = generate_auth(params, self._secretKey)
        response = http.delete(url, params=params, headers=auth_header)

        repeat_times = 0
        max_try_times = 2
        time_interval = 1
        while True:
            try:
                json_result = response.json()
                result_order_id = json_result['data']['id']
                amount = json_result['data']['amount']
                buy_or_sell = json_result['data']['type']
                log(u'取消订单成功, order_id:%s,\t currency_pair:%s' % (order_id, pair))
                return all([result_order_id, amount, buy_or_sell])
            except(ValueError, KeyError, TypeError):
                log(u'json 解析失败: %s' % response.text)
                if repeat_times < max_try_times:
                    time.sleep(time_interval)
                    log(u'尝试再次撤销订单(最多尝试 [%s] 次)...' % max_try_times)
                    repeat_times += 1
                else:
                    raise RuntimeError(u'尝试撤销订单失败，请检查网络')

    def status(self, order_id: str, pair=''):
        url = 'https://api.coinex.com/v1/order/'
        params = {
            'access_id': self._apiKey,
            'id': str(order_id),
            'market': pair,
            'tonce': str(int(round(time.time() * 1000)))
        }

        response = http.get(url, params=params, headers=generate_auth(params, self._secretKey))

        repeat_times = 0
        max_try_times = 5
        time_interval = 0.5
        while True:
            try:
                json_result = response.json()
                avg_price = json_result['data']['avg_price']
                deal_fee = json_result['data']['deal_fee']
                left = json_result['data']['left']
                status = json_result['data']['status']
                return OrderStatus(self.order_status.index(status))
            except(ValueError, KeyError, TypeError):
                log(u'json 解析失败: %s' % response.text)
                if repeat_times < max_try_times:
                    time.sleep(time_interval)
                    log(u'尝试再次检查订单(最多尝试 [%s] 次)...' % max_try_times)
                    repeat_times += 1
                else:
                    raise RuntimeError(u'尝试检查订单失败，请检查网络')

    def mining_difficult(self):
        url = 'https://api.coinex.com/v1/order/mining/difficulty'
        params = {
            'access_id': self._apiKey,
            'tonce': str(int(round(time.time() * 1000)))
        }

        response = http.get(url, params=params, headers=generate_auth(params, self._secretKey))

        repeat_times = 0
        max_try_times = 5
        time_interval = 0.5
        while True:
            try:
                json_result = response.json()
                if json_result.get('code') == 0:
                    data = json_result.get('data')
                    difficulty = data.get('difficulty')
                    prediction = data.get('prediction')
                    return [difficulty, prediction]
                else:
                    log(u'接口返回code异常 %s' % json.dumps(json_result))
            except(ValueError, KeyError, TypeError):
                log(u'json 解析失败: %s' % response.text)
                if repeat_times < max_try_times:
                    time.sleep(time_interval)
                    log(u'尝试再次查询难度(最多尝试 [%s] 次)...' % max_try_times)
                    repeat_times += 1
                else:
                    raise RuntimeError(u'尝试检查订单失败，请检查网络')


class CoinExAccountService(AccountService):
    def __init__(self, account):
        super().__init__(account)
        self.__balance_url = 'https://api.coinex.com/v1/balance/'

    def get_balance_by_coins(self, coins):
        if not (isinstance(coins, list) or isinstance(coins, tuple)):
            coins = [coins]
        coins = [coin.upper() for coin in coins]
        params = {
            'access_id': self._apiKey,
            'tonce': str(int(round(time.time() * 1000)))
        }

        auth_header = generate_auth(params, self._secretKey)

        response = http.get(self.__balance_url, params=params, headers=auth_header)

        repeat_times = 0
        max_try_times = 5
        time_interval = 0.5
        while True:
            try:
                json_result = response.json()
                if json_result.get('code') == 0:
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
                    log(u'接口返回code异常 %s' % json.dumps(json_result))
            except(ValueError, TypeError):
                log(u'json 解析失败: %s' % response.text)
                if repeat_times < max_try_times:
                    time.sleep(time_interval)
                    log(u'尝试再次查询余额(最多尝试 [%s] 次)...' % max_try_times)
                    repeat_times += 1
                else:
                    raise RuntimeError(u'尝试查询余额失败，请检查网络')


if __name__ == '__main__':
    PAIR = 'CARDBTC'
    # market
    marketService = CoinExMarketService()
    ticker = marketService.get_ticker(pair=PAIR)
    log(u'ticker: %s' % json.dumps(ticker, cls=ExtendJSONEncoder))
