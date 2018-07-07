from configparser import ConfigParser

import requests

cfg = ConfigParser()
cfg.read('../conf.ini')


def notify_dingtalk_md(body):
    requests.post('https://oapi.dingtalk.com/robot/send?access_token=' + cfg.get('dingtalk', 'token'), json=body)
