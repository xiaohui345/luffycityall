# -*- coding: utf-8 -*-
# @Author: 曾辉
import os
import sys
from django_redis import get_redis_connection

if __name__ == "__main__":
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "luffycity.settings")
	conn = get_redis_connection('default')
	# conn.flushall()
	print(conn.keys())
	# # Django中的事务
	# try:
	# 	from django.db import transaction
	#
	# 	with transaction.atomic():
	# 		# ORM 的操作
	# 		pass
	# except Exception:
	#
	# 	pass
