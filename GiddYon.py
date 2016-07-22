import os
import socket
import time
import datetime
from threading import Thread
from email.utils import formatdate
from collections import OrderedDict

import magic


def main(host, port):
#   creates socket, listens, and starts threading off clients as they connect
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen(5)
    while True:
        connection, addr = s.accept()
        client = Client()
        client.run(connection, addr)


class Client(Thread):
#   threaded client to handle interactions

    def run(self, connection, addr):
    #   builds buffer of requests and begins parsing their types
        super().__init__()
        self.connection = connection
        self.addr = addr
        self.buffer = b''
        self.req_type = None
        self.headders = None
        self.in_body = None
        eof = b'\r\n'

        while eof not in self.buffer:
            try:
                self.buffer += self.connection.recv(4096)
            except KeyboardInterrupt:
                self.connection.close()
                self.connection = None
                raise SystemExit
        self.buffer = str(self.buffer, 'utf-8')
        recvd = self.buffer.split('\r\n')

    #   builds profile of request
        self.req_type = recvd[0]
        self.headders = {hedr: hedr_guts for hedr, hedr_guts in
                    [x.split(':', 1) for x in recvd[1:recvd.index('')]]}
        self.in_body = ''.join(recvd[(recvd.index('')+1):])

        self.check_req_method()
        self.headders = None
        self.connection.close()
        self.connection = None

    def check_req_method(self):
    #   checks request method type
        if self.req_type.startswith('GET'):
            if 'Expect' in self.headders:
                self.resp_400()
            else:
                self.get_handler()
        elif self.req_type.startswith('HEAD'):
            if 'Expect' in self.headders:
                self.resp_400()
            else:
                self.head_handler()
        elif self.req_type.startswith('POST', 'PUT',
                                    'DELETE', 'CONNECT',
                                    'OPTIONS', 'TRACE'):
            self.resp_501()
        else:
            self.resp_400() 

    def get_handler(self):
    #   handles GET requests and client side caching
        file_path = self.uri_constructor()
        file_size = self.get_size(file_path)
        if file_size:
            if 'If-Modified-Since' in self.headders:
                if self.check_if_mod():
                    self.resp_200(file_path, file_size)
                else:
                    self.resp_304()
            elif 'If-Unmodified-Since' in self.headders:
                if self.check_if_unmod():
                    self.resp_200(file_path, file_size)
                else:
                    self.resp_412()
            else:
                self.resp_200(file_path, file_size)
        else:
            self.resp_404()

    def head_handler(self):
    #   handles HEAD requests
        file_path = self.uri_constructor()
        file_size = self.get_size(file_path)
        if file_size:
            self.resp_200(file_path, file_size, True)
        else:
            self.resp_404()

    def send(self, *data, file_path=None):
    #   packages headder(s) and/or body for sending, and sends
        data = ''.join(data) + '\r\n'
        self.connection.send(bytes(data, 'utf-8'))
        if file_path:
            with open(file_path, 'rb') as got_file:
                self.connection.send(bytes('\r\n', 'utf-8'))
                while True:
                    bytechunk = got_file.read(4096)
                    if bytechunk:
                        self.connection.send(bytechunk)
                    else:
                        break

    def uri_constructor(self):
    #   builds urls from the given uri and returns target path as string
        uri = self.req_type.split()[1]
        if uri.lower().startswith('http'):
            uri = uri.split('/', 3)[3]
        file_path = os.path.join(*uri.split('/'))
        return file_path

    def get_size(self, file_path):
    #   gets the target's size in bytes and returns as string
    #   exception indicates 404 should be sent
        try:
            file_size = os.path.getsize(file_path)
        except OSError as e:
            return False
        else:
            return file_size

    def get_type(self, file_path):
    #   uses python-magic to get mime file type(s)
        return magic.from_file(file_path, mime=True).decode(encoding='utf-8')

    def get_mtime(self, file_path):
    #   gets the target's last modified time and returns string + datetime obj
        t_stamp = os.path.getmtime(file_path)
        t_stamp = datetime.datetime.fromtimestamp(t_stamp)
        return t_stamp.strftime('%a, %d %b %Y %X GMT'), t_stamp

    def check_if_mod(self):
    #   runs comparison for If-Modified-Since headder and returns indicator
        try:
            req_time = time.strptime(self.headders['If-Modified-Since'],
                                                '%a, %d %b %Y %X GMT')
        except:
            self.resp_400()
        else:
            req_time = datetime.datetime(*req_time[:6])
            mod_time = self.get_mtime(file_path)[1]
            if req_time - mod_time < 0:
                return True
            else:
                return False

    def check_if_unmod(self):
    #   runs comparison for If-Unmodified-Since headder and returns indicator
        try:
            req_time = time.strptime(self.headders['If-Unmodified-Since'],
                                                    '%a, %d %b %Y %X GMT')
        except:
            self.resp_400()
        else:
            req_time = datetime.datetime(*req_time[:6])
            mod_time = self.get_mtime(file_path)[1]
            if req_time - mod_time < 0:
                return False
            else:
                return True

    def gmt_formatdate(self):
    #   formats date correctly for outbound Date headders
        return formatdate().replace('-0000', 'GMT')

    def resp_100(self):
    #   handles http 100 Continue response
        self.send(['HTTP/1.1 100 Continue'])

    def resp_200(self, file_path, file_size, h_directive=False):
    #   handles http 200 OK response for GET and HEAD
        http_200 = OrderedDict([('HTTP/1.1', '200 OK'),
                                ('Date:', self.gmt_formatdate()),
                                ('Server:', 'GiddYon/0.1.1'),
                                ('Cache-Control:', 'Private, max-age=0'),
                                ('Expires:', self.gmt_formatdate()),
                                ('Content-Type:', self.get_type(file_path)),
                                ('Content-Length:', str(file_size))])

        response = [key + ' ' + value for key, value in http_200.items()]
        if not h_directive:
            self.send(*response, file_path=file_path)
        else:
            self.send(*response)

    def resp_304(self):
    #   handles http 304 Not Modified response
        http_304 = OrderedDict([('HTTP/1.1', '304 Not Modified'),
                                ('Date:', self.gmt_formatdate())])
        response = [key + ' ' + value + '\n' for key, value in http_304.items()]
        self.send(*response)

    def resp_400(self):
    #   handles http 400 Bad Request response
        http_400 = OrderedDict([('HTTP/1.1', '400 Bad Request'),
                                ('Date:', self.gmt_formatdate()),
                                ('Server:', 'GiddYon/0.1.1')])
        response = [key + ' ' + value + '\n' for key, value in http_400.items()]
        self.send(*response)

    def resp_404(self):
    #   handles ye olde http 404 Not Found response
        http_404 = OrderedDict([('HTTP/1.1', '404 Not Found'),
                                ('Date:', self.gmt_formatdate()),
                                ('Server:', 'GiddYon/0.1.1')])
        response = [key + ' ' + value + '\n' for key, value in http_404.items()]
        self.send(*response)

    def resp_412(self):
    #   handles http 412 Precognitive Alert Team
        self.send(['HTTP/1.1 412 Precondition Failed'])

    def resp_501(self):
    #   handles http 501 Not Implemented response for unsupported headder(s)
        self.send(['HTTP/1.1 501 Not Implemented'])

HOST = ''
PORT = None

if __name__ == '__main__':
    main(HOST, PORT)


#   refactor http_* (use decorator)
#   mimetypes

