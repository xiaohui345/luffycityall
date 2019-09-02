# -*- coding: utf-8 -*-
# @Author: 曾辉
import json
import datetime

from django_redis import get_redis_connection
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import F
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ViewSetMixin

from app01.utils.response_ret import BaseResponse
from app01 import models
from app01.utils.exceptions import PricePolicyInvalid,ShopNumberInvalid
from app01.utils.userAuth import MyuserAuth

# ----------简单版本的购物车
# redis存储形式
''''
{       name    ：    k -->  v
	luffy_shopping_car_6_11
	shopping_dic_1(用户ID)_2(课程ID) : { 'title': '金融量化分析入门', 'img': '/xx/xx/xx.png',
							            'policy': {
							                10: {'name': '有效期1个月', 'price': 599},
											11: {'name': '有效期3个月', 'price': 1599},
											13: {'name': '有效期6个月', 'price': 2599},
										},
										'default_policy': 12
}

'''


class ShoppingView(APIView):
	'''
	购物车
	'''
	authentication_classes = [MyuserAuth]
	# 获取redis连接
	conn = get_redis_connection('default')

	def get(self, request, *args, **kwargs):
		'''
		获得当前用户的购物车里面的所有信息
		:param request:
		:param args:
		:param kwargs:
		:return:
		'''
		ret = BaseResponse()
		user_id = request.auth.user.id
		try:
			redis_name = settings.SHOPPING_CRA_NAME % (user_id, "*")
			data = []
			for item in self.conn.scan_iter(redis_name, count=10):
				couser = {}

				_, c_id = item.decode("utf-8").rsplit('_', 1)
				title = self.conn.hget(item, "title")
				img = self.conn.hget(item, "img")
				policy = self.conn.hget(item, "policy")
				default_policy = self.conn.hget(item, "default_policy")

				couser[c_id] = {
					"title": title.decode("utf-8"),
					"img": img.decode("utf-8"),
					"policy": json.loads(policy.decode("utf-8")),
					"default_policy": default_policy.decode("utf-8"),  # bytes ---> json字符串---->dict
				}
				# redis缓存里面有数据
				# 取到当前用户的购物车里面的所有商品
				data.append(couser)

			ret.data = data
		# 缓存里面没有就证明为没有添加到购物车里面.
		# 在redis传输全部用字节
		except Exception:
			ret.code = 1002
			ret.error = "查看购物车错误"

		return Response(ret.dict)

	def post(self, request, *args, **kwargs):
		'''
		往当前用户的购物车里面添加内容
		:param request:
		:param args:
		:param kwargs:
		:return:
		'''
		ret = BaseResponse()
		try:
			# 从 前端 传过来的数据：数据类型
			course_id = int(request.data.get("courseid"))
			price_policy_id = int(request.data.get("policyid"))

			# 从认证组件中获取user_id
			user_id = request.auth.user.id
			# print(user_id)
			# 为了防止串改价格，必须要在后台进行验证 此课程是否有这个价格。
			# 反向查询
			course_obj = models.Course.objects.get(id=course_id)
			# 验证课程是否存在；不存在，报错后，会被外面的ObjectDoesNotExist错误 捕捉到。

			# 拿到这个课程的所有价格对象
			price_list = course_obj.price_policy.all()
			policy = {}
			for price_obj in price_list:
				policy[price_obj.id] = {"period_display": price_obj.get_valid_period_display(),
				                        "price": price_obj.price, "period": price_obj.valid_period}

			# 如果此课程没有这个价格。policy 里面的key就是价格策略的id
			if price_policy_id not in policy:
				# 一种是报错
				raise PricePolicyInvalid("价格不合法")
			# 另外一种是直接返回

			# ret.code = 1002
			# ret.error = "价格不存在"
			# return Response(ret.dict)

			# 此课程有这个价格。

			# 创建课程字典放入redis中
			shoppingcar_course = {
				'title': course_obj.name,
				'img': '/xx/xx/xx.png',
				'policy': json.dumps(policy),
				'default_policy': price_policy_id
			}

			# luffy_shopping_car_6_11
			redis_name = settings.SHOPPING_CRA_NAME % (user_id, course_id)

			# 对购物车里面的商品做限制(最多存放100个商品)
			num=0
			for n in self.conn.scan_iter(settings.SHOPPING_CRA_NAME % (user_id, '*')):
				if num < 100:
					num +=1
				else:
					raise ShopNumberInvalid("购物车数量已满")


			# 按照字典的类型存储;在name对应的hash中批量设置键值对
			self.conn.hmset(redis_name, shoppingcar_course)
			ret.data = "添加课程成功"

		except ShopNumberInvalid as e:
			ret.code = 1005
			ret.error = e.msg

		except PricePolicyInvalid as e:
			ret.code = 1004
			ret.error = e.msg

		except ObjectDoesNotExist:
			ret.code = 1003
			ret.error = "课程不存在"

		except Exception:
			ret.code = 1002
			ret.error = "添加课程错误"

		return Response(ret.dict)

	def delete(self, request, *args, **kwargs):
		'''
		删除购物车里面的记录
		:param request:
		:param args:
		:param kwargs:
		:return:
		'''
		ret = BaseResponse()
		try:
			courseid_list = request.data.get("courseid")
			user_id = request.auth.user.id
			# 获得要删除的name ;如果redis里面没有，不会报错。
			name_list = [settings.SHOPPING_CRA_NAME % (user_id, course_id) for course_id in courseid_list]
			# 获取redis连接,并且删除name
			self.conn.delete(*name_list)

		except Exception:
			ret.code = 1002,
			ret.error = "删除错误"

		return Response(ret.dict)

	def patch(self, request, *args, **kwargs):
		'''
		更新价格策略
		:param request:
		:param args:
		:param kwargs:
		:return:
		'''
		ret = BaseResponse()
		course_id = request.data.get("courseid")
		user_id = request.auth.user_id
		policy_id = request.data.get("policyid")
		try:
			# 修改的话，课程肯定是存在的，只不过修改的价格可能是非法的。

			# 先判断要修改的价格是否合法；也就是从redis里面该课程对应的取 'policy': {...}
			redis_name = settings.SHOPPING_CRA_NAME % (user_id, course_id)
			prince_list = self.conn.hget(redis_name, 'policy')
			prince_dict = json.loads(prince_list.decode('utf-8'))

			if policy_id not in prince_dict:
				ret.code = 1004
				ret.error = "价格不合法"
				return Response(ret.dict)

			# 价格合法的话，就修改default_policy价格
			self.conn.hset(redis_name, 'default_policy', policy_id)

		except Exception:
			ret.code = 1002
			ret.error = "更新失败"

		return Response(ret.dict)


