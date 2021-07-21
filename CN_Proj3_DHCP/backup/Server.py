import ipaddress
import json
import dhcppython
import socket
import threading
import random
mac_address = 'de:ad:be:ef:c0:de'
assigned_IPs = {}   # it's not the same as reservation_list!

def pool_maker(from_ip, to_ip):
    from_ip_splitted = from_ip.split('.')
    to_ip_splitted = to_ip.split('.')
    ip_pool = []

    if from_ip_splitted[0] != to_ip_splitted[0]:
        pass
    elif from_ip_splitted[1] != to_ip_splitted[1]:
        pass
    elif from_ip_splitted[2] != to_ip_splitted[2]:
        pass
    else:
        start = int(from_ip_splitted[3])
        end = int(to_ip_splitted[3])

        mutual_part = from_ip_splitted[0] + '.' + from_ip_splitted[1] + '.' + from_ip_splitted[2] + '.'
        for end_part in range(start, end+1):
            ip_pool.append(mutual_part + str(end_part))
    return ip_pool


json_file = 'configs.json'
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

    lease_time = config['lease_time']
    reservation_list = config['reservation_list']
    black_list = config['black_list']
    f.close()
    return ip_pool, lease_time, reservation_list, black_list


def offer_ip(ip_pool, mac_address, reservation_list):
    if mac_address in reservation_list.keys():
        return reservation_list[mac_address]
    else:
        while True:
            ip_to_assign = random.choice(ip_pool)
            if ip_to_assign not in reservation_list.values() and ip_to_assign not in assigned_IPs.values():
                return ip_to_assign


def show_clients():
    pass

def main():
    ip_pool, lease_time, reservation_list, black_list = load_server_config(json_file)
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    server.bind(("", 6666))

    # while True:
    threading.Thread(target=handle_client, args=(server,ip_pool, lease_time, reservation_list, black_list)).start()

def handle_client(server,ip_pool, lease_time, reservation_list, black_list):



    # listen for Discovery packet (it should be multi-thread)
    while True:
        data_discovery, addr = server.recvfrom(1024)
        packet_discovery = dhcppython.packet.DHCPPacket.from_bytes(data_discovery)
        print("received message:", packet_discovery)
        dhcp_type = packet_discovery.options.as_dict()['dhcp_message_type']
        if packet_discovery.op == 'BOOTREQUEST' and dhcp_type == 'DHCPDISCOVER':
            print('Discover packet received')
            transaction_id = packet_discovery.xid
            break


    # Offer packet
    offered_ip = offer_ip(ip_pool, mac_address, reservation_list)
    offer_packet = dhcppython.packet.DHCPPacket.Offer(mac_address, seconds=0, tx_id=transaction_id, yiaddr=ipaddress.IPv4Address(offered_ip))
    server.sendto(offer_packet.asbytes, ('<broadcast>', 4444))

    # print('offer sent')

    # listen for Client request packet (parse request)
    while True:
        data_request, addr = server.recvfrom(1024)
        packet_request = dhcppython.packet.DHCPPacket.from_bytes(data_request)
        print("request message:", packet_request)
        dhcp_type = packet_request.options.as_dict()['dhcp_message_type']
        if packet_request.op == 'BOOTREQUEST' and dhcp_type == 'DHCPREQUEST':
            print('Request packet received')
            break

    # print('request received')

    # Ack packet
    assigned_IPs[packet_request.chaddr] = offered_ip
    print('ip:', offered_ip)
    ack_packet = dhcppython.packet.DHCPPacket.Ack(mac_address, seconds=0, tx_id=transaction_id, yiaddr=ipaddress.IPv4Address(offered_ip))
    server.sendto(ack_packet.asbytes, ('<broadcast>', 4444))

    # print('ack sent')

    # TODO handle lease-time (perhaps in a different thread for each client)

if __name__ == '__main__':
    main()
