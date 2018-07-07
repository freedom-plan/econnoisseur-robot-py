# coding=utf-8

from enum import Enum, unique


class Account(object):
    def __init__(self, name, api_key, secret_key):
        self.name = name
        self.secretKey = secret_key
        self.apiKey = api_key


class Depth(object):
    def __init__(self):
        self.asks = []
        self.bids = []


class Order(object):
    def __init__(self):
        self.pair = None
        self.is_limit_order = False
        self.is_sell_order = False
        self.price = None
        self.amount = None


@unique
class OrderStatus(Enum):
    Open = 0
    PartDeal = 1
    Done = 2
    Cancel = 3


class Ticker(object):
    def __init__(self):
        self.timestamp = None
        self.percent = None
        self.vol = None
        self.sellAmount = None
        self.sellPrice = None
        self.buyAmount = None
        self.buyPrice = None
        self.low = None
        self.high = None
        self.last = None
        self.pair = None

    def __str__(self):
        return self.__dict__


class Balance(object):
    def __init__(self):
        self.symbol = None
        self.freeze = None
        self.available = None
        self.total = None