# ----------复杂版本的购物车
# redis存储形式
# { shopping_dic :{
# 	1(用户id): {
# 		课程ID: {
# 			'title': '金融量化分析入门',
# 			'img': '/xx/xx/xx.png',
# 			'policy': {
# 				10: {'name': '有效期1个月', 'price': 599},
# 				11: {'name': '有效期3个月', 'price': 1599},
# 				13: {'name': '有效期6个月', 'price': 2599},
# 			},
# 			'default_policy': 12
# 		},
#
# 	},
# 	2: {
# 		"课程1": {
# 			'title': '金融量化分析入门',
# 			'img': '/xx/xx/xx.png',
# 			'policy': {
# 				10: {'name': '有效期1个月', 'price': 599},
# 				11: {'name': '有效期3个月', 'price': 1599},
# 				13: {'name': '有效期6个月', 'price': 2599},
# 			},
# 			'default_policy': 12
# 		},
# }

# class ShoppingView(ModelViewSet):
# 	'''
# 	购物车
# 	'''
# 	def list(self, request, *args, **kwargs):
# 		'''
# 		获得当前用户的购物车里面的所有信息
# 		:param request:
# 		:param args:
# 		:param kwargs:
# 		:return:
# 		'''
# 		ret = BaseResponse()
# 		# tokens = request.data.get("token")
# 		account = models.Tokeninfo.objects.filter(tokens="1f59d7b3-40d2-4ed1-a844-696d1ba1a062").first().user
# 		# 后端进行校验
# 		if not account:
# 			ret.code = 1003
# 			ret.error = "用户名或者密码错误"
# 		else:
# 			# 用户登录的id
# 			user_id = 5
# 			ret.code = 1000
# 			try:
# 				conn = get_redis_connection('default')
# 				# 购物车里面的记录应该不是很多。
# 				# conn.set("shopping_car", json.dumps(shopping_dic))
# 				k = conn.keys()
# 				# print(k)
# 				val = conn.get('shop_car')
# 				print(type(json.loads(val)))
# 				# redis缓存里面有数据
# 				#取到当前用户的购物车里面的所有商品
# 				val = json.dumps(json.loads(val).get(str(user_id)))
# 				ret.data = val
# 				#缓存里面没有就证明为没有添加到购物车里面.
# 				#在redis传输全部用字节
# 			except Exception :
# 				ret.code = 1002
# 				ret.error = "错误"
# 		return Response(ret.dict)
#
#
#
# 	def create(self, request, *args, **kwargs):
# 		'''
# 		往当前用户的购物车里面添加内容
# 		:param request:
# 		:param args:
# 		:param kwargs:
# 		:return:
# 		'''
# 		ret = BaseResponse()
# 		#从 前端 传过来的数据：
# 		price_policy_id = 5
# 		course_id = 1
# 		user_id = 5
# 		# 为了防止串改价格，必须要在后台进行验证 此课程是否有这个价格。
# 		#反向查询
# 		course_obj = models.Course.objects.get(id=course_id)
# 		#拿到这个课程的所有价格对象
# 		price_list = course_obj.price_policy.all()
# 		policy={}
# 		for price_obj in price_list:
# 			policy[price_obj.id] = {"name":price_obj.get_valid_period_display(),"price":price_obj.price}
# 		# 如果此课程没有这个价格。
# 		if price_policy_id not in [ item.id for item in price_list]:
# 			ret.code=1002
# 			ret.error = "价格不存在"
#
# 		# 此课程有这个价格。
#
# 		# 创建课程字典放入redis中
# 		shoppingcar_course = {
# 						'title': "python",
# 						'img': '/xx/xx/xx.png',
# 						'policy':policy,
# 						'default_policy': price_policy_id
# 							}
# 		# 获取redis连接
# 		conn = get_redis_connection('default')
# 		valexist = conn.get('shop_car')
# 		shopping_user = {}
# 		if not valexist:
# 			#redis里面什么都没有
# 			shopping_user[user_id] = {course_id:shoppingcar_course}
# 			# 有这个key就不执行，没有就设置值
# 			conn.setnx('shop_car',json.dumps(shopping_user))
# 		# redis里面已经有'shopping_car'这个k了
# 		else:
# 			val = json.loads(valexist)
# 			data = val.get(str(user_id))
# 			if not data:
# 				#此用户的购物车没有东西
# 				val[user_id] = {course_id:shoppingcar_course}
# 			else:
# 				data["2"] = shoppingcar_course
# 				# 重新添加数据
# 			conn.set("shop_car",json.dumps(val))
#
# 		return Response(ret.dict)
#
# 	def destroy(self, request, *args, **kwargs):
# 		'''
# 		删除购物车里面的记录
# 		:param request:
# 		:param args:
# 		:param kwargs:
# 		:return:
# 		'''
# 		ret = BaseResponse()
# 		courselist_id = [1]
# 		user_id = 1
# 		try:
# 			# 获取redis连接
# 			conn = get_redis_connection('default')
# 			val = json.loads(conn.get('shop_car'))
# 			user_data = val.get(str(user_id))
# 			for c_id in courselist_id:
# 				user_data.pop(str(c_id),None)
# 			#更新
# 			conn.set('shop_car', json.dumps(val))
# 		except Exception:
# 			ret.code=1002,
# 			ret.error="删除错误"
#
# 		return Response(ret.dict)
#
# 	def update(self, request, *args, **kwargs):
# 		'''
# 		更新价格策略
# 		:param request:
# 		:param args:
# 		:param kwargs:
# 		:return:
# 		'''
# 		ret = BaseResponse()
# 		courseid = 1
# 		user_id = 5
# 		policy_id=2
# 		try:
# 			# 获取redis连接
# 			conn = get_redis_connection('default')
# 			val = json.loads(conn.get('shop_car'))
# 			user_data = val.get(str(user_id))
# 			course = user_data.get(str(courseid))
# 			course['default_policy'] = policy_id
#
# 			# 更新
# 			conn.set('shop_car',json.dumps(val))
#
# 			#返回的是更新后的课程数据
# 			ret.data = json.dumps(user_data)
#
# 		except Exception:
# 			ret.code =1002
# 			ret.error ="更新失败"
#
# 		return Response(ret.dict)



