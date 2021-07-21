import random
import threading
import dhcppython
import socket
import ipaddress
import time
import math

mac_address = 'DE:AD:BE:EF:C0:44'
backoff_cutoff = 120   # in seconds
initial_interval = 10   # in seconds
ack_timeout = 10   # in seconds
lease_time = 10   # in seconds
ip = ''


def countdown(t):
    while t:
        time.sleep(1)
        t -= 1


def update_timeout(prev_interval):  # Discover timeout in a thread
    new_interval = math.ceil(2 * prev_interval * random.random())
    if new_interval < backoff_cutoff:
        return new_interval
    else:
        return backoff_cutoff


def handle_discover_timeout(client, time_interval, state):
    countdown(time_interval)
    if ip == '' and state == 'from offer':
        send_discover(client, 'offer')
        print('time interval should be updated')
        time_interval = update_timeout(time_interval)
        print('new time interval: ', time_interval)
        handle_discover_timeout(client, time_interval, 'from offer')
    elif ip == '' and state == 'from ack':
        send_discover(client, 'ack')
        print('Ack is not received')
        handle_discover_timeout(client, time_interval, 'from ack')
    else:
        print('we have a valid ip :)')
        handle_discover_timeout(client, time_interval, 'from ack')


def handle_ack_timeout(client, ack_timeout):
    if ip == '':
        handle_discover_timeout(client, ack_timeout, 'from ack')


def lease_time_timeout(client, leas_time):
    countdown(leas_time)
    print('lease time is finished\n')
    send_discover(client, 'lease_time')


def wait_for_ack(client):   # listen for Ack from Server
    while True:
        data_ack, addr = client.recvfrom(1024)
        packet_ack = dhcppython.packet.DHCPPacket.from_bytes(data_ack)
        dhcp_type = packet_ack.options.as_dict()['dhcp_message_type']
        if packet_ack.op == 'BOOTREPLY' and dhcp_type == 'DHCPACK':
            print("ack message:", packet_ack)
            ip = packet_ack.yiaddr
            print(f'ip: {ip} is assigned to this client\n')
            lease_time_t = threading.Thread(target=lease_time_timeout, args=(client, lease_time,))
            lease_time_t.start()
            break


def send_request(client, transaction_id, from_state, offered_ip):   # Request packet
    request_packet = dhcppython.packet.DHCPPacket(op="BOOTREQUEST", htype="ETHERNET", hlen=6, hops=0, xid=transaction_id, secs=0, flags=0, ciaddr=ipaddress.IPv4Address(0), yiaddr=ipaddress.IPv4Address(offered_ip), siaddr=ipaddress.IPv4Address(0), giaddr=ipaddress.IPv4Address(0), chaddr=mac_address, sname=b'', file=b'', options=dhcppython.options.OptionList([dhcppython.options.options.short_value_to_object(53, "DHCPREQUEST")]))
    client.sendto(request_packet.asbytes, ('<broadcast>', 6666))
    if from_state == 'start':
        wait_for_ack_t = threading.Thread(target=handle_ack_timeout, args=(client, ack_timeout,))
        wait_for_ack_t.start()
        wait_for_ack(client)
    else:
        wait_for_ack(client)


def wait_for_offer(client, transaction_id, from_state):  # listen for Server Offer
    while True:
        data_offer, addr = client.recvfrom(1024)
        packet_offer = dhcppython.packet.DHCPPacket.from_bytes(data_offer)
        dhcp_type = packet_offer.options.as_dict()['dhcp_message_type']
        if packet_offer.op == 'BOOTREPLY' and dhcp_type == 'DHCPOFFER':
            print("offer message:", packet_offer)
            offered_ip = packet_offer.yiaddr
            print(f'server offer is: {offered_ip}\n')
            send_request(client, transaction_id, from_state, offered_ip)
            break


def send_discover(client, from_state):  # Discovery packet
    discover_packet = dhcppython.packet.DHCPPacket.Discover(mac_address)
    client.sendto(discover_packet.asbytes, ('<broadcast>', 6666))
    transaction_id = discover_packet.xid
    if from_state == 'start':
        wait_for_offer_t = threading.Thread(target=handle_discover_timeout, args=(client, initial_interval, 'from offer'))
        wait_for_offer_t.start()
        wait_for_offer(client, transaction_id, from_state)
    else:
        wait_for_offer(client, transaction_id, from_state)


def main():
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) # UDP
    client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)    # Enable port reusage
    client.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)    # Enable broadcasting mode
    client.bind(("", 4444))
    while True:
        send_discover(client, 'start')


if __name__ == '__main__':
    main()