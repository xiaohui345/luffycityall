# -*- coding: utf-8 -*-
# @Author: 曾辉
from django.conf.urls import url
from app01.views import course,account,shop,pay,order
from app01 import alipay
app_name = 'luffy01'

urlpatterns = [

    #第二种方式
    url(r'course/$', course.CourseView.as_view({"get":"list"})),
    url(r'course/(?P<pk>\d+)/$', course.CourseView.as_view({"get":"retrieve"})),

    #登录
    url(r'login/$', account.Login.as_view()),
    #注册
    url(r'register/$', account.register.as_view()),
	#
    url(r'micro/$', course.MicroView.as_view({"get":"list"})),
	url(r'micro/(?P<pk>\d+)/$', course.MicroView.as_view({"get": "retrieve","post":"create"})),

    #对某篇文章进行点赞API
    url(r'micro/(?P<pk>\d+)/updown/$', course.UpdownView.as_view()),

    #收藏API
    url(r'micro/(?P<pk>\d+)/collection/$', course.CollectionView.as_view()),

    #支付相关的API    记录全部都放入redis中

    #有两个url的时候 传入参数，才会简单。一个就没必要，并且还复杂了。

    #查看购物车里面的所有记录; 点击加入购物车;#删除购物车里面的记录
    url(r'shopping/$', shop.ShoppingView.as_view()),


    #结算中心，也是存放到redis里面。
    url(r'paying/$', pay.PayingView.as_view()),

	# 结算中心，也是存放到redis里面。
	url(r'order/$', order.OrderView.as_view()),


	#支付宝的跳转页面
	url(r'^pay_result/', alipay.pay_result),
    url(r'^update_order/', alipay.update_order),
]