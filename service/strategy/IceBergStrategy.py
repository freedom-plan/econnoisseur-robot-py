# coding=utf-8
import random
import time
from decimal import Decimal, ROUND_DOWN

from coinex.coinex_service import CoinExAccountService, CoinExMarketService, CoinExOrderService
from logger import log
from service.common_service import *


# 买
# 1 查询ticker
# 2 当last<=最高买入价
# 3 校验余额，设置price 和 amount
# 4 立马挂一个指定深度的订单
# 5 不断查询订单状态
# 6 当离上一个订单价差太多，cancel订单
# 7 当订单完全成交后，继续1~4

def berg_buy(pair: str, base_coin: str, highest: str, depth: str, avg_amount: str, total_base_amount: str, market_service: MarketService,
             order_service: OrderService, account_service: AccountService):
    """

    :param pair: 交易对
    :param base_coin: 本位币种
    :param highest: 最高买入价
    :param depth: 深度 m%
    :param avg_amount: 每笔订单数量均值
    :param total_base_amount: 本位币合计数量
    :param market_service: ms
    :param order_service: os
    :param account_service: as
    """

    highest = Decimal(highest)
    depth = Decimal(depth) / 100
    avg_amount = Decimal(avg_amount)
    total_base_amount = Decimal(total_base_amount)

    log('冰山策略买入模式启动...')

    bc_dict = account_service.get_balance_by_coins(base_coin)

    unperform_base_count = total_base_amount

    while unperform_base_count > 0:
        # 冰山未融化完

        # 获取余额用于购买目标币种
        real_time_base_balance = bc_dict.get(base_coin)
        if not real_time_base_balance or real_time_base_balance.available == 0:
            raise RuntimeError('Balance insufficient')

        balance = real_time_base_balance.available
        log(u'本金(%s)可用余额: %s，可继续策略交易' % (base_coin, real_time_base_balance.available))

        # 获取当前ticker
        ticker = market_service.get_ticker(pair)
        # 设置价格
        if ticker.last > highest:
            # 当前价格超过设定的最高价
            log(u'当前成交价超过设定的最高价: %s > %s, 暂停做盘...\n' % (ticker.last, highest))
            time.sleep(random.randint(1, 10))
            continue
        else:
            log(u'当前最新成交价：%s，可进行冰山策略委托挂单，开始准备订单' % ticker.last)

        price = (ticker.buyPrice * (Decimal('1.0') - depth)).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
        # 设置数量
        if unperform_base_count < avg_amount * Decimal('1.30'):
            # 如果待购买的目标币种数量低于均值的1.3倍，最后一次将全部下单
            log(u'待购买的目标币种数量低于均值的1.3倍，全部下单')
            amount = unperform_base_count
        else:
            # 否则，正常设置每单购买量，在均值的上下
            amount = (avg_amount * Decimal(str(round(random.uniform(0.985, 1.015), 3)))).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
            log(u'正常设置每单购买量，在每笔数量(%s)上下1.5%%波动' % avg_amount)

        log(u'本笔订单(%s)的购买数量: %s' % (base_coin, amount))

        # 判断数量是否满足最小个数限定
        execute_count = (amount / price).quantize(Decimal('0.0000'), rounding=ROUND_DOWN)
        if execute_count <= 1:
            log(u'Sorry，本次订单执行数量低于最小值要求，请调整后继续执行\n')
            break

        # 开始执行订单
        order = Order()
        order.amount = execute_count
        order.is_limit_order = True
        order.is_sell_order = False
        order.pair = pair
        order.price = price
        log(u'本地初始化订单完毕，价格：%s, 数量：%s，发送订单中...' % (order.price, order.amount))

        order_id = order_service.buy(order=order)

        # 订单未执行成功，结束本次挂单
        if not order_id:
            log(u'订单未提交成功，尝试重新计算价格并挂单...\n')
            time.sleep(random.randint(1, 10))
            continue

        order.order_id = order_id
        # 检查订单状态
        status = order_service.status(order)
        while status is not OrderStatus.Done:
            log(u'等待订单完全成交, Status: %s' % status)
            # 在已有未成交单的情况下，如果价格超过设定阈值，且最新成交价低于设定的最高价，取消当前单，重新挂单
            time.sleep(random.randint(1, 10))
            status = order_service.status(order)

        # 订单执行完毕，更新未执行的数量
        if status is OrderStatus.Done:
            # 本块冰上全部融化，继续下一块
            log(u'本块冰山全部融化，继续下一块')
            unperform_base_count -= amount
            # elif status is OrderStatus.PartDeal:
            # unperform_count -= excuted_amount
        log(u'剩余未执行的数量：%s\n' % unperform_base_count)
        if unperform_base_count == 0:
            log(u'恭喜，本次冰山委托全部成交')


if __name__ == '__main__':
    currency_pair = 'CETETH'
    base = 'ETH'
    sky = '0.00024000'
    depth_percentage = '0.01'
    avg_per_order = '0.00025'
    total_base = '0.01'

    acc = Account('test', 'key', 'secret')
    mks = CoinExMarketService()
    ods = CoinExOrderService(acc)
    acs = CoinExAccountService(acc)

    berg_buy(currency_pair, base, sky, depth_percentage, avg_per_order, total_base, mks, ods, acs)
