# -*- coding: utf-8 -*-
# @Author: 曾辉

from rest_framework.exceptions import AuthenticationFailed
from rest_framework.authentication import BaseAuthentication

from app01 import models


class MyuserAuth(BaseAuthentication):

	def authenticate(self, request):
		# 接收token值用来判断。
		# 这个 request 是新封装的request
		token = request.query_params.get("token")
		# get ，匹配不到的时候会报错.
		t_obj = models.Tokeninfo.objects.filter(tokens=token).first()
		if not t_obj:
			raise AuthenticationFailed({"code":1001,"error":"用户验证失败"})
		return (t_obj.user.username,t_obj)
