
# Copyright (c) 2013 Calin Crisan
# This file is part of motionEye.
#
# motionEye is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>. 

'''MJPEG camera client.
'''

import datetime
import errno
import logging
import re
import socket
import time

from tornado.ioloop import IOLoop
from tornado.iostream import IOStream

import config
import motionctl
import settings
import utils


class MjpgClient(IOStream):
    '''MJPG stream client.
    
    :param camera_id: `Camera ID`
    :type camera_id: ``int``
    :param port: Port number
    :type port: ``int``
    :param username: User name
    :type username: ``string``
    :param password: Password
    :type password: ``string``
    :param auth_mode: Auth mode 'basic' or 'digest'
    :type auth_mode: ``strinc``
    '''
    _FPS_LEN = 4
    
    #: dictionary of clients indexed by camera id
    clients = {}  
    
    #: helps detecting erroneous connections and restart motion
    _last_erroneous_close_time = 0  

    def __init__(self, camera_id, port, username, password, auth_mode):
        self._camera_id = camera_id
        self._port = port
        self._username = (username or '').encode('utf8')
        self._password = (password or '').encode('utf8')
        self._auth_mode = auth_mode
        self._auth_digest_state = {}
        
        self._last_access = 0
        self._last_jpg = None
        self._last_jpg_times = []
        
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        IOStream.__init__(self, s)
        
        self.set_close_callback(self.on_close)
        
    def do_connect(self):
        '''Connect IOStream.'''
        IOStream.connect(self, ('localhost', self._port), self._on_connect)

    def get_port(self):
        '''Get port number.

        :return: Port number
        :rtype: ``int``
        '''
        return self._port
    
    def on_close(self):
        '''IOStream close event handler.
        '''
        logging.debug('connection closed for mjpg client for camera %(camera_id)s on port %(port)s' % {
                'port': self._port, 'camera_id': self._camera_id})
        
        if MjpgClient.clients.pop(self._camera_id, None):
            logging.debug('mjpg client for camera %(camera_id)s on port %(port)s removed' % {
                    'port': self._port, 'camera_id': self._camera_id})

        if getattr(self, 'error', None) and self.error.errno != errno.ECONNREFUSED:
            now = time.time()
            if now - MjpgClient._last_erroneous_close_time < settings.MJPG_CLIENT_TIMEOUT:
                msg = 'connection problem detected for mjpg client for camera %(camera_id)s on port %(port)s' % {
                        'port': self._port, 'camera_id': self._camera_id}

                logging.error(msg)
                
                if settings.MOTION_RESTART_ON_ERRORS:
                    motionctl.stop(invalidate=True)  # this will close all the mjpg clients
                    motionctl.start(deferred=True)

            MjpgClient._last_erroneous_close_time = now
    
    def get_last_jpg(self):
        '''Access to last image.
        
        Sets :data:`_last_access` to current :func:`time.time`

        '''
        self._last_access = time.time()
        return self._last_jpg

    def get_last_access(self):
        '''Get last access time.

        :return: :data:`_last_access` value
        :rtype: ``time``
        '''
        return self._last_access

    def get_last_jpg_time(self):
        '''Get last JPG access time.

        :return: :data:`_last_jpg_times` value
        :rtype: ``time``
        '''
        if not self._last_jpg_times:
            self._last_jpg_times.append(time.time())

        return self._last_jpg_times[-1]

    def get_fps(self):
        '''Get FPS.

        :return: Frames per second
        :rtype: ``int``
        '''
        if len(self._last_jpg_times) < self._FPS_LEN:
            return 0  # not enough "samples"
        
        if time.time() - self._last_jpg_times[-1] > 1:
            return 0  # everything below 1 fps is considered 0
        
        return (len(self._last_jpg_times) - 1) / (self._last_jpg_times[-1] - self._last_jpg_times[0])

    def _check_error(self):
        '''Check socket is there and :data:`tornado.iostream.IOStream.error` is None.'''
        if self.socket is None:
            logging.warning('mjpg client connection for camera %(camera_id)s on port %(port)s is closed' % {
                    'port': self._port, 'camera_id': self._camera_id})
            
            self.close()
            
            return True
            
        error = getattr(self, 'error', None)
        if (error is None) or (getattr(error, 'errno', None) == 0):  # error could also be ESUCCESS for some reason
            return False
        
        self._error(error)
        
        return True
     
    def _error(self, error):
        '''Log error and close.

        :param error: Error message
        :type error: ``string``
        '''
        logging.error('mjpg client for camera %(camera_id)s on port %(port)s error: %(msg)s' % {
                'port': self._port, 'camera_id': self._camera_id, 'msg': unicode(error)})
        
        try:
            self.close()
        
        except:
            pass
    
    def _on_connect(self):
        '''On stream connection handler.'''
        logging.debug('mjpg client for camera %(camera_id)s connected on port %(port)s' % {
                'port': self._port, 'camera_id': self._camera_id})

        if self._auth_mode == 'basic':
            logging.debug('mjpg client using basic authentication')

            auth_header = utils.build_basic_header(self._username, self._password)
            self.write('GET / HTTP/1.0\r\n\r\nAuthorization: %s\r\n\r\n' % auth_header)
            
        else:  # in digest auth mode, the header is built upon receiving 401
            self.write('GET / HTTP/1.0\r\n\r\n')

        self._seek_http()

    def _seek_http(self):
        '''Check if error and read until HTTP/1.

        Calls :func:`tornado.iostream.IOStream.read_until_regex`
        '''
        if self._check_error():
            return
        
        self.read_until_regex('HTTP/1.\d \d+ ', self._on_http)

    def _on_http(self, data):
        '''Check if authentication is needed (HTTP 401).

        Starts :func:`_seek_www_authenticate` or skips directly to :func:`_seek_content_length`
        '''
        if data.endswith('401 '):
            self._seek_www_authenticate()

        else:  # no authorization required, skip to content length
            self._seek_content_length()

    def _seek_www_authenticate(self):
        '''Seek 'WWW-Authenticate:' and call :func:`_on_before_www_authenticate`'''
        if self._check_error():
            return
        
        self.read_until('WWW-Authenticate:', self._on_before_www_authenticate)

    def _on_before_www_authenticate(self, data):
        '''Seek '\r\n' and call :func:`_on_www_authenticate`
        
        :param data: Data
        :type data: ``string``
        '''
        if self._check_error():
            return
        
        self.read_until('\r\n', self._on_www_authenticate)
    
    def _on_www_authenticate(self, data):
        '''Send basic/digest authentication and calls func:`_seek_content_length`
        
        :param data: Data
        :type data: ``string``
        '''
        if self._check_error():
            return
        
        m = re.match('Basic\s*realm="([a-zA-Z0-9\-\s]+)"', data.strip())
        if m:
            logging.debug('mjpg client using basic authentication')
            
            auth_header = utils.build_basic_header(self._username, self._password)
            self.write('GET / HTTP/1.0\r\n\r\nAuthorization: %s\r\n\r\n' % auth_header)
            self._seek_http()

            return

        m = re.match('Digest\s*realm="([a-zA-Z0-9\-\s]+)",\s*nonce="([a-zA-Z0-9]+)"', data.strip())
        if m:
            logging.debug('mjpg client using digest authentication')

            realm, nonce = m.groups()
            self._auth_digest_state['realm'] = realm
            self._auth_digest_state['nonce'] = nonce
    
            auth_header = utils.build_digest_header('GET', '/', self._username, self._password, self._auth_digest_state)
            self.write('GET / HTTP/1.0\r\n\r\nAuthorization: %s\r\n\r\n' % auth_header)
            self._seek_http()
            
            return

        logging.error('mjpg client unknown authentication header: "%s"' % data)
        self._seek_content_length()

    def _seek_content_length(self):
        ''' Seek 'Content-Length:' and call :func:`_on_before_content_length`'''
        if self._check_error():
            return
        
        self.read_until('Content-Length:', self._on_before_content_length)
    
    def _on_before_content_length(self, data):
        ''' Seek ''\r\n\r\n' and call :func:`_on_content_length`'''
        if self._check_error():
            return
        
        self.read_until('\r\n\r\n', self._on_content_length)
    
    def _on_content_length(self, data):
        '''Read all bytes.

        Calls :func:`tornado.iostream.IOStream.read_until_regex`
        '''
        if self._check_error():
            return
        
        matches = re.findall('(\d+)', data)
        if not matches:
            self._error('could not find content length in mjpg header line "%(header)s"' % {
                    'header': data})
            
            return
        
        length = int(matches[0])
        
        self.read_bytes(length, self._on_jpg)
    
    def _on_jpg(self, data):
        '''Set last jpg image and :func:`_seek_content_length` again

        :param data: Image
        :type data: ``bytes``
        '''
        self._last_jpg = data
        self._last_jpg_times.append(time.time())
        while len(self._last_jpg_times) > self._FPS_LEN:
            self._last_jpg_times.pop(0)

        self._seek_content_length()


