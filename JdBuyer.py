# -*- coding: utf-8 -*-
import argparse
import ast
import json
import os
import sys
import threading
import time
from datetime import datetime, timedelta

import qrcode
from PIL import Image
from pyzbar.pyzbar import decode

from config import global_config
from exception import JDException
from JdSession import Session
from log import logger
from timer import Timer
from utils import open_image, save_image, send_wechat


class Buyer(object):
    """
    京东买手
    """

    # 初始化
    def __init__(self):
        self.session = Session()
        self.config_list = []

        if getattr(sys, "frozen", False):
            self.absPath = os.path.dirname(os.path.abspath(sys.executable))
        elif __file__:
            self.absPath = os.path.dirname(os.path.abspath(__file__))
        # 微信推送
        self.enableWx = global_config.getboolean("messenger", "enable")
        self.scKey = global_config.get("messenger", "sckey")

    ############## 登录相关 #############
    # 二维码登录
    def loginByQrCode(self):
        if self.session.isLogin:
            logger.info("登录成功")
            return

        # download QR code
        qrCode = self.session.getQRcode()
        if not qrCode:
            raise JDException("二维码下载失败")

        fileName = "QRcode.png"
        save_image(qrCode, fileName)
        logger.info("二维码获取成功，请打开京东APP扫描")
        # open_image(fileName)

        barcode_url = ""
        barcodes = decode(Image.open(f"./{fileName}"))
        for barcode in barcodes:
            barcode_url = barcode.data.decode("utf-8")
        logger.info(barcode_url)

        qr = qrcode.QRCode()
        qr.add_data(barcode_url)
        # invert=True白底黑块,有些app不识别黑底白块.
        qr.print_ascii(invert=True)

        # get QR code ticket
        ticket = None
        retryTimes = 85
        for i in range(retryTimes):
            ticket = self.session.getQRcodeTicket()
            if ticket:
                break
            time.sleep(2)
        else:
            raise JDException("二维码过期，请重新获取扫描")

        # validate QR code ticket
        if not self.session.validateQRcodeTicket(ticket):
            raise JDException("二维码信息校验失败")

        logger.info("二维码登录成功")
        self.session.isLogin = True
        self.session.saveCookies()

    ############## 外部方法 #############
    def show_countdown(self, skuId, buyTime="2022-12-17 20:00:00"):
        """显示一个倒计时
        :buyTime 定时执行
        """
        bt = datetime.strptime(buyTime, "%Y-%m-%d %H:%M:%S")
        while True:
            try:
                cur = datetime.today()
                dif = bt - cur
                dif_sec = dif.seconds
                # get min and seconds first
                mm, ss = divmod(dif_sec, 60)
                # Get hours
                hh, mm = divmod(mm, 60)

                str_hh = str(hh) if hh > 10 else f"0{hh}"
                str_mm = str(mm) if mm > 10 else f"0{mm}"
                str_ss = str(ss) if ss > 10 else f"0{ss}"

                logger.info(
                    f"{skuId} count down: {str_hh} Hours {str_mm} Minutes, {str_ss} Seconds"
                )

                # td = timedelta(seconds=dif_sec)
                # logger.info(f"count down hh:mm:ss.ms: {td}")

                if dif_sec < 0:
                    break
                elif dif_sec < 30:
                    time.sleep(1)
                else:
                    time.sleep(60)
            except Exception:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                logger.error(exc_type, fname, exc_tb.tb_lineno)
                continue

    def init_countdonw_thread(self, skuId, buyTime="2022-12-17 20:00:00"):
        """初始化一个倒计时线程
        :buyTime 定时执行
        """
        th = threading.Thread(
            target=self.show_countdown,
            name=f"Thread-countdown-{skuId}",
            args=[skuId, buyTime],
        )
        th.start()

    def _loadConfigList(self):
        with open(os.path.join(self.absPath, "config_list.json"), "rb") as f:
            self.config_list = json.load(f)
            logger.info(self.config_list)

    def init_buy_thread(
        self,
    ):
        """初始化购买线程池，一个的sku一个购买线程
        :config_list
        """
        # buyer.buyItemInStock(
        #     skuId, areaId, skuNum, stockInterval, submitRetry, submitInterval, buyTime
        # )
        self._loadConfigList()
        buy_cnt = 0
        for config in self.config_list:
            skuId = config.get("skuId")
            areaId = config.get("areaId")
            skuNum = config.get("skuNum")
            stockInterval = (
                config.get("stockInterval") if "stockInterval" in config else 3
            )
            submitRetry = config.get("submitRetry") if "submitRetry" in config else 3
            submitInterval = config.get("submitRetry") if "submitRetry" in config else 5
            buyTime = config.get("buyTime")
            logger.info(config)
            # continue
            th = threading.Thread(
                target=self.buyItemInStock,
                name=f"Thread-buy-{buy_cnt}",
                args=[
                    skuId,
                    areaId,
                    skuNum,
                    stockInterval,
                    submitRetry,
                    submitInterval,
                    buyTime,
                ],
            )
            buy_cnt += 1
            th.start()

    def buyItemInStock(
        self,
        skuId,
        areaId,
        skuNum=1,
        stockInterval=3,
        submitRetry=3,
        submitInterval=5,
        buyTime="2022-12-17 20:00:00",
    ):
        """根据库存自动下单商品
        :skuId 商品sku
        :areaId 下单区域id
        :skuNum 购买数量
        :stockInterval 库存查询间隔（单位秒）
        :submitRetry 下单尝试次数
        :submitInterval 下单尝试间隔（单位秒）
        :buyTime 定时执行
        """
        self.session.fetchItemDetail(skuId)
        self.init_countdonw_thread(skuId, buyTime)
        timer = Timer(buyTime)
        timer.start()

        while True:
            try:
                if not self.session.getItemStock(skuId, skuNum, areaId):
                    logger.info("不满足下单条件，{0}s后进行下一次查询".format(stockInterval))
                else:
                    logger.info("{0} 满足下单条件，开始执行".format(skuId))
                    if self.session.trySubmitOrder(
                        skuId, skuNum, areaId, submitRetry, submitInterval
                    ):
                        logger.info("下单成功")
                        if self.enableWx:
                            send_wechat(
                                message="JdBuyerApp",
                                desp="您的商品已下单成功，请及时支付订单",
                                sckey=self.scKey,
                            )
                        return
            except Exception as e:
                logger.error(e)
            time.sleep(stockInterval)


