from django.db import models

class Helper_User(models.Model):
    user_name = models.CharField(max_length=20)
    user_id = models.EmailField()
    password = models.CharField(max_length=20)
    nick_name = models.CharField(max_length=20)
    course_list = models.TextField(default='[]')
    remind_list = models.TextField(default='[]')
    is_open = models.BooleanField(default=True)
    have_remind = models.BooleanField(default=False)
    wx_UserName = models.CharField(max_length=50, default='')

    def __str__(self):
        return "%s" % self.nick_name