import socket
import threading
import socketserver
import melee_env.env_v2
import pickle
import argparse
import hashlib
from sheeprl.utils.timer import timer
from torchmetrics import MaxMetric, MeanMetric
import time
import struct


def send_msg(sock, msg):
    # Prefix each message with a 4-byte length (network byte order)
    print('1')
    msg = struct.pack('>I', len(msg)) + msg
    print('2')
    sock.sendall(msg)

def recv_msg(sock):
    # Read message length and unpack it into an integer
    raw_msglen = recvall(sock, 4)
    if not raw_msglen:
        return None
    msglen = struct.unpack('>I', raw_msglen)[0]
    # Read the message data
    return recvall(sock, msglen)

def recvall(sock, n):
    # Helper function to recv n bytes or return None if EOF is hit
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data

class clientclass():
    def __init__(self, ip, port) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((ip, port))

    def client(self, message):        
        send_msg(self.sock, message)
    
    
        #sock.sendall(message)

        response = recv_msg(self.sock)
        
        if response:
            unpickled = pickle.loads(response)
        else:
            unpickled = [0,0,0,0]
    
        print("Received: {}".format(unpickled))
        return unpickled
        
def client(ip, port, message):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((ip, port))
        
        send_msg(sock, message)
    
    
        #sock.sendall(message)

        response = recv_msg(sock)
        
        if response:
            unpickled = pickle.loads(response)
        else:
            unpickled = [0,0,0,0]
    
        print("Received: {}".format(unpickled))
        return unpickled