if __name__ == "__main__":

    # 商品sku
    skuId = "100004408701"
    # 区域id(可根据工程 area_id 目录查找)
    areaId = "19_1607_4773"
    # 购买数量
    skuNum = 1
    # 库存查询间隔(秒)
    stockInterval = 3
    # 监听库存后尝试下单次数
    submitRetry = 3
    # 下单尝试间隔(秒)
    submitInterval = 5
    # 程序开始执行时间(晚于当前时间立即执行，适用于定时抢购类)
    buyTime = "2022-12-17 20:00:00"

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--flag",
        help='True or False flag, input should be either "True" or "False".',
        type=ast.literal_eval,
        dest="flag",
    )
    parser.add_argument("-skuId", "--skuId", help="商品sku", default=skuId)
    parser.add_argument(
        "-areaId", "--areaId", help="区域id(可根据工程 area_id 目录查找)", default=areaId
    )

    parser.add_argument("-skuNum", "--skuNum", help="购买数量", default=skuNum)
    parser.add_argument(
        "-stockInterval", "--stockInterval", help="库存查询间隔(秒)", default=stockInterval
    )
    parser.add_argument(
        "-submitRetry", "--submitRetry", help="监听库存后尝试下单次数", default=submitRetry
    )
    parser.add_argument(
        "-submitInterval", "--submitInterval", help="下单尝试间隔(秒)", default=submitInterval
    )

    parser.add_argument(
        "-buyTime", "--buyTime", help="程序开始执行时间(晚于当前时间立即执行，适用于定时抢购类)", default=buyTime
    )
    args = parser.parse_args()

    buyer = Buyer()  # 初始化
    buyer.loginByQrCode()
    buyer.init_buy_thread()
    if args.flag is True:
        buyer.buyItemInStock(
            args.skuId,
            args.areaId,
            args.skuNum,
            args.stockInterval,
            args.submitRetry,
            args.submitInterval,
            args.buyTime,
        )
