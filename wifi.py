import os
import subprocess
import locale

from mainconfig import NAME_OF_ROUTER
from mainconfig import NET, PDST, PSRC

# scan available Wifi networks

os_encoding = locale.getpreferredencoding()
# os.system('cmd /c "netsh wlan show networks"')

# connect to the given wifi network
# os.system(f'''cmd /c "netsh wlan connect name={NAME_OF_ROUTER}"''')


def detect_network():
    network_list = []
    for ip in range(128):
        if ip not in [0, 1, 255]:
            data = check_arp(ip)
            if data:
                network_list.append(data)
    # network_list = check_net()
    return network_list


def check_arp(ip):
    answers = sr1(ARP(op='who-has', psrc=PSRC, pdst=PDST + str(ip)), timeout=1, verbose=False)
    data = {}
    if answers:
        ans = answers[0]
        date, time = check_hour()
        data = {'mac': ans.hwsrc, 'ip': ans.psrc, 'date': date, 'time': time}
    return data


def check_net():
    network_list = []
    ans, noans = scapy.layers.l2.arping(NET, timeout=2, verbose=False)
    for sent, received in ans.res:
        mac = received.hwsrc
        ip = received.psrc
        date, time = check_hour()
        network_list.append({'mac': mac, 'ip': ip, 'date': date, 'time': time})
    return network_list

def find():
    cmd = 'netsh interface show interface'
    cmd = cmd.split()
    fd_popen = subprocess.Popen(cmd, stdout=subprocess.PIPE).stdout
    data_list = fd_popen.read().decode(os_encoding).strip().split()
    fd_popen.close()

    status_list = []
    interface_list = []
    for data in data_list:
        if '연결' in data or 'connected' in data.lower():
            status_list.append(data.lower())
        if '이더넷' in data or 'ethernet' in data.lower() or 'wi-fi' in data.lower():
            interface_list.append(data.lower())

    connected = False
    for status, interface in zip(status_list, interface_list):
        if interface == 'wi-fi':
            if status == '연결됨' or status == 'connected':
                connected = True

    return connected





find()





