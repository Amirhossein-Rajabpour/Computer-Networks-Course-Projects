import ipaddress
import json
import dhcppython
import socket
import threading
import random
import time

mac_address = 'DE:AD:BE:EF:C0:88'
assigned_IPs = {}   # it's not the same as reservation_list!
lease_mac = {}  # record lease time for each client
json_file = 'configs.json'


def pool_maker(from_ip, to_ip):
    ip_pool = []
    from_ip_splitted = from_ip.split('.')
    to_ip_splitted = to_ip.split('.')
    start = int(from_ip_splitted[3])
    end = int(to_ip_splitted[3])
    mutual_part = from_ip_splitted[0] + '.' + from_ip_splitted[1] + '.' + from_ip_splitted[2] + '.'

    for end_part in range(start, end+1):
        ip_pool.append(mutual_part + str(end_part))
    return ip_pool


def pool_maker_subnet(ip_block, subnet_mask):
    power = 8 - bin(int(subnet_mask.split('.')[-1])).count('1')
    if ip_block.split('.')[-1] == '0':
        from_ip = ip_block[:-1] + '1'
        print(from_ip)
    else:
        from_ip = ip_block
    to_ip = ip_block[:-1] + str((2 ** power) - 1)
    print('to ip is:', to_ip)
    return pool_maker(from_ip, to_ip)


def load_server_config(json_file):
    f = open(json_file)
    config = json.load(f)
    ip_pool = []
    pool_mode = config['pool_mode']
    if pool_mode == 'range':
        from_ip = config['range']['from']
        to_ip = config['range']['to']
        ip_pool = pool_maker(from_ip, to_ip)
    elif pool_mode == 'subnet':
        ip_block = config['subnet']['ip_block']
        subnet_mask = config['subnet']['subnet_mask']
        ip_pool = pool_maker_subnet(ip_block, subnet_mask)

    lease_time = config['lease_time']
    reservation_list = config['reservation_list']
    black_list = config['black_list']
    f.close()
    return ip_pool, lease_time, reservation_list, black_list


def offer_ip(ip_pool, mac_address, reservation_list, black_list):
    if mac_address in reservation_list.keys():
        print(f'IP {reservation_list[mac_address]} is reserved for mac address {mac_address}\n')
        return reservation_list[mac_address]
    elif mac_address in black_list:
        return 'BLOCK'
    elif mac_address in assigned_IPs.keys():
        return assigned_IPs[mac_address]
    else:
        while True:
            ip_to_assign = random.choice(ip_pool)
            if ip_to_assign not in reservation_list.values() and ip_to_assign not in assigned_IPs.values():
                return ip_to_assign


def show_clients(assigned_IPs, lease_mac):
    for mac in assigned_IPs.keys():
        print(f'mac:{mac}, time to expire:{lease_mac[mac]}, IP:{assigned_IPs[mac]}\n')


def countdown(t, lease_time):
    while t:
        time.sleep(1)
        lease_time -= 1
        t -= 1


def lease_time_timeout(server, ip_pool, reservation_list, black_list, lease_time, mac_addr):
    countdown(lease_time, lease_mac[mac_addr])
    assigned_IPs.pop(mac_addr)
    lease_mac[mac_addr] = 0
    print(f'lease time for client {mac_addr} is finished')
    show_clients(assigned_IPs, lease_mac)
    manage_client(server, ip_pool, reservation_list, black_list, lease_time)


def manage_client(server, ip_pool, reservation_list, black_list, lease_time):
    # listen for Discovery packet
    while True:
        data_discovery, addr = server.recvfrom(1024)
        packet_discovery = dhcppython.packet.DHCPPacket.from_bytes(data_discovery)
        print("discover message:", packet_discovery)
        dhcp_type = packet_discovery.options.as_dict()['dhcp_message_type']
        if packet_discovery.op == 'BOOTREQUEST' and dhcp_type == 'DHCPDISCOVER':
            client_mac_address = packet_discovery.chaddr
            print('Discover packet received\n')
            transaction_id = packet_discovery.xid
            break


    # Offer packet
    offered_ip = offer_ip(ip_pool, client_mac_address, reservation_list, black_list)
    if offered_ip == 'BLOCK':
        print('This client is blocked!\n')
    else:
        offer_packet = dhcppython.packet.DHCPPacket.Offer(mac_address, seconds=0, tx_id=transaction_id, yiaddr=ipaddress.IPv4Address(offered_ip))
        server.sendto(offer_packet.asbytes, ('<broadcast>', 4444))

    # time.sleep(20)
    # print('offer sent')

    # listen for Client request packet
    while True:
        data_request, addr = server.recvfrom(1024)
        packet_request = dhcppython.packet.DHCPPacket.from_bytes(data_request)
        dhcp_type = packet_request.options.as_dict()['dhcp_message_type']
        if packet_request.op == 'BOOTREQUEST' and dhcp_type == 'DHCPREQUEST':
            print("request message:", packet_request)
            print('Request packet received\n')
            break

    # time.sleep(15)

    # Ack packet
    client_mac_address = packet_request.chaddr
    assigned_IPs[client_mac_address] = offered_ip
    print(f'ip {offered_ip} is assigned to client')
    ack_packet = dhcppython.packet.DHCPPacket.Ack(mac_address, seconds=0, tx_id=transaction_id, yiaddr=ipaddress.IPv4Address(offered_ip))
    server.sendto(ack_packet.asbytes, ('<broadcast>', 4444))
    lease_mac[client_mac_address] = lease_time

    # print('ack sent')
    show_clients(assigned_IPs, lease_mac)
    # lease_time_t = threading.Thread(target=lease_time_timeout, args=(server, ip_pool, reservation_list, black_list, lease_time, client_mac_address))
    # lease_time_t.start()
    return client_mac_address


def main():
    ip_pool, lease_time, reservation_list, black_list = load_server_config(json_file)
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    server.bind(("", 6666))

    # while True:
    threading.Thread(target=handle_client, args=(server,ip_pool, lease_time, reservation_list, black_list)).start()

def handle_client(server,ip_pool, lease_time, reservation_list, black_list):

    client_mac_address = manage_client(server, ip_pool, reservation_list, black_list, lease_time)

    # timer for handling client lease time
    # lease_time_t = threading.Thread(target=lease_time_timeout, args=(server, ip_pool, reservation_list, black_list, lease_time, client_mac_address))
    # lease_time_t.start()


if __name__ == '__main__':
    main()
