# -*- coding: utf-8 -*-
# @Author: 曾辉
import json
import datetime

from django_redis import get_redis_connection
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ViewSetMixin
from django.conf import settings
from app01.utils.response_ret import BaseResponse
from app01 import models
from app01.utils.userAuth import MyuserAuth

class PayingView(APIView):
	authentication_classes = [MyuserAuth]
	'''
	结算中心
	'''
	conn = get_redis_connection('default')

	def get(self, request, *args, **kwargs):
		'''
		展示结算中心
		:param request:
		:param args:
		:param kwargs:
		:return:
		'''
		ret = BaseResponse()
		try:
			user_id = request.auth.user_id
			# 绑定的优惠卷
			pay_name = settings.PAYMENT_CRA_NAME % (user_id, "*")

			# 全站优惠卷
			# global_c_dict = {}
			global_coupon_name = settings.GLOBAL_COUPON % (user_id)
			#判断是否有全局的优惠卷
			global_c_dict = {}
			if self.conn.exists(global_coupon_name):
				# print(self.conn.hget(global_coupon_name, "coupon"))
				global_coupon = json.loads(self.conn.hget(global_coupon_name, "coupon").decode("utf-8"))
				global_default_coupon = self.conn.hget(global_coupon_name, "default_coupon").decode("utf-8")
				# global_c_dict["global_coupon"] = global_coupon
				# global_c_dict["default_coupon"] = global_default_coupon

				# 添加全站的优惠卷
				global_c_dict = {
					"global_coupon" : global_coupon,
					"global_default_coupon":global_default_coupon
				}

			pay_list = []
			for key in self.conn.scan_iter(pay_name, count=10):
				pay = {}
				for k,v in self.conn.hgetall(key).items():
					k_str = k.decode("utf-8")
					if k_str == "coupon":
						pay[k.decode("utf-8")] = json.loads(v.decode("utf-8"))
					else:
						pay[k.decode("utf-8")] = v.decode("utf-8")
				pay_list.append(pay)
				# c_id = self.conn.hget(key, "course_id").decode("utf-8")
				# title = self.conn.hget(key, "title").decode("utf-8")
				# img = self.conn.hget(key, "img").decode("utf-8")
				# period_display = self.conn.hget(key, "period_display").decode("utf-8")
				# period = self.conn.hget(key, "period").decode("utf-8")
				# price = self.conn.hget(key, "price").decode("utf-8")
				# coupon = json.loads(self.conn.hget(key, "coupon").decode("utf-8"))
				# default_coupon = self.conn.hget(key, "default_coupon").decode("utf-8")
				#
				# pay[c_id] = {
				# 	"title": title,
				# 	"img": img,
				# 	"period_display": period_display,
				# 	"period": period,
				# 	"price": price,
				# 	"coupon": coupon,
				# 	"default_coupon": default_coupon
				# }

				#pay_list.append(pay)

			# print(pay_list)
			# ret.data = pay_list
			ret.data ={
				"course_list" : pay_list,
				"global_coupon_dict":global_c_dict,
			}
		except Exception:
			ret.code = 1002
			ret.error = "查看结算中心失败"
		return Response(ret.dict)

	def post(self, request, *args, **kwargs):
		'''
		提交数据到结算中心
		:param request:
		:param args:
		:param kwargs:
		:return:
		'''
		ret = BaseResponse()
		try:

			c_idlist = request.data.get("courseid")
			user_id = request.auth.user_id
			# 每次把数据添加到结算中心之前，需要把该用户以前的数据清空后 再进行添加；

			# payment_1_1
			for key in self.conn.scan_iter(settings.PAYMENT_CRA_NAME % (user_id, "*")):
				self.conn.delete(key)

			# payment_global_coupon_1
			self.conn.delete(settings.GLOBAL_COUPON%user_id)

			# 1.获取用户要结算的课程;
			# 要验证用户里面是否有这个课程（不加入购物车直接支付 也就可行的）
			# 判断这个课程是否在用户的购物车里面
			pays_dict = {}
			for c_id in c_idlist:
				pay_couser = {}
				s_name = settings.SHOPPING_CRA_NAME % (user_id, c_id)

				# 校验课程是否在购物车里面self.conn.exists() 看redis字典里面 name是否存在
				if not self.conn.exists(s_name):
					ret.code = 1002
					ret.error = "课程需要加入购物车才能进行结算"
					return Response(ret.dict)

				# 从用户购物车中获取信息，放入到结算中心。
				policy = json.loads(self.conn.hget(s_name, "policy").decode("utf-8"))
				price_policyid = self.conn.hget(s_name, "default_policy").decode("utf-8"),
				# print(price_policyid)  变为元组了 ('1',)
				policy_info = policy[price_policyid[0]]
				# 要结算的所有课程
				pay_couser = {
					'course_id': c_id,
					"title": self.conn.hget(s_name, "title").decode("utf-8"),
					"img": self.conn.hget(s_name, "img").decode("utf-8"),
					"price_policyid": self.conn.hget(s_name, "default_policy").decode("utf-8"),
					"coupon": {},
					"default_coupon": 0,
				}
				pay_couser.update(policy_info)
				pays_dict[str(c_id)] = pay_couser
			# print(pays_dict)
			#在这里报错，只是没有优惠卷而已。
			try:

				c_time = datetime.date.today()  # 年月日；    datetime.datetime.now()   #年月日 时分秒
				# 比如 优惠卷有效时间截止到7 ；如果优惠卷是包含7号当天的话，就today()；如果不包含的话就用 now()
				# 获取优惠券:  有比有效时间大，并且比有效结束时间小的优惠卷才能使用；  lte 小于等于
				coupon_obj_list = models.CouponRecord.objects.filter(
					account__id=user_id,
					status=0,
					coupon__valid_begin_date__lte=c_time,
					coupon__valid_end_date__gte=c_time
				)
				# coupon_obj_list 没有找到就会报错
				# print(coupon_obj_list)
				# 放全站优惠卷
				global_coupon_dict = {
					"coupon": {},
					"default_coupon": 0
				}
				for coupon_obj in coupon_obj_list:
					# 筛选出绑定课程的优惠卷
					# 绑定课程的优惠卷 也分3种：通用(立减);满减;折扣; 每一个优惠券取的值不同
					coupon_dic = {}
					# 优惠卷的id
					coupon_id = coupon_obj.id
					# 优惠卷的类型
					c_type = coupon_obj.coupon.coupon_type
					coupon_type = coupon_obj.coupon.get_coupon_type_display()
					# 优惠卷绑定课程的id
					bind_c = coupon_obj.coupon.object_id

					if not bind_c:
						# 不是绑定课程的优惠卷; 即全站优惠卷;同样也分为三种:
						global_coupon = {}
						global_coupon["c_type"] = c_type
						global_coupon["coupon_type"] = coupon_type
						if c_type == 0:
							# 通用(立减)
							global_coupon["money_equivalent_value"] = coupon_obj.coupon.money_equivalent_value
						elif c_type == 1:
							# 满减
							global_coupon["money_equivalent_value"] = coupon_obj.coupon.money_equivalent_value
							global_coupon["minimum_consume"] = coupon_obj.coupon.minimum_consume
						else:
							# 折扣 (不带满减的折扣)
							global_coupon["off_percent"] = coupon_obj.coupon.off_percent

						global_coupon_dict["coupon"][coupon_id] = global_coupon
						global_coupon_dict["coupon"] = json.dumps(global_coupon_dict["coupon"])

					# print(global_coupon_dict,type(global_coupon_dict["coupon"]))
					coupon_dic = {}
					coupon_dic["c_type"] = c_type
					coupon_dic["coupon_type"] = coupon_type
					# 绑定课程的优惠卷
					if c_type == 0:
						# 通用(立减)
						coupon_dic["money_equivalent_value"] = coupon_obj.coupon.money_equivalent_value
					elif c_type == 1:
						# 满减
						coupon_dic["money_equivalent_value"] = coupon_obj.coupon.money_equivalent_value
						coupon_dic["minimum_consume"] = coupon_obj.coupon.minimum_consume
					else:
						# 折扣 (不带满减的折扣)
						coupon_dic["off_percent"] = coupon_obj.coupon.off_percent

					# 把绑定课程的优惠卷放入指定课程内：
					for c_id in pays_dict:
						if c_id != str(bind_c):
							continue
						# 是绑定该课程的优惠卷
						pays_dict[c_id]['coupon'][coupon_id] = coupon_dic
				# print(pays_dict)
				# print(global_coupon_dict)
				for key, v in pays_dict.items():

					# 把字典变为字符串
					v["coupon"] = json.dumps(v["coupon"])
					self.conn.hmset(settings.PAYMENT_CRA_NAME % (user_id, key), v)
				# 放全站优惠卷 只与用户有关。
				self.conn.hmset(settings.GLOBAL_COUPON % user_id, global_coupon_dict)
				ret.data = "添加成功"

			except Exception:
				ret.data = "添加成功"

		except Exception:
			ret.code = 1002
			ret.error = "提交错误"

		return Response(ret.dict)

	def patch(self, request, *args, **kwargs):
		'''
		修改结算中心的优惠券
		:param request:
		:param args:
		:param kwargs:
		:return:
		'''
		ret = BaseResponse()
		try:
			user_id = request.auth.user_id
			courseid = request.data.get("courseid", None)
			couponid = str(request.data.get("coupon"))
			# couponid为0的话，就表示不想用优惠卷。
			if courseid == None:
				# 全站优惠卷;
				global_coupon = settings.GLOBAL_COUPON % (user_id)
				global_coupon_dict = json.loads(self.conn.hget(global_coupon, "coupon").decode("utf-8"))
				# 要修改的是全站的优惠卷
				if couponid not in global_coupon_dict and couponid != "0":
					ret.code = 1002
					ret.error = "全站优惠券不合法"
					return Response(ret.dict)
				# 修改全站优惠卷
				self.conn.hset(global_coupon, "default_coupon", couponid)
				ret.data = "修改全站的优惠券成功"
				return Response(ret.dict)

			# 修改绑定课程的优惠卷
			# 绑定优惠卷
			pay_name = settings.PAYMENT_CRA_NAME % (user_id, courseid)
			coupon_dict = json.loads(self.conn.hget(pay_name, "coupon").decode("utf-8"))

			# 判断传过来的优惠券是存在。（用户有）
			if couponid not in coupon_dict and couponid != "0":
				ret.code = 1003
				ret.error = "绑定优惠券不合法"
				return Response(ret.dict)

			# 修改绑定的优惠券
			self.conn.hset(pay_name, "default_coupon", couponid)
			ret.data = "修改绑定的优惠卷成功"

		except Exception:
			ret.code = 1003
			ret.error = "修改优惠卷失败"

		return Response(ret.dict)