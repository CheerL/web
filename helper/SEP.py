# _*_ coding: utf-8 _*_
'国科大教育系统选课程序'
import re
import requests
import lxml
from bs4 import BeautifulSoup as Bs
from .base import info, EXCEPTIONS, TIMEOUT, IntegrityError
from . import models

class UCASSEP(object):
    'UCAS SEP系统'
    user_id = ''
    password = ''
    user_name = ''
    course_list = None
    session = requests.Session()
    is_login = False
    is_course = False
    temp_page = ''

    def _get(self, url, data=None, empty_post_tag=False):
        try:
            if data is None and empty_post_tag is False:
                response = self.session.get(url=url, timeout=TIMEOUT)
            else:
                response = self.session.post(url=url, data=data, timeout=TIMEOUT)
            if response.status_code is 200:
                return response
            else:
                response.raise_for_status()
        except EXCEPTIONS as error:
            info(error, True)

    def _get_json(self, url, data=None, empty_post_tag=False):
        try:
            response = self._get(url, data, empty_post_tag)
            return response.json()
        except EXCEPTIONS:
            info('该网页返回的不是json数据', True)

    def _get_page(self, url, data=None, empty_post_tag=False):
        try:
            response = self._get(url, data, empty_post_tag)
            return Bs(response.text, 'html.parser')
        except EXCEPTIONS:
            info('无法解析该网页', True)

    def __init__(self, user_id, password):
        try:
            self.session.headers.update({
                'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) \
                    AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.75 Safari/537.36',
                'X-Requested-With':'XMLHttpRequest',
                })
            self.user_id = user_id
            self.password = password
            self.login()
            self.login_course()
        except EXCEPTIONS as error:
            info('用户信息错误, {}'.format(error), True)

    def login(self):
        '登陆'
        data = {
            'username': self.user_id,
            'password': self.password,
            'remember': 'checked'
            }
        url = 'http://onestop.ucas.ac.cn/Ajax/Login/0'
        try:
            result = self._get_json(url=url, data=data)
            if result['f'] is True:
                self.is_login = True
                soup = self._get_page(result['msg'])
                self.temp_page = result['msg']
                self.user_name = str(soup.find('li', 'btnav-info').contents[0])\
                    .replace('\r', '').replace('\n', '').replace('\t', '').replace(' ', '')\
                    .replace(u'\x80', '').replace(u'\x90', '').replace(u'\xa0', ' ')
                info('%s登陆成功' % self.user_name)
            else:
                raise NotImplementedError(result['msg'])
        except EXCEPTIONS as error:
            info(error, True)

    def logout(self):
        '退出登陆'
        url = 'http://sep.ucas.ac.cn/logout?o=platform'
        self._get(url=url)
        self.is_login = False
        info('{}退出登陆'.format(self.user_name))

    def login_course(self):
        '登陆至选课系统'
        if self.is_login is False:
            info('尚未成功登陆SEP')
            self.login()
        else:
            if not self.is_course:
                try:
                    url = 'http://sep.ucas.ac.cn/portal/site/226/821'
                    soup = self._get_page(url)
                    reDirUrl = soup.find('h4').contents[1].get('href')
                    self._get(reDirUrl)
                    self.is_course = True
                except EXCEPTIONS:
                    self.is_login = False
                    self.is_course = False
                    info('登陆SEP系统失效, 重新登陆')
                    self.login()

    def is_chosen(self, course):
        '查看该课程是否已经选上'
        if not isinstance(course, str):
            course = str(course)
        if not self.course_list:
            self.get_course_list()
        for item in self.course_list:
            if item['num'] == course:
                info('{}已经选上'.format(item['name']))
                result = True
                break
        else:
            info('编号为{}的课程未选上'.format(course))
            result = False
        return result

    def add_course(self, course):
        '选课'
        if self.is_chosen(course):
            return True
        else:
            data = {
                'deptIds':'910',
                'sids':course
            }
            url = 'http://jwxk.ucas.ac.cn/courseManageBachelor/saveCourse?s='
            try:
                soup = self._get_page(url=url, data=data)
                if str(soup.find('title').contents[0]).find('Apache Tomcat') is not -1:
                    raise NotImplementedError('尚未开放选课, 或课程编号' + course + '有误')
                if len(soup.find('label', 'success').contents) is not 0:
                    info(soup.find('label', 'success').contents[0])
                    return True
                elif len(soup.find('label', 'error').contents) is not 0:
                    info(soup.find('label', 'error').contents[0])
                    return False
                else:
                    raise NotImplementedError('获取选课结果时出现异常错误')
            except EXCEPTIONS as error:
                info(error)
                return False

    def drop_course(self, course):
        '退课'
        if self.is_chosen(course):
            url = 'http://jwxk.ucas.ac.cn/courseManageBachelor/del/' + course + '?s='
            try:
                soup = self._get_page(url)
                if len(soup.find('label', 'success').contents) is not 0:
                    info(soup.find('label', 'success').contents[0])
                    return True
                elif len(soup.find('label', 'error').contents) is not 0:
                    info(soup.find('label', 'error').contents[0])
                    return False
                else:
                    raise NotImplementedError('获取退课结果时出现异常错误')
            except EXCEPTIONS as error:
                info(error)
                return True
        else:
            info('课程未选上, 无法退课')
            return False

    def save_course(self, num):
        '储存指定课程'
        def get_course_detail(num):
            '获取指定课程的具体信息'
            link = 'http://jwxk.ucas.ac.cn/course/coursetime/' + str(num)
            tree = lxml.etree.HTML(self.session.get(url=link).content)
            if tree.xpath('//title/text()')[0] != '课程时间地点信息-选课系统'\
            or not tree.xpath('//th'):
                return None
            name = (tree.xpath('//p/text()'))[0][5:]
            place = tree.xpath('//th[text()="上课地点"]/../td/text()')[0]
            times = [(re.findall(r'(星期.?)：', each)[0], re.findall(r'(\d*)[、节]', each))
                     for each in tree.xpath('//th[text()="上课时间"]/../td/text()')]
            weeks_temp = tree.xpath('//th[text()="上课周次"]/../td/text()')[0].split('、')
            weeks = (int(weeks_temp[0]) - 1, int(weeks_temp[-1]) - 1)
            return dict(name=name, weeks=weeks, place=place, times=times)

        try:
            courese = get_course_detail(num)
            if not courese:
                info('不存在编号%d对应的课程' % num)
                return

        except EXCEPTIONS as error:
            info(error)
            return

        try:
            new_course = models.Course.objects.create(ident=num)
        except EXCEPTIONS:
            new_course = models.Course.objects.get(ident=num)
            if new_course.place:
                info('编号为%d的课程已经存在' % num)
                return

        for times in courese['times']:
            try:
                coursetime = models.Coursetime.objects.get(
                    weekday=models.Weekday.objects.get(day=times[0]),
                    start=int(times[1][0]),
                    end=int(times[1][-1])
                    )
            except models.Coursetime.DoesNotExist:
                coursetime = models.Coursetime.objects.create(
                    weekday=models.Weekday.objects.get(day=times[0]),
                    start=int(times[1][0]),
                    end=int(times[1][-1])
                )
            new_course.coursetimes.add(coursetime)
        new_course.start_week, new_course.end_week = courese['weeks'][0], courese['weeks'][1]
        new_course.name = courese['name']
        new_course.place = courese['place']
        new_course.save()

    def get_course_list(self):
        '获取已选择课程, 并储存'
        self.course_list = list()
        url = 'http://jwxk.ucas.ac.cn/courseManageBachelor/main'
        soup = self._get_page(url)
        pattern = re.compile(r'/course/coursetime/(\d*)')
        for item in soup.find_all('a', href=pattern):
            num = re.findall(pattern, item['href'])[0]
            if not models.Course.objects.filter(ident=num).count():
                self.save_course(num)
            self.course_list.append(num)
        info('%s 课表获取成功' % self.user_name)
        return self.course_list

