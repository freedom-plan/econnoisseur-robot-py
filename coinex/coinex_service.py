# coding=utf-8
import hashlib
import random
import threading
from configparser import ConfigParser
from decimal import *
from functools import *

import requests
import time

from logger import TimeLogger
from service.common_service import *
from util.json_util import *

# 设置全局日志类
log = TimeLogger('../logs/coinex.log').timeLog

# 设置全局请求类
http = requests.session()
user_agent_header = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36'
}
http.headers.update(user_agent_header)

cfg = ConfigParser()
cfg.read('../conf.ini')


def generate_auth(params, secret):
    sorted_items = sorted(params.items())
    plain_text = reduce(lambda x, y: x + '&' + y, list(map(lambda x: x[0] + '=' + x[1], sorted_items))) + '&secret_key=' + secret
    md5_text = hashlib.md5(plain_text.encode(encoding='utf-8')).hexdigest().upper()
    return {'authorization': md5_text}


def is_safe_wide(sell1, buy1):
    wide = (Decimal(sell1) - Decimal(buy1)).quantize(Decimal('0.00000000'))
    ret = False
    if wide >= Decimal('0.00000002'):
        ret = True
    log(u'正在检查盘口宽度是否合适做单：%s' % repr(ret))
    return ret


def get_safe_average(num1: Decimal, num2: Decimal) -> Decimal:
    return ((Decimal(num1) + Decimal(num2)) / Decimal('2.0')).quantize(Decimal('0.00000000'), rounding=ROUND_UP)


def max_can_deal_num(target_coin, base_coin, price, sell_account_service, buy_account_service):
    target_coin = target_coin.upper()
    base_coin = base_coin.upper()

    t_status = sell_account_service.get_balance_by_coins(target_coin)
    sell_balance = t_status.get(target_coin)
    s_available = sell_balance.available if sell_balance else Decimal('0')
    log(u'卖单账户: %s\t剩余(%s):\t%s' % (sell_account_service.name, target_coin, s_available))

    b_status = buy_account_service.get_balance_by_coins(base_coin)
    buy_balance = b_status.get(base_coin)
    b_available = buy_balance.available if buy_balance else Decimal('0')
    log(u'买单账户: %s\t剩余(%s):\t%s' % (buy_account_service.name, base_coin, b_available))

    # safe count is min(buy_acc has enough base coin, and sell_acc has enough target_coin)
    max_num = (min(sell_balance.available, buy_balance.available / Decimal(price))).quantize(Decimal('0.000'), rounding=ROUND_DOWN)
    log(u'本次最多能支付币个数\t%s' % max_num)
    # *Decimal(str(round(random.uniform(0.600, 0.920), 3)))).quantize(Decimal('0.000'), rounding=ROUND_DOWN)
    return max_num


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
                    log(u'下单成功, op: sell,\tcurrency_pair:%s,\t count: %s' % (order.pair, str(order.amount)))
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


