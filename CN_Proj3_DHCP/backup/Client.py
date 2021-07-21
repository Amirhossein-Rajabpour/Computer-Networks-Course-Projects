import random
import dhcppython
import socket
import ipaddress
mac_address = 'de:ad:be:ef:c0:de'

# TODO Discover timeout in a thread (calculated by a formula: Prev_interval * 2 * Random(0,1))
backoff_cutoff = 120    # in seconds
initial_interval = 10   # in seconds
def calculate_timeout(prev_interval):
    new_interval = 2 * prev_interval * random.random()
    if new_interval < backoff_cutoff:
        return backoff_cutoff
    else:
        return new_interval


client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) # UDP
client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)    # Enable port reusage
client.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)    # Enable broadcasting mode
client.bind(("", 4444))

while True:

    # Discovery packet
    discover_packet = dhcppython.packet.DHCPPacket.Discover(mac_address)
    client.sendto(discover_packet.asbytes, ('<broadcast>', 6666))
    transaction_id = discover_packet.xid

    # listen for Server Offer
    while True:
        data_offer, addr = client.recvfrom(1024)
        packet_offer = dhcppython.packet.DHCPPacket.from_bytes(data_offer)
        print("received message:", packet_offer)
        dhcp_type = packet_offer.options.as_dict()['dhcp_message_type']
        if packet_offer.op == 'BOOTREPLY' and dhcp_type == 'DHCPOFFER':
            print(f'server offer is: {packet_offer.yiaddr}')
            break

    # print('offer received')

    # Request packet
    request_packet = dhcppython.packet.DHCPPacket.Request(mac_address, seconds=0, tx_id=transaction_id)
    print('request: ', request_packet)
    client.sendto(request_packet.asbytes, ('<broadcast>', 6666))

    # print('request sent')

    # listen for Ack from Server
    while True:
        data_ack, addr = client.recvfrom(1024)
        packet_ack = dhcppython.packet.DHCPPacket.from_bytes(data_ack)
        print("received message:", packet_ack)
        dhcp_type = packet_ack.options.as_dict()['dhcp_message_type']
        if packet_ack.op == 'BOOTREPLY' and dhcp_type == 'DHCPACK':
            print(f'ip: {packet_ack.yiaddr} is assigned to this client')
            break

    # print('ack received')


    # TODO implement timeout (arbitrary timeout)
    exit()