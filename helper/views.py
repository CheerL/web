import os
import json
import itchat
from ast import literal_eval
from channels import Group
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from .wheel import parallel as pl
from .models import Robot
from .main import HELPER
from .base import info, EXCEPTIONS, QR_pic, WX_pic, log_read, pkl_path, str_multi_replace
from . import tests

MSG_init = '请点击登录按钮'
MSG_error = '错误,请重新登录'
MSG_login = '小助手运行中'
MSG_scan = '请扫描二维码'
MSG_logout = '小助手成功退出'
MSG_reload = '重新启动'
MSG_remind = '小助手提醒中'
MSG_confirm = '请在手机上确认登录'

ITEM_LIST = [
    {'text': '登录', 'id': 'login'},
    {'text': '聊天', 'id': 'chat'},
    {'text': '日志', 'id': 'log'},
    {'text': '设置', 'id': 'setting'},
]

# Create your views here.


def index(request):
    'app初始界面, 有可能是唯一的界面'
    if HELPER.IS_LOGIN:
        return run_page(request)
    else:
        return login_page(request)
# 跳转页面部分


def run_page(request):
    if not HELPER.IS_LOGIN:
        return render(request, 'helper/return_to_login.html')
    res = dict(
        status=HELPER.IS_LOGIN,
        item_list=ITEM_LIST,
        page='login'
    )
    return render(request, 'helper/run.html', res)


def login_page(request):
    status = HELPER.IS_LOGIN
    msg = MSG_login if status else MSG_init
    res = dict(
        status=status,
        msg=msg,
        pic=WX_pic,
    )
    return render(request, 'helper/login.html', res)


def log_page(request):
    if not HELPER.IS_LOGIN:
        return render(request, 'helper/return_to_login.html')
    return render(request, 'helper/log.html')


def chat_page(request):
    if not HELPER.IS_LOGIN:
        return render(request, 'helper/return_to_login.html')
    return render(request, 'helper/chat.html')


def setting_page(request):
    if not HELPER.IS_LOGIN:
        return render(request, 'helper/return_to_login.html')
    item_list = vars(HELPER.settings).items()
    bool_list = [
        {
            'name': name,
            'show': HELPER.settings.trans_to_chinese(name),
            'val': val
        }
        for name, val in item_list if isinstance(val, bool)
    ]
    num_list = [
        {
            'name': name,
            'show': HELPER.settings.trans_to_chinese(name),
            'val': val if name != 'FLEXIBLE_DAY' else HELPER.settings.trans_flexible_day()
        }
        for name, val in item_list if not isinstance(val, bool) and name != 'LAST_UPDATE'
    ]
    show_list = []
    return render(
        request,
        'helper/setting.html',
        {'bool_list': bool_list, 'num_list': num_list, 'show_list': show_list}
    )


# 登陆 api
@csrf_exempt
def login(request):
    '终于登录了'
    if request.method == 'GET':
        if not HELPER.IS_LOGIN:
            return render(request, 'helper/return_to_login.html')
        else:
            return login_page(request)
    else:
        def qr_func(uuid, status, qrcode):
            if qrcode:
                info('成功获取二维码')
                with open(QR_pic, 'wb') as pic:
                    pic.write(qrcode)
                Group('login').send({'text': json.dumps(dict(
                    msg=MSG_scan,
                    pic=QR_pic
                ))})
            else:
                info('等待确认登录')
                Group('login').send({'text': json.dumps(dict(
                    msg=MSG_confirm,
                    pic=WX_pic
                ))})

        def login_func():
            user = itchat.search_friends()
            robot = Robot.objects.get_or_create(uin=user['Uin'])[0]
            robot.nick_name = user['NickName']
            robot.save()
            HELPER.robot = robot
            HELPER.robot.apply_settings(HELPER.settings)
            info('%s成功登录' % robot.nick_name)
            HELPER.wxname_update()
            HELPER.remind()
            HELPER.IS_LOGIN = True
            if os.path.exists(QR_pic):
                os.remove(QR_pic)
            Group('login').send({'text': json.dumps(dict(
                msg=MSG_login,
                pic=WX_pic
            ))})

        def exit_func():
            HELPER.logout()
            info(MSG_logout)

        def login_main():
            try:
                info('尝试登陆')
                itchat.auto_login(True, pkl_path, False, QR_pic,
                                  qr_func, login_func, exit_func)
                itchat.run(debug=True, blockThread=False)
            except:
                Group('login').send({'text': json.dumps(dict(
                    msg=MSG_error,
                    pic=WX_pic
                ))})

        pl.run_thread([(login_main, ())], name='login', is_lock=False)
        return HttpResponse()


@csrf_exempt
def logout(request):
    '退出登录'
    if request.method == 'GET':
        return render(request, 'helper/return_to_login.html')
    else:
        if HELPER.IS_LOGIN:
            HELPER.logout()
            info(MSG_logout)
        return HttpResponse(MSG_logout)


# 日志 api
def get_log(request, start=0, count=1):
    log_list = log_read(count=int(count), start=int(start))
    return JsonResponse(dict(log_list=log_list))


def get_log_all(request):
    log_list = log_read(count=-1, start=0)
    return HttpResponse('<br>'.join(log_list))


@csrf_exempt
def send_log(request):
    if request.method == 'POST':
        Group('log').send({'text': json.dumps({"msg": request.POST['msg']})})
    return HttpResponse()


# 聊天 api
def chat_user(request):
    def chat_user_head(user):
        HELPER.get_head_img(user['user_name'], user['path'], user['name'])

    user_list = []
    for user in itchat.get_friends():
        temp_dict = {
            'name': user['RemarkName'] if user['RemarkName'] else user['NickName'],
            'nick_name': str_multi_replace(user['NickName']),
            'user_name': user['UserName']
        }
        temp_dict['path'] = 'static/head/%s.png' % temp_dict['nick_name']
        user_list.append(temp_dict)

    req_list = [(chat_user_head, (user,)) for user in user_list]
    pl.run_thread_pool(req_list, is_lock=False)

    return JsonResponse(dict(user_list=user_list, count=len(user_list)))


@csrf_exempt
def chat_send(request):
    '主动发送消息'
    try:
        if request.method == 'POST':
            msg = request.POST['msg']
            user = request.POST['user']
            HELPER.send(msg, user)
            return JsonResponse(dict(res=True))
        else:
            raise NotImplementedError('访问错误')
    except EXCEPTIONS as error:
        return JsonResponse(dict(res=False, msg=error))


# 设置api
@csrf_exempt
def setting_change(request):
    if request.method == 'POST':
        items = literal_eval(request.POST['res'])
        for day in ['一', '二', '三', '四', '五', '六', '日', '天']:
            if day in items['FLEXIBLE_DAY']:
                if day == '天':
                    items['FLEXIBLE_DAY'] = '星期日'
                else:
                    items['FLEXIBLE_DAY'] = '星期' + day
                break
        else:
            return JsonResponse({'res': True, 'msg': '灵活调整日期有误'})
        HELPER.settings.change_settings(items)
        HELPER.robot.save_settings(HELPER.settings)
        return JsonResponse({'res': True, 'msg': '修改成功\n' + str(HELPER.settings)})
    else:
        return JsonResponse({'res': False, 'msg': '访问错误'})
