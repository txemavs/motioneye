
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

'''Remove old pictures and movies.

A background process runs :func:`motioneye.mediafiles.cleanup_media`
'''

import datetime
import logging
import multiprocessing
import os
import signal

from tornado.ioloop import IOLoop

import mediafiles
import settings


_process = None


def start():
    '''Start cleaning every :data:`motioneye.settings.CLEANUP_INTERVAL`
    '''
    if not settings.CLEANUP_INTERVAL:
        return

    # schedule the first call a bit later to improve performance at startup
    io_loop = IOLoop.instance()
    io_loop.add_timeout(datetime.timedelta(seconds=min(settings.CLEANUP_INTERVAL, 60)), _run_process)


def stop():
    '''Stop cleaning.
    '''
    global _process
    
    if not running():
        _process = None
        return
    
    if _process.is_alive():
        _process.join(timeout=10)
    
    if _process.is_alive():
        logging.error('cleanup process did not finish in time, killing it...')
        os.kill(_process.pid, signal.SIGKILL)
    
    _process = None


def running():
    '''Is the process running?

    :return: Process is alive.
    :rtype: ``bool``

    '''

    return _process is not None and _process.is_alive()


def _run_process():
    '''Launch :func:`_do_cleanup` as a new ``multiprocessing.Process`` 
    '''
    global _process
    
    io_loop = IOLoop.instance()
    
    # schedule the next call
    io_loop.add_timeout(datetime.timedelta(seconds=settings.CLEANUP_INTERVAL), _run_process)

    if not running():  # check that the previous process has finished
        logging.debug('running cleanup process...')

        _process = multiprocessing.Process(target=_do_cleanup)
        _process.start()


def _do_cleanup():
    '''Do the picture and movie cleaning.
    This will be executed in a separate subprocess.
    Ignores the terminate and interrupt signals.
    '''
    
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    
    try:
        mediafiles.cleanup_media('picture')
        mediafiles.cleanup_media('movie')
        logging.debug('cleanup done')
         
    except Exception as e:
        logging.error('failed to cleanup media files: %(msg)s' % {
                'msg': unicode(e)}, exc_info=True)
