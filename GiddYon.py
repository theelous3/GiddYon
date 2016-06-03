import os
import socket
from threading import Thread
import time
from email.utils import formatdate

import magic

class Connector(Thread):
    def __init__(self, host, port):
        super().__init__()
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind((host, port))
        self.s.listen(5)
        self.clients = {}
    
    def run(self):
        while True:
            cnect, addr = self.s.accept()
            client = Clientor(cnect, addr)
            client.start()


class Clientor(Thread):
    def __init__(self, cnect, addr):
        super().__init__()
        self.cnect = cnect
        self.addr = addr
        self.data = ''


    def run(self):
        while True:
            try:
                self.data += str(self.cnect.recv(1024), 'utf-8')
            except KeyboardInterrupt:
                self.cnect.close()
                self.cnect = None
            else:
                recvd = self.data.split('\r\n')
                if recvd[0].startswith('GET'):
                    get_handler = GetManager(recvd, self.cnect)
                    get_handler.run()
                self.cnect.close()
                break
        self.cnect = None

    def send(self, *data):
        data = ''.join(data) + '\r\n'
        self.cnect.send(bytes(data, 'utf-8'))


class GetManager(Clientor):
    def __init__(self, data, cnect):
        self.data = data
        self.cnect = cnect
        self.response = ()
 
    def run(self):
        uri = self.data[0].split()[1]
        self.fetch_requested(uri)
        return(self.response)

    def fetch_requested(self, uri):
        file_path = os.path.join(*uri.split('/'))
        try:
            file_size = os.path.getsize(file_path)
        except OSError as e:
            self.error_404()
        else:
            with open(file_path, 'r') as got_file:
                with open(os.path.join('responses','get_response_200.txt'), 'r') as respond_file:
                    response = ''.join(respond_file.readlines())
                    response = response.format('200 OK',
                                                formatdate(),
                                                self.get_type(file_path),
                                                str(file_size),
                                                ''.join(got_file.readlines()))
                    self.send(response)

    def get_type(self, file_path):
        return magic.from_file(file_path, mime=True).decode(encoding='utf-8')

    def error_404(self):
        with open(os.path.join('responses','get_response_404.txt'), 'r') as respond_file:
                response = ''.join(respond_file.readlines())
                response = response.format('404 Not Found',
                                            formatdate(),
                                            'I\'m afraid we\'ve 404\'d.')
                self.send(response)


def main(host, port):
    cnect_host = Connector(host, port)
    cnect_host.start()

HOST = ''
PORT = 50007

if __name__ == '__main__':
    main(HOST, PORT)