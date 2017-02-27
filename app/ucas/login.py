'手动改写登陆函数'
import io
import os
import time
import sys
import logging
import itchat
from pyqrcode import QRCode
from itchat.utils import test_connect

logger = logging.getLogger('itchat')

def login(pic_dir):
    '来吧复杂的登陆函数'
    #如果无法链接, 就推出
    if not test_connect():
        logger.info("You can't get access to internet or wechat domain, so exit.")
        sys.exit()
        #确认登陆状态
    uuid = __open_qr(pic_dir)
    logger.info('请扫码')
    yield '/' + pic_dir
    logger.info('开始检测扫码')
    __login_after_qr(uuid, pic_dir)
    os.remove(pic_dir)
    yield

def __open_qr(pic_dir):
    for _ in range(3):
        logger.info('Getting uuid')
        uuid = itchat.get_QRuuid()
        #收到uuid为止
        while uuid is None:
            uuid = itchat.get_QRuuid()
            time.sleep(1)
        logger.info('Getting QR Code')
        #如果成功获取二维码, 跳出循环
        time.sleep(1)
        if __get_qr(uuid, pic_dir):
            break
    #否则重试3次
    else:
        logger.info('Failed to get QR Code, please restart the program')
        sys.exit()
    logger.info('Please scan the QR Code')
    return uuid

def __login_after_qr(uuid, pic_dir):
    waitForConfirm = False
    while True:
        time.sleep(2)
        logger.info('检查登陆状态')
        status = itchat.check_login(uuid)
        if status == '200':
            break
        elif status == '201':
            if waitForConfirm:
                logger.info('请扫码')
                waitForConfirm = True
        elif status == '408':
            logger.info('Reloading QR Code')
            uuid = __open_qr(pic_dir)
            waitForConfirm = False
    userInfo = itchat.web_init()
    itchat.show_mobile_login()
    itchat.get_contact(True)

    msg = 'Login successfully as %s' % userInfo['User']['NickName']
    logger.info(msg)
    itchat.start_receiving()

def __get_qr(uuid, pic_dir):
    qrStorage = io.BytesIO()
    qrCode = QRCode('https://login.weixin.qq.com/l/' + uuid)
    time.sleep(1)
    qrCode.png(qrStorage, scale=10)
    with open(pic_dir, 'wb') as f:
        f.write(qrStorage.getvalue())
    return qrStorage
