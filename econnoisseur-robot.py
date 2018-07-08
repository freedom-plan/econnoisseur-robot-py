# coding=utf-8

from service.strategy.for_trading_amount import *
from configparser import ConfigParser
from conf.setting import BASE_CONF
cfg = ConfigParser()
cfg.read(BASE_CONF)


if __name__ == '__main__':
    log(u'主函数启动...')
    PAIR = 'CARDBTC'
    target = 'CARD'
    base = 'BTC'

    Q45Acc = Account('Q450382690', cfg.get('coinex', 'Q45-apiKey'), cfg.get('coinex', 'Q45-secretKey'))
    SnormanAcc = Account('Snorman', cfg.get('coinex', 'Snorman-apiKey'), cfg.get('coinex', 'Snorman-secretKey'))
    WhulongAcc = Account('whulong', cfg.get('coinex', 'Whulong-apiKey'), cfg.get('coinex', 'Whulong-secretKey'))

    # fast_step_exchange_by_multi_thread(PAIR, [Q45Acc, SnormanAcc], target, base)
    fast_step_exchange_by_multi_thread(PAIR, WhulongAcc, target, base)
