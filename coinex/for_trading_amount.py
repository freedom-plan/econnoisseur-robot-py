import random
import threading
import time
from decimal import Decimal, ROUND_UP, ROUND_DOWN

from coinex.coinex_service import CoinExMarketService, CoinExOrderService, CoinExAccountService
from dto.common import *
from logger import log


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
    return max_num


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
        time.sleep(44444444)
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

    # Q45Acc = Account('Q450382690', cfg.get('coinex', 'Q45-apiKey'), cfg.get('coinex', 'Q45-secretKey'))
    # SnormanAcc = Account('Snorman', cfg.get('coinex', 'Snorman-apiKey'), cfg.get('coinex', 'Snorman-secretKey'))
    # WhulongAcc = Account('whulong', cfg.get('coinex', 'Whulong-apiKey'), cfg.get('coinex', 'Whulong-secretKey'))

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
    # orderService = CoinExOrderService(WhulongAcc)
    # print(orderService.mining_difficult())
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
