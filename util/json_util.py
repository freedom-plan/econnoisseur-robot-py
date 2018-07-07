# coding=utf-8
import json
from dto.common import *
from decimal import Decimal
from functools import singledispatch


@singledispatch
def convert(o):
    raise TypeError('can not convert type')


# @convert.register(datetime)
# def _(o):
#     return o.strftime('%b %d %Y %H:%M:%S')

@convert.register(Order)
def _(o):
    return o.__dict__


@convert.register(Ticker)
def _(o):
    return o.__dict__


@convert.register(Account)
def _(o):
    return o.__dict__


@convert.register(Balance)
def _(o):
    return o.__dict__


@convert.register(Depth)
def _(o):
    return o.__dict__


@convert.register(Decimal)
def _(o):
    return float(o)


class ExtendJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return convert(obj)
        except TypeError:
            return super(ExtendJSONEncoder, self).default(obj)
