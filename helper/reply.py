'程序运行主体'
import re
import os
import time

# from helper.async_itchat import async_itchat as itchat
import itchat
from asgiref.sync import async_to_sync
from helper.helper import HELPER
from helper.models import Message
from helper.setting import EXCEPTIONS, HOST
from helper.utils import async_utils
from helper.voice import auto_chat, voice_recognize

KEYS_1 = ['???', '？？？']


@itchat.msg_register(itchat.content.FRIENDS)
@async_to_sync
async def add_friend(msg):
    '自动接受好友申请'
    itchat.add_friend(**msg['Text'])
    user = msg['Text']['autoUpdate']
    await HELPER.send('Nice to see you! 你可以试着输入"???"来查看帮助信息', user['UserName'])
    await HELPER.logger.info('添加新好友%s' % (user['NickName']))


@itchat.msg_register([itchat.content.TEXT, itchat.content.VOICE])
@async_to_sync
async def reply(msg):
    try:
        message_type = msg['Type']
        send_user = itchat.search_friends(userName=msg['FromUserName'])
        user = msg['User']
        name = user['RemarkName'] if user['RemarkName'] else user['NickName']
        if message_type == itchat.content.TEXT:
            await text_reply(msg, message_type, name, user, send_user)
        elif message_type == itchat.content.VOICE:
            await voice_reply(msg, message_type, name, user, send_user)

    except EXCEPTIONS as error:
        await HELPER.error_report(error, msg['FromUserName'], False)

async def text_reply(msg, message_type, name, user, send_user):
    '文字消息的回复'
    text = msg['Text']
    await HELPER.create_message(text, message_type,
                                name, user, send_user)

    if '???' in text or '？？？' in text:
        msg = '功能有: ' + ', '.join([', '.join(each) for each in [KEYS_1[:1]]])
        await HELPER.send(msg, send_user)
    else:
        if HELPER.robot.settings.rebot_reply:
            try:
                answer, result = auto_chat(text, send_user['NickName'])
            except Exception as error:
                answer, result = str(error), False

            if result:
                await HELPER.send(answer, send_user)
            else:
                await HELPER.logger.info(answer)
                await HELPER.send('我不知道该怎么接', send_user)

async def voice_reply(msg, message_type, name, user, send_user):
    '语音消息的回复'
    voice_path = 'media/voices/%s' % msg['FileName']
    msg.download(voice_path)
    while not os.path.exists(voice_path):
        pass
    await HELPER.create_message('语音:' + voice_path, message_type,
                                name, send_user, user)
    try:
        voice_url = '%s/%s' % (HOST, voice_path)
        translate, result = voice_recognize(voice_url)
    except Exception as error:
        translate, result = str(error), False

    if result:
        await HELPER.send('你说的是:' + translate, send_user)
        await HELPER.logger.info('收到来自%s的语音, 内容: %s' % (name, translate))
        if HELPER.robot.settings.voice_reply:
            msg['Text'] = translate
            await text_reply(msg, itchat.content.TEXT,
                             name, user, send_user)
    else:
        await HELPER.logger.info(translate)
        await HELPER.send('我没有听懂', send_user)
