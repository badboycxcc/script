# conding:UFT-8
# by cx
# ETH 价格实时监控脚本 gui

import tkinter as tk
import requests
import time
from lxml import etree

global i

url = "https://coinmarketcap.com/currencies/ethereum/"
url_zh = "https://coinmarketcap.com/zh/currencies/ethereum/"
xpath_id = '//*[@id="__next"]/div/div[2]/div/div[1]/div[3]/div[2]/div[1]/div/text()'

def refreshText():
    global i
    r = requests.get(url)
    r1 = requests.get(url_zh)
    r.encoding = r.apparent_encoding
    r1.encoding = r1.apparent_encoding
    dom = etree.HTML(r.text)
    dom1 = etree.HTML(r1.text)
    id = dom.xpath(xpath_id)
    id1 = dom1.xpath(xpath_id)

    i = id[0]
    i1 = id1[0]
    i = i[1:] + "美元"
    i1 = i1[2:] + "人民币"
    text3.delete(0.0,tk.END)
    text4.delete(0.0,tk.END)
    text3.insert(tk.INSERT,i)
    text4.insert(tk.INSERT,i1)
    text3.update()
    text4.update()
    windows.after(1000,refreshText)
    time.sleep(10) # 10秒一次更新


while True:
    windows = tk.Tk()
    windows.geometry('250x150') #设置界面大小
    windows.resizable(False, False)  ## 规定窗口不可缩放
    text1 = tk.Label(windows, text="ETH实时监控程序")
    text1.pack()
    text2 = tk.Label(windows, text="当前ETH价格")
    text2.pack()
    text3 = tk.Text(windows,width=15,height=1)
    text3.pack()
    text4 = tk.Text(windows,width=15,height=1)
    text4.pack()
    windows.after(1000,refreshText)
    windows.mainloop()