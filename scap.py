import scapy.layers.l2
from scapy.all import *
import time
import threading


timestamp1 = time.time()
t = []

def check_arp(ip):
    answers = sr1(ARP(op='who-has', psrc='192.168.2.5', pdst='192.168.2.' + str(ip)), timeout=1, verbose=True)
    print(answers)
    if answers:
        ans = answers[0]
        print('mac', ans.hwsrc, ans.psrc)
    print(ip)


while True:
    t = []
    for i in range(255):
        if i not in [0, 1, 52, 255]:
            check_arp(i)
            # t.append(threading.Thread(target=check_arp, args=(i, )))
            # t[-1].daemon = True
            # t[-1].start()
    timestamp2 = time.time()
    timestamp1 = timestamp2
    time.sleep(10)
