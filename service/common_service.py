# coding=utf-8

from dto.common import *


class MarketService(object):
    def get_ticker(self, pair: str) -> Ticker:
        """ 获取指定币种的ticker

        :rtype: Ticker 详情
        :param pair: 交易对
        """
        raise RuntimeError('Not implement yet!')

    def get_depth(self, pair: str) -> list:
        """ 获取市场深度

        :param pair: coin pair symbol
        :rtype: list Depth list
        """
        raise RuntimeError('Not implement yet!')


class AccountService(object):
    def __init__(self, account):
        self.name = account.name
        self._secretKey = account.secretKey
        self._apiKey = account.apiKey

    def _refresh(self):
        raise RuntimeError('Not implement yet!')

    def get_balance_by_coins(self, coins) -> dict:
        """ 获取指定币种余额

        :rtype: dict of coin balance, key-> coin, value-> Balance
        :param coins: coin list
        """
        raise RuntimeError('Not implement yet!')


class OrderService(object):
    def __init__(self, account):
        self.name = account.name
        self._secretKey = account.secretKey
        self._apiKey = account.apiKey

    def buy(self, order: Order) -> str:
        """ 发送买单

        :rtype: str 订单号
        :param order: 订单详情
        """
        raise RuntimeError('Not implement yet!')

    def sell(self, order: Order) -> str:
        """ 发送卖单

        :rtype: str 订单号
        :param order: 订单详情
        """
        raise RuntimeError('Not implement yet!')

    def cancel(self, order_id: str, **kwargs) -> bool:
        """ 取消指定订单

        :type kwargs: 特殊参数
        :param order_id: 订单号
        """
        raise RuntimeError('Not implement yet!')

    def cancel_all(self):
        """ 取消所有未成交订单

        """
        raise RuntimeError('Not implement yet!')

    def status(self, order: Order) -> OrderStatus:
        """ 检查指定订单的状态
        :param order: 待查询的订单信息
        :rtype: object

        """
        raise RuntimeError('Not implement yet!')
