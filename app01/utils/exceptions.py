# -*- coding: utf-8 -*-
# @Author: 曾辉

#自定制的错误需要继承Exception。


class PricePolicyInvalid(Exception):
	def __init__(self,msg):
		self.msg = msg


class ShopNumberInvalid(Exception):
	def __init__(self,msg):
		self.msg = msg