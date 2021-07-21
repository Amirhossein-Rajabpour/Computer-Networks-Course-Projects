import binascii
import socket
import sys
import pandas as pd

# resolved_urls = {url: times that url has resolved, ...}
resloved_urls = {}
# cached_urls = {url: ip, ...}
cached_urls = {}

def send_request(message, address):
    print("sending request to server: ", address)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(binascii.unhexlify(message), (address, 53))
        data, _ = sock.recvfrom(4096)
    finally:
        sock.close()
    return binascii.hexlify(data).decode("utf-8")


def create_message(address):
    message = ""

    ID = 43690  # 16-bit identifier (0-65535) # 43690 equals 'aaaa'
    message += "{:04x}".format(ID)

    QR = "0"         # 1bit Query=0, Response=1 
    OPCODE = "0000"  # 4bit
    AA = "0"         # 1bit
    TC = "0"         # 1bit
    RD = "1"         # 1bit
    RA = "0"         # 1bit
    Z = "000"        # 3bit
    RCODE = "0000"   # 4bit

    query_params = QR + OPCODE + AA + TC + RD + RA + Z + RCODE
    query_params = "{:04x}".format(int(query_params, 2))
    message += query_params

    # when we're sending request, we have only Header and Question
    QDCOUNT = 1 # Number of questions           4bit
    message += "{:04x}".format(QDCOUNT)

    ANCOUNT = 0 # Number of answers             4bit
    message += "{:04x}".format(ANCOUNT)

    NSCOUNT = 0 # Number of authority records   4bit
    message += "{:04x}".format(NSCOUNT)

    ARCOUNT = 0 # Number of additional records  4bit
    message += "{:04x}".format(ARCOUNT)

    addr_parts = address.split(".")
    for part in addr_parts:
        addr_len = "{:02x}".format(len(part))
        message += addr_len

        addr_part = binascii.hexlify(part.encode())
        message += addr_part.decode()

    # Terminating bit for QNAME
    message += "00" 

    # Type of request
    QTYPE = "0001"  # type A
    message += QTYPE

    QCLASS = "0001"  # IN: internet
    message += QCLASS

    return message

def update_url_request(url):
    value = resloved_urls.get(url, "not exist")
    if value == "not exist":
        value = 1
    else:
        value += 1
    resloved_urls[url] = value
    return value

def hex_to_ip(hex_ip):
    ip_decoded = ""
    for i in range(len(hex_ip)):
        if (i % 2) == 0:
            ip_decoded += str(int(hex_ip[i:i+2], 16))
            ip_decoded += "."
            i += 1
    return ip_decoded[:-1]

def parse_parts(message, start, parts):
    part_start = start + 2
    part_len = message[start:part_start]
    
    if len(part_len) == 0:
        return parts
    
    part_end = part_start + (int(part_len, 16) * 2)
    parts.append(message[part_start:part_end])

    if message[part_end:part_end + 2] == "00" or part_end > len(message):
        return parts
    else:
        return parse_parts(message, part_end, parts)


def parse_Question(response):
    QUESTION_SECTION_STARTS = 24
    question_parts = parse_parts(response, QUESTION_SECTION_STARTS, [])
    
    QTYPE_STARTS = QUESTION_SECTION_STARTS + (len("".join(question_parts))) + (len(question_parts) * 2) + 2
    QCLASS_STARTS = QTYPE_STARTS + 4
    QCLASS_ENDS = QCLASS_STARTS + 4

    return QCLASS_ENDS

def parse_AN_NS_AR(count, server_response, start):
    ip = ""
    for c in range(count):
        if (start < len(server_response)):
            TYPE = server_response[start + 4:start + 8]
            LENGTH = int(server_response[start + 20:start + 24], 16)
            # print("type is:", TYPE)

            if TYPE == "0001": # A
                DATA = server_response[start + 24:start + 24 + (LENGTH * 2)]
                ip = hex_to_ip(DATA)
                start = start + 24 + (LENGTH * 2)

            elif TYPE == "0005" or TYPE == "0002": # CNAME or NS
                start = start + 24 + (LENGTH * 2)

    # print(start)
    return ip, start

def find_ip(server_response):

    is_final_ip = False # in order to handle iterative search

    ANCOUNT = server_response[12:16]   # number of answers
    ANCOUNT = int(ANCOUNT, 16)

    NSCOUNT = server_response[16:20]
    NSCOUNT = int(NSCOUNT, 16)

    ARCOUNT = server_response[20:24]
    ARCOUNT = int(ARCOUNT, 16)

    # parse Question section
    QCLASS_ENDS = parse_Question(server_response)

    if ANCOUNT != 0: # we have multiple answers
        # parse Answers section and return IP
        ip, _ = parse_AN_NS_AR(ANCOUNT, server_response, QCLASS_ENDS)
        is_final_ip = True
        return ip, is_final_ip

    else: # there is no Answer section, we should check Authority and Additional sections
        print("Searching in another server ...")
        # parsing Authority and Additional sections
        if NSCOUNT != 0:
            _, end_of_NS = parse_AN_NS_AR(NSCOUNT, server_response, QCLASS_ENDS)
        else:
            end_of_NS = QCLASS_ENDS

        if ARCOUNT != 0:
            ip, _  = parse_AN_NS_AR(ARCOUNT, server_response, end_of_NS)


    return ip, is_final_ip  # ip of another server


def handle_url(url):
    times_requested = update_url_request(url)

    if times_requested <= 3:
        message = create_message(url) 
        print("Request for " + url +" URL :\n" + message + "\n")
        # response = send_request(message, "198.41.0.4")
        response = send_request(message, "1.1.1.1")
        print("Response for " + url +" URL:\n" + response + "\n")
        ip, is_final_ip = find_ip(response)
        print(ip)

        while not is_final_ip:
            response = send_request(message, ip)
            ip, is_final_ip = find_ip(response)
            print("Returned ip is: " + ip +"\n" + response + "\n")

        # update cache
        cached_urls[url] = ip

    else:
        print("Searching in cache for " + url + " ...")
        ip = cached_urls.get(url)

    print("Requested IP is: " + ip + "\n")
    return ip    


def read_from_csv(csv_file_name):
    df = pd.read_csv(csv_file_name)
    IPs = []
    for i in range(0, len(df)):
        ip = handle_url(str(df.iloc[i,0]))
        IPs.append(ip)

    df["IPs"] = IPs
    print(df)
    df.to_csv('urls.csv')


while True:
    option = input("Which option do you prefer? \n 1) Enter a URL \n 2) Import URLs from a csv file\n 3) Exit\n")

    if option == "1":
        url = input("Enter URL:\n")
        handle_url(url)
    elif option == "2":
        csv_file_name = input("Enter csv file name:\n")
        read_from_csv(csv_file_name)
    elif option == "3":
        exit()
    else:
        print("Wrong input!")