def fast_step_exchange_by_multi_thread(currency_pair, accounts, target_coin='', base_coin=''):
    if not (isinstance(accounts, list) or isinstance(accounts, tuple)):
        accounts = [accounts]

    # init market service
    market_service = CoinExMarketService()
    order_services = [CoinExOrderService(acc) for acc in accounts]
    account_services = [CoinExAccountService(acc) for acc in accounts]

    inner_circulation_count = 0
    accumulated_amount = Decimal('0')
    # for i in range(1):
    while True:
        ticker = market_service.get_ticker(currency_pair)
        if is_safe_wide(ticker.sellPrice, ticker.buyPrice):
            # 设置买卖账户下标
            sell_index = (inner_circulation_count + 0) % len(accounts)
            buy_index = (inner_circulation_count + 1) % len(accounts)
            # log(u'卖单账户->[%s]\t买单账户->[%s]' % (accounts[sell_index].name, accounts[buy_index].name))

            # 设置价格
            price = get_safe_average(ticker.sellPrice, ticker.buyPrice)

            # maxCount = random.randint(650, 750)
            # maxCount = 10.21
            # maxCount = round(random.uniform(39.91, 40.11), 3)
            # 最大操作量
            max_count = max_can_deal_num(target_coin, base_coin, price, account_services[sell_index], account_services[buy_index])
            # 下单数量
            # deal_count = (max_count * Decimal(str(round(random.uniform(0.600, 0.920), 3)))).quantize(Decimal('0.000'), rounding=ROUND_DOWN)
            deal_count = (max_count * Decimal(str(round(random.uniform(0.100, 0.220), 3)))).quantize(Decimal('0.000'), rounding=ROUND_DOWN)
            # 特定币种有单笔交易量规定，如：不低于两百，小数不超过3位
            if deal_count < 200:
                log(u'deal_count is less than 200')
                break

            log(u'第 [%s] 次执行价: [%s], 执行量: [%s], 最大操作空间: [%s]' % (inner_circulation_count + 1, str(price), str(deal_count), max_count))

            # 设置卖单
            sell_order = Order()
            sell_order.amount = deal_count
            sell_order.price = price
            sell_order.is_limit_order = True
            sell_order.is_sell_order = True
            sell_order.pair = currency_pair
            t_sell = threading.Thread(target=order_services[sell_index].sell, args=(sell_order,), name=accounts[sell_index].name)

            # 设置买单
            buy_order = Order()
            buy_order.amount = deal_count
            buy_order.price = price
            buy_order.is_limit_order = True
            buy_order.is_sell_order = False
            buy_order.pair = currency_pair
            t_buy = threading.Thread(target=order_services[buy_index].buy, args=(buy_order,), name=accounts[buy_index].name)

            t_sell.start()
            t_buy.start()

            t_sell.join()
            t_buy.join()
            accumulated_amount += deal_count
            inner_circulation_count += 1
            log(u'$$$> 第 %s 次执行交易成功, Uptime累计刷单数量:%s\t准备进行下一轮订单...\n' % (inner_circulation_count, accumulated_amount))
            time.sleep(555555)
        else:
            log(u'盘口宽度不够，暂停交易1s，请等待...\n')
            time.sleep(1)
        time.sleep(1)


if __name__ == '__main__':
    log(u'主函数启动...')
    PAIR = 'CARDBTC'
    target = 'CARD'
    base = 'BTC'

    Q45Acc = Account('Q450382690', cfg.get('coinex', 'Q45-apiKey'), cfg.get('coinex', 'Q45-secretKey'))
    SnormanAcc = Account('Snorman', cfg.get('coinex', 'Snorman-apiKey'), cfg.get('coinex', 'Snorman-secretKey'))
    WhulongAcc = Account('whulong', cfg.get('coinex', 'Whulong-apiKey'), cfg.get('coinex', 'Whulong-secretKey'))

    # fast_step_exchange_by_multi_thread(PAIR, [Q45Acc, SnormanAcc], target, base)
    # fast_step_exchange_by_multi_thread(PAIR, WhulongAcc, target, base)

    # market
    # marketService = CoinExMarketService()
    # ticker = marketService.get_ticker(pair=PAIR)
    # log(u'ticker: %s' % json.dumps(ticker, cls=ExtendJSONEncoder))

    # account
    # mainAcc = Account('norman', cfg.get('coinex', 'Q45-apiKey'), cfg.get('coinex', 'Q45-secretKey'))
    # accountService = CoinExAccountService(mainAcc)
    # balance = accountService.get_balance_by_coins(['cet', 'nano', 'usdt'])
    # log(u'balance of cet: %s' % json.dumps(balance, cls=ExtendJSONEncoder))

    # order
    orderService = CoinExOrderService(WhulongAcc)
    print(orderService.mining_difficult())
    # orderService.mining_difficult()
    # sellOrder = Order()
    # sellOrder.pair = PAIR
    # sellOrder.amount = 1
    # sellOrder.price = 2 * ticker.sellPrice
    # sellOrder.is_limit_order = True
    # sellOrder.is_sell_order = True
    #
    # sellOrderId = orderService.sell(sellOrder)
    # log(u'sellResult %s' % sellOrderId)
    # sellOrderStatus = orderService.status(sellOrderId, PAIR)
    # log(u'sellOrderStatus %s' % sellOrderStatus)
    #
    # cancelStatus = orderService.cancel(sellOrderId, PAIR)
    # log(u'cancelStatus: %s' % cancelStatus)