def start():
    '''Schedule the first call to :func:`_garbage_collector`.'''
    io_loop = IOLoop.instance()
    io_loop.add_timeout(datetime.timedelta(seconds=settings.MJPG_CLIENT_TIMEOUT), _garbage_collector)


def get_jpg(camera_id):
    '''Call :func:`MjpgClient.get_last_jpg` on client.

    Creates a new  :class:`MjpgClient` instance if ID not in :data:`MjpgClient.clients` keys.
    
    :param camera_id: `Camera ID`
    :type camera_id: ``int``
    '''
    if camera_id not in MjpgClient.clients:
        # mjpg client not started yet for this camera
        
        logging.debug('creating mjpg client for camera %(camera_id)s' % {
                'camera_id': camera_id})
        
        camera_config = config.get_camera(camera_id)
        if not camera_config['@enabled'] or not utils.is_local_motion_camera(camera_config):
            logging.error('could not start mjpg client for camera id %(camera_id)s: not enabled or not local' % {
                    'camera_id': camera_id})
            
            return None
        
        port = camera_config['stream_port']
        username, password = None, None
        auth_mode = None
        if camera_config.get('stream_auth_method') > 0:
            username, password = camera_config.get('stream_authentication', ':').split(':')
            auth_mode = 'digest' if camera_config.get('stream_auth_method') > 1 else 'basic'

        client = MjpgClient(camera_id, port, username, password, auth_mode)
        client.do_connect()
        
        MjpgClient.clients[camera_id] = client

    client = MjpgClient.clients[camera_id]

    return client.get_last_jpg()


