# -*- coding: utf-8 -*-
# @Author: 曾辉
import json
import datetime
import time
from django.shortcuts import redirect
from django_redis import get_redis_connection
from django.conf import settings
from django.db.models import F
from rest_framework.response import Response
from rest_framework.views import APIView

from app01 import models
from app01 import alipay
from app01.utils.response_ret import BaseResponse

from app01.utils.userAuth import MyuserAuth


class OrderView(APIView):
	authentication_classes = [MyuserAuth]
	conn = get_redis_connection('default')

	def post(self, request, *args, **kwargs):

		ret = BaseResponse()
		# 1.点击支付后，从前端传过来有 用来抵消支付的贝里；已经总共需要支付的价格
		try:
			user_id = request.auth.user.id
			#从前端传过来的 贝里，已经 需要支付的总金额;需要与后端进行验证
			balance = float(request.data.get("balance"))
			allmoney = float(request.data.get("allmoney"))

			# 2.数据验证；验证当前用户是否有 与前端传过来的一样的贝里
			user_balance = models.Userinfo.objects.filter(id=user_id).first().balance
			if user_balance < balance:
				# 用户账户里面没有足够的贝里
				ret.code = 1002
				ret.error = "该账户余额不足"
				return Response(ret.dict)
			# 去数据库里面去验证                               #用户是否用
			# 3.去结算中心里面取相应的数据，并进行验证; 验证当前的课程ID是否存在，以及价格策略ID是否存在，和使用的优惠卷ID是否存在。
			coupon__id_list = []
			course_obj_list = []
			all_price = 0
			for key in self.conn.scan_iter(settings.PAYMENT_CRA_NAME % (user_id, "*")):
				course_dict = {}
				title = self.conn.hget(key, "title").decode("utf-8")
				course_id = self.conn.hget(key, "course_id").decode("utf-8")
				c_time = self.conn.hget(key, "period").decode("utf-8")
				period_display = self.conn.hget(key, "period_display").decode("utf-8")
				price_id = self.conn.hget(key, "price_policyid").decode("utf-8")
				price = float(self.conn.hget(key, "price").decode("utf-8"))

				coupon_id = self.conn.hget(key, "default_coupon").decode("utf-8")

				coupon_dict = json.loads(self.conn.hget(key, "coupon").decode("utf-8"))
				c_obj = models.Course.objects.filter(id=course_id).first()
				p_obj = models.PricePolicy.objects.filter(id=price_id)

				if not c_obj:
					ret.code = 1003
					ret.error = "%s课程不存在" % title
					return Response(ret.dict)

				if not p_obj:
					ret.code = 1005
					ret.error = "%s课程价格不存在" % title
					return Response(ret.dict)

				couponused_price = price

				# 使用绑定的优惠卷
				if coupon_id != "0":
					coupon_obj = models.CouponRecord.objects.filter(id=coupon_id).first()
					if not coupon_obj:
						ret.code = 1003
						ret.error = "%s课程的优惠卷不存在" % title
						return Response(ret.dict)
					# 优惠卷存在
					coupon__id_list.append(coupon_id)
					coupon_item = coupon_dict[coupon_id]
					c_type = coupon_item["c_type"]
					if c_type == 0:
						# 立减
						money_equivalent_value = coupon_item["money_equivalent_value"]
						couponused_price = price - money_equivalent_value
						if couponused_price < 0:
							couponused_price = 0
					elif c_type == 1:
						# 满减
						money_equivalent_value = coupon_item["money_equivalent_value"]
						minimum_consume = coupon_item["minimum_consume"]
						if price < minimum_consume:
							ret.code = 1005
							ret.error = "%s课程的费用达不到满减的要求" % title
							return Response(ret.dict)
						# 达到满减的要求：
						couponused_price = price - money_equivalent_value
					else:
						# 折扣
						off_percent = coupon_item["off_percent"]
						couponused_price = price * (off_percent / 100)
					# 验证完后获取每个商品的原价和优惠后的价格
					# 优惠后的价格
				# 没有使用绑定的优惠卷

				course_dict["c_obj"] = c_obj
				course_dict["price"] = price
				course_dict["couponused_price"] = couponused_price
				course_dict["c_time"] = c_time
				course_dict["period_display"] = period_display
				course_obj_list.append(course_dict)
				all_price += couponused_price


			# print(course_obj_list)
			# print(all_price)

			# 4.验证全局优惠卷是否存在，以及最终的价格
			global_coupon_id = self.conn.hget(settings.GLOBAL_COUPON % user_id, "default_coupon").decode("utf-8")

			# print(global_coupon_item)

			end_price = all_price
			# 使用全站的优惠卷
			if global_coupon_id != "0":
				global_coupon_obj = models.CouponRecord.objects.filter(id=global_coupon_id)
				global_coupon_dict = json.loads(self.conn.hget(settings.GLOBAL_COUPON % user_id, "coupon").decode("utf-8"))
				global_coupon_item = global_coupon_dict[global_coupon_id]
				if not global_coupon_obj:
					ret.code = 1006
					ret.error = "全站优惠卷已经不存在"
				coupon__id_list.append(global_coupon_id)
				c_type = global_coupon_item["c_type"]
				if c_type == 0:
					# 立减
					money_equivalent_value = global_coupon_item["money_equivalent_value"]
					end_price = all_price - money_equivalent_value
					if end_price < 0:
						end_price = 0
				elif c_type == 1:
					# 满减
					money_equivalent_value = global_coupon_item["money_equivalent_value"]
					minimum_consume = global_coupon_item["minimum_consume"]
					if all_price < minimum_consume:
						ret.code = 1005
						ret.error = "结算费用达不到满减的要求"
						return Response(ret.dict)
					# 达到满减的要求：
					end_price = all_price - money_equivalent_value
				else:
					# 折扣
					off_percent = global_coupon_item["off_percent"]
					end_price = all_price * (off_percent / 100)

			# print(end_price)
			# 贝里抵扣;为最后支付的价格
			pay_price = end_price - balance
			print(pay_price)
			if pay_price <= 0:
				# 相当于全部抵消
				pay_price = 0
			if pay_price != allmoney:
				# 前端显示的最终支付的钱 不等于 后端计算的钱的时候就报错
				ret.code = 1100
				ret.error = "金额不合法"
				return Response(ret.dict)
			print(pay_price)

			#对 数据库里面的操作必须是原子性操作。
			# Django中的事务

			#生成订单号
			order_number = "x2" + str(time.time())
			try:
				from django.db import transaction

				with transaction.atomic():
					# ORM 的操作
					# 生成订单
					order_obj = models.Order.objects.create(payment_type=1, order_number=order_number,
					                                        account=request.auth.user,
					                                        actual_amount=pay_price, status=1)

					# 每一个课程分别生成订单详情
					for item in course_obj_list:
						obj = item["c_obj"]
						price = item["price"]
						couponused_price = item["couponused_price"]
						c_time = item["c_time"]
						period_display = item["period_display"]
						models.OrderDetail.objects.create(order=order_obj, content_object=obj,original_price=price,price=couponused_price,valid_period= c_time,
						                                  valid_period_display=period_display)

					#如果有贝里支付；就修改用户账号里面的贝里
					if balance >0:
						#有贝里支付
						models.Userinfo.objects.filter(id=request.auth.user.id).update(balance = F("balance") - balance)

					#以及修改使用后的优惠卷的状态
					for coupon_id in coupon__id_list:
						models.CouponRecord.objects.filter(account=request.auth.user,id=coupon_id).update(status=1)
			except Exception:
				ret.code = 1200
				ret.error = "数据库操作失败"

			if pay_price ==0:
				ret.data = "支付成功"
				return Response(ret.dict)

			#pay_price>0，用第三方的支付宝支付; 即跳转到第三方去支付

			url = alipay.index(request,"课程",pay_price,order_number)
			return redirect(url)

		except Exception:
			ret.code=1111
			ret.error="支付失败"
		return Response(ret.dict)
