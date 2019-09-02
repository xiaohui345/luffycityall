# -*- coding: utf-8 -*-
# @Author: 曾辉
from rest_framework.response import Response
from django.shortcuts import redirect, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from utils.pay import AliPay
from django.conf import settings
from app01 import models
from app01.utils.response_ret import BaseResponse

def aliPay():
	obj = AliPay(
		appid=settings.APPID,       #支付宝appID
		app_notify_url=settings.NOTIFY_URL,  # 如果支付成功，支付宝会向这个地址发送POST请求（校验是否支付已经完成）
		return_url=settings.RETURN_URL,  # 如果支付成功，重定向回到你的网站的地址。
		alipay_public_key_path=settings.PUB_KEY_PATH,  # 支付宝公钥
		app_private_key_path=settings.PRI_KEY_PATH,  # 应用私钥
		debug=True,  # 默认False,
	)
	return obj


def index(request,title,money,out_trade_no):
	alipay = aliPay()
	# 对购买的数据进行加密
	query_params = alipay.direct_pay(
		subject=title,  # 商品简单描述
		out_trade_no=out_trade_no,  # 商户订单号
		total_amount=money,  # 交易金额(单位: 元 保留俩位小数)
	)

	pay_url = "https://openapi.alipaydev.com/gateway.do?{}".format(query_params)
	return pay_url

def pay_result(request):
	"""
	支付完成后，跳转回的地址
	:param request:
	:return:
	"""
	params = request.GET.dict()
	sign = params.pop('sign', None)

	alipay = aliPay()

	status = alipay.verify(params, sign)

	if status:
		# 原则上是在下面的接口进行修改订单的操作，但是没有服务器，就无法让支付宝发送POST请求，等到公司后就可以了
		# 因此现在在这里进行修改订单的操作，方便测试.
		# order_num = params.get("out_trade_no")  # 订单号
		# 支付成功后修改订单的状态
		# models.Order.objects.update_or_create(order_num=order_num, defaults={"status": 1})
		# order_obj = models.Order.objects.filter(order_num=order_num).first()
		# order_obj.status = 1

		# 可以跳转到购买的页面。
		return HttpResponse('支付成功')
	return HttpResponse('支付失败')



# 支付宝会给我们发送请求，在一天之内，不断的给我们发，直到我们回复了sucess。
# 这个接口需要挂载到服务器上，让支付宝找到这个端口，这样才能发post请求
@csrf_exempt
def update_order(request):
	"""
	支付成功后，支付宝向该地址发送的POST请求（用于修改订单状态）
	:param request:
	:return:
	"""
	# 发送过来的一定是POST请求
	if request.method == 'POST':
		from urllib.parse import parse_qs

		ret = BaseResponse()
		body_str = request.body.decode('utf-8')
		post_data = parse_qs(body_str)

		post_dict = {}
		for k, v in post_data.items():
			post_dict[k] = v[0]

		alipay = aliPay()

		sign = post_dict.pop('sign', None)
		status = alipay.verify(post_dict, sign)
		if status:
			# 修改订单状态
			out_trade_no = post_dict.get('out_trade_no')
			# 2. 根据订单号将数据库中的数据进行更新
			models.Order.objects.filter(order_number=out_trade_no).update(status=0)
			ret.data = '支付成功'

			return Response(ret.dict)

		else:
			ret.code = 1100
			ret.data = '支付失败'
			return Response(ret.dict)
	return HttpResponse('')