def main():
    '主函数'
    try:
        #some
            # LCR = UCASSEP('1017801883@qq.com', 'lcr0717')
            # for num in range(131382, 132000):
            #     try:
            #         LCR.save_course(num)
            #     except EXCEPTIONS:
            #         pass
            # pl.run_thread_pool(
            #     [(LCR.save_course, (num,)) for num in range(3246, 50000)],
            #     is_lock=True,
            #     limit_num=8
            #     )
            # num = 666
            # filname = 'file%d' % num
            # with open(filname, 'w+') as file:
            #     for course in models.Course.objects.all():
            #         try:
            #             coursetimes = [
            #                 (times.weekday.index, times.start, times.end)
            #                 for times in course.coursetimes.all()
            #             ]
            #             inf = "ident:%d, name:%s, place:%s, start_week:%d, end_week:%d, coursetimes:%s\n"%(
            #                 course.ident,
            #                 course.name,
            #                 course.place,
            #                 course.start_week,
            #                 course.end_week,
            #                 coursetimes
            #                 )
            #             file.write(inf)
            #         except:
            #             pass
            # print('end %d' % num)
            # with open('file666', 'r') as file:
            #     id_set = set(re.findall(r'ident:(\d*),', file.read()))
            # with open("file_w", 'w+') as file_write:
            #     with open('file0', 'r') as file_read:
            #         for line in file_read.readlines():
            #             try:
            #                 line_id = re.findall(r'ident:(\d*),', line)[0]
            #                 if line_id not in id_set:
            #                     file_write.write(line)
            #                     print('write %s' % line_id)
            #             except:
            #                 pass

            # with open('file666', 'r') as f:
            #     id_set = set(re.findall(r'ident:(\d*),', f.read()))
            # with open('file_w', 'w+') as f_w:
            #     with open('file0', 'r') as f_r:
            #         for line in f_r.readlines():
            #             try:
            #                 line_id = re.findall(r'ident:(\d*),', line)[0]
            #                 if line_id not in id_set:
            #                     f_w.write(line)
            #                     info('write %d' % line_id)
            #             except EXCEPTIONS:
            #                 pass
            # from ast import literal_eval
            # filename = 'file_w'
            # with open(filename, 'r') as file_r:
            #     res = re.findall(
            #         r"ident:(\d*), name:(.*?), place:(.*?), start_week:(\d*), end_week:(\d*), coursetimes:(.*?)\n",
            #         file_r.read()
            #         )
            #     for result in res:
            #         ident, name, place, start_week, end_week, coursetimes_temp = result
            #         try:
            #             course = models.Course.objects.create(
            #                 ident=int(ident),
            #                 name=name,
            #                 place=place,
            #                 start_week=int(start_week),
            #                 end_week=int(end_week)
            #             )
            #             coursetimes = literal_eval(coursetimes_temp)
            #             for times in coursetimes:
            #                 try:
            #                     coursetime = models.Coursetime.objects.get(
            #                         weekday=models.Weekday.objects.get(index=int(times[0])),
            #                         start=int(times[1]),
            #                         end=int(times[2])
            #                         )
            #                 except models.Coursetime.DoesNotExist:
            #                     coursetime = models.Coursetime.objects.create(
            #                         weekday=models.Weekday.objects.get(index=int(times[0])),
            #                         start=int(times[1]),
            #                         end=int(times[2])
            #                     )
            #                 finally:
            #                     course.coursetimes.add(coursetime)
            #             course.save()
            #             print('添加课程%s' % ident)
            #         except IntegrityError:
            #             print('error')
        pass
    except EXCEPTIONS as error:
        info(error)

if __name__ == '__main__':
    main()