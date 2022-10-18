import json
import socket
from _thread import *
from threading import Thread
from multiprocessing import Queue
sockets = dict()
queue = Queue()

# 쓰레드에서 실행되는 코드입니다.
# 접속한 클라이언트마다 새로운 쓰레드가 생성되어 통신을 하게 됩니다.


def threaded(client_socket, addr):
    print(f'ip 연결 : {addr[0]}:{addr[1]}')
    # 클라이언트가 접속을 끊을 때 까지 반복합니다.
    while True:
        try:
            # 데이터가 수신되면 클라이언트에 다시 전송합니다.(에코)
            data = client_socket.recv(1024)
            if not data:
                print(f'ip 연결해제: {addr[0]}:{addr[1]}')
                break
            res = data.decode()
            print(res)
            queue.put((res, client_socket))
        except ConnectionResetError as e:
            print(f'ip 연결해제: {addr[0]}:{addr[1]}')
            break
    client_socket.close()


HOST = '0.0.0.0'
PORT = 5000

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.listen()

print('server start')

# 클라이언트가 접속하면 accept 함수에서 새로운 소켓을 리턴합니다.
# 새로운 쓰레드에서 해당 소켓을 사용하여 통신을 하게 됩니다.


def select_send(id_, text):
    if sockets.get(id_):
        sockets[id_].send(json.dumps(text).encode())
    else:
        print(f"id: {id_}는 열려있지 않습니다.")


def loop():
    while True:
        print('wait')
        client_socket, addr = server_socket.accept()
        start_new_thread(threaded, (client_socket, addr))


if __name__ == "__main__":
    Thread(target=loop).start()
    while True:
        try:
            if queue.empty():
                continue
            
            js, sock = queue.get()
            data = json.loads(js)
            identify = data['identify']
            info = data['data']
            
            if identify == "web":
                select_send(1234, {'data': info})
                
            elif identify == "region":
                if info == "new":
                    id_ = data['id']
                    sockets[id_] = sock
                    print(f"{id_} 연결됨")
                    select_send(id_, {'status':'ok'})
                else:
                    print(f"id: {id_}, data: {info}")
            else:
                sock.send("nothing to handle".encode())
        except KeyboardInterrupt:
            break
        except:
            pass
server_socket.close()
