from socket import *
import os, sys, ssl
import mysql.connector

PACKET_SIZE = 64
context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
context.load_verify_locations('cert.pem')

def show_history(history_file):
    with open(history_file, 'r') as f:
        history = f.read()
        history = history.replace(",", "\n").replace("[", "").replace("]", "").replace("\n ", "\n")
        print(history)

def show_history_from_db(cursor):
    history_record = "SELECT * FROM history"
    cursor.execute(history_record)
    for (record) in cursor:
        print(record[1])

def find_open_ports(host, start, end):
    free_ports = []
    for port in range(start, end):
        with socket() as tmp_sock:
            tmp_sock.settimeout(1)
            try:
                tmp_sock.connect((host, port))
                free_ports.append(port)
            except:
                pass    
    return free_ports

def  connect_to_db():
    conn = mysql.connector.connect(user='root', password='', host='localhost', database='telnet')
    cursor = conn.cursor()
    return cursor, conn

def add_to_db(data, cursor, conn):
    command = (data ,)
    add_record = "INSERT INTO history(command) VALUES(%s)"
    cursor.execute(add_record, command)
    conn.commit()

def send_encrypted(data):
    hostname='localhost'
    ip = '127.0.0.1'
    port = 8443
    with create_connection((ip, port)) as client:
        print('data encrypt: ', type(data))
        with context.wrap_socket(client, server_hostname=hostname) as ssock:
            ssock.sendall(data.encode())
            print(f'Using {ssock.version()}\n')
            sys.stdout.flush()


class Client():
    def __init__(self, server_host, server_port):
        self.server_host = server_host
        self.server_port = server_port
        self.command_history = []

        self.socket = socket(AF_INET, SOCK_STREAM)
        try:
            self.socket.connect((gethostbyname(self.server_host),self.server_port))
            print('connected to ', gethostbyname(self.server_host))
        except:
            print(f'not able to connect to {self.server_host}:{self.server_port}\n')
            exit()

    def send_message(self, data): 
        # data += '\n'         
        self.socket.sendall(data.encode())
        sys.stdout.flush()

    def send_file(self, file_directory):
        try:
            file_size = os.stat(file_directory).st_size
            print('file size: ', file_size)
            self.socket.sendall(str(file_size).encode())
            with open(file_directory, 'rb') as f:
                file = f.read()
                self.socket.sendall(file)
                sys.stdout.flush()

        except Exception as e:
            print('error: ', e)
            pass

    def receive_data(self):
        data = b''
        while True:
            part = self.socket.recv(PACKET_SIZE)
            data += part
            if len(part) < PACKET_SIZE: # either 0 or end of data
                break
        return data.decode()

    def close_connection(self):
        if self.socket:
            self.socket.close()



if __name__ == '__main__':

    if len(sys.argv) == 1:
        HOST = 'localhost'
        PORT = 1080
    elif len(sys.argv) == 2 and sys.argv[1] == 'find-open-ports':    # find open ports
        HOST = input('Host: ')
        min_port = input('minimum port range: ')
        max_port = input('maximum port range: ')
        open_ports = find_open_ports(HOST, int(min_port), int(max_port))
        print(f'open ports for host: {HOST} are: {open_ports} \n')
        exit()
    else:
        HOST = sys.argv[1]
        PORT = int(sys.argv[2])

    print(f'host is {HOST}, port is {PORT}')
    myclient = Client(HOST, PORT)

    cursor, conn = connect_to_db()

    while True:
        data = input(">> ")
        myclient.command_history.append(data)
        # add to file
        with open('commands history.txt', 'w') as f:
            f.write(str(myclient.command_history))

        # add to mysql database
        add_to_db(data, cursor, conn)

        if len(data.split(' '))>1 and data.split(' ')[1] == 'upload':
            myclient.send_message(data)
            myclient.send_file(data.split(' ')[2])

        elif len(data.split(' '))>1 and data.split(' ')[1] == 'send' and data.split(' ')[2] == '-e':
            myclient.send_message(str(data.split(' ')[:3]).replace(",", "").replace("[", "").replace("]", "").replace("'", ""))
            send_encrypted(str(data.split(' ')[3:]).replace(",", "").replace("[", "").replace("]", "").replace("'", ""))

        elif len(data.split(' '))>1 and data.split(' ')[1] == 'history':
            # show_history('commands history.txt')
            show_history_from_db(cursor)
            myclient.send_message(data)
            
        else:    
            myclient.send_message(data)


        received_data = myclient.receive_data()
        print('received from server: ', received_data)
        if received_data == 'closing the connection...':
            myclient.close_connection()
            break