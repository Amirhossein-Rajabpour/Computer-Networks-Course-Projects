from socket import *
import subprocess, threading, sys, ssl

PACKET_SIZE = 64 
command_history = []
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain('cert.pem', 'key.pem')
# PEM Phrase = 1 2 3 4

def recv_encrypted():
    ip = '127.0.0.1'
    port = 8443
    with socket(AF_INET, SOCK_STREAM) as server:
        server.bind((ip, port))
        server.listen(1)
        with context.wrap_socket(server, server_side=True) as tls:
            connection, address = tls.accept()
            data = connection.recv(PACKET_SIZE)
            return data


def main():
    server_socket = socket(AF_INET, SOCK_STREAM)
    server_socket.bind(('', 1080))
    server_socket.listen(10)

    while True:
        conn, addr = server_socket.accept()
        threading.Thread(target=handle_client, args=(conn,server_socket)).start()

def handle_client(conn, server_socket):

    print('client connected!')
    while True:    

        data = conn.recv(PACKET_SIZE)
        data = data.decode()
        sys.stdout.flush()
        print(f'from client: {data}')
        splitted_data = data.split(' ', 2)

        command_history.append(data)

        if splitted_data[1] == 'exec':
            command = splitted_data[2]
            print('command is:', command)
            response = subprocess.check_output(command, shell=True)
            print('response is:', response)
            conn.sendall(response)

        elif splitted_data[1] == 'send' and splitted_data[2] != '-e':
            message = splitted_data[2]
            print('message is:', message)
            response = "message received"
            print('response is:', response)
            conn.sendall(response.encode())

        elif splitted_data[1] == 'send' and splitted_data[2] == '-e':
            print('encrypted mode')
            enc_data = recv_encrypted()
            print('encrypted data is: ', enc_data.decode())
            response = "encrypted message received"
            print('response is:', response)
            conn.sendall(response.encode())

        elif splitted_data[1] == 'upload':
            print('uploading...')
            file_size = conn.recv(PACKET_SIZE)
            file_size = int(file_size.decode())
            print('file size: ', file_size)
            file = conn.recv(file_size)
            file_in_server = "server files\\" + splitted_data[2].split('\\')[-1]
            print('file in server dir: ', file_in_server)
            with open(file_in_server, "wb") as f:
                f.write(file)

            response = "file received"
            print('response is:', response)
            conn.sendall(response.encode())

        elif splitted_data[1] == 'history':
            print('client history...')
            conn.sendall("show history".encode())

        elif splitted_data[1] == 'exit':
            response = 'closing the connection...'
            conn.sendall(response.encode())
            conn.close()
            break

        else:
            conn.sendall('wrong command!'.encode())
            pass

if __name__ == '__main__':
    main()