def get_fps(camera_id):
    '''Call :func:`MjpgClient.get_fps` on client.'''
    client = MjpgClient.clients.get(camera_id)
    if client is None:
        return 0
    
    return client.get_fps()
    

def close_all(invalidate=False):
    '''Close all :class:`MjpgClient` clients.

    :param invalidate: Reset :data:`MjpgClient.clients` dictionary.
    :type invalidate: ``bool``
    '''
    for client in MjpgClient.clients.values():
        client.close()
    
    if invalidate:
        MjpgClient.clients = {}
        MjpgClient._last_erroneous_close_time = 0


def _garbage_collector():
    '''Garbage collector check for frame and last access timeouts.

    Called periodically every :data:`.settings.MJPG_CLIENT_TIMEOUT` seconds.
    
    Restarts motion if :data:`.settings.MOTION_RESTART_ON_ERRORS`.
    This will close all the mjpg clients.

    '''
    io_loop = IOLoop.instance()
    io_loop.add_timeout(datetime.timedelta(seconds=settings.MJPG_CLIENT_TIMEOUT), _garbage_collector)

    now = time.time()
    for camera_id, client in MjpgClient.clients.items():
        port = client.get_port()

        if client.closed():
            continue

        # check for jpeg frame timeout
        last_jpg_time = client.get_last_jpg_time()
        delta = now - last_jpg_time
        if delta > settings.MJPG_CLIENT_TIMEOUT:
            logging.error('mjpg client timed out receiving data for camera %(camera_id)s on port %(port)s' % {
                    'camera_id': camera_id, 'port': port})
            
            if settings.MOTION_RESTART_ON_ERRORS:
                motionctl.stop(invalidate=True)  
                motionctl.start(deferred=True)
            
            break

        # check for last access timeout
        delta = now - client.get_last_access()
        if settings.MJPG_CLIENT_IDLE_TIMEOUT and delta > settings.MJPG_CLIENT_IDLE_TIMEOUT:
            msg = ('mjpg client for camera %(camera_id)s on port %(port)s has been idle '
                   'for %(timeout)s seconds, removing it' % {
                    'camera_id': camera_id, 'port': port, 'timeout': settings.MJPG_CLIENT_IDLE_TIMEOUT})

            logging.debug(msg)

            client.close()

            continue
