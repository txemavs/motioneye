
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

'''Platform updates.'''

import datetime
import logging
import re
import subprocess

from tornado import ioloop


def get_os_version():
    '''Get OS version.

    Tries :func:`platformupdate.get_os_version` or :func:`_get_os_version_lsb_release`

    :returns: (name, version)
    :rtype: ``tuple``
    '''
    try:
        import platformupdate
        
        return platformupdate.get_os_version()

    except ImportError:
        return _get_os_version_lsb_release()


def _get_os_version_lsb_release():
    '''Get OS version.

    Uses 'lsb_release -sri' or calls :func:`_get_os_version_uname`

    :returns: (name, version)
    :rtype: ``tuple``
    '''
    try:
        output = subprocess.check_output('lsb_release -sri', shell=True)
        lines = output.strip().split()
        name, version = lines
        if version.lower() == 'rolling':
            version = ''
        
        return name, version

    except:
        return _get_os_version_uname()


def _get_os_version_uname():
    '''Get OS version.

    Uses 'uname -rs'  or simply returns ('Linux', '')

    :returns: (name, version)
    :rtype: ``tuple``
    '''
    try:
        output = subprocess.check_output('uname -rs', shell=True)
        lines = output.strip().split()
        name, version = lines
        
        return name, version

    except:
        return 'Linux', ''  # most likely :)


def compare_versions(version1, version2):
    '''Compare versions.

    :param version1: Version.
    :type version1: ``string``
    :param version2: Version.
    :type version2: ``string``
    :returns: positive if version1>version2
    :rtype:``int``
    '''

    version1 = re.sub('[^0-9.]', '', version1)
    version2 = re.sub('[^0-9.]', '', version2)
    
    def int_or_0(n):
        try:
            return int(n)
        
        except:
            return 0

    version1 = [int_or_0(n) for n in version1.split('.')]
    version2 = [int_or_0(n) for n in version2.split('.')]
    
    len1 = len(version1)
    len2 = len(version2)
    length = min(len1, len2)
    for i in xrange(length):
        p1 = version1[i]
        p2 = version2[i]
        
        if p1 < p2:
            return -1
        
        elif p1 > p2:
            return 1
    
    if len1 < len2:
        return -1
    
    elif len1 > len2:
        return 1
    
    else:
        return 0


def get_all_versions():
    '''Get all versions.

    :returns: :func:`platformupdate.get_all_versions`
    :rtype: ``list``
    '''
    try:
        import platformupdate

    except ImportError:
        return []
    
    return platformupdate.get_all_versions()


def perform_update(version):
    '''Perform update.

    Calls :func:`platformupdate.perform_update`

    :param version: Version.
    :type version: ``string``    
    '''
    logging.info('updating to version %(version)s...' % {'version': version})

    try:
        import platformupdate

    except ImportError:
        logging.error('updating is not available on this platform')
        
        raise Exception('updating is not available on this platform')

    # schedule the actual update for two seconds later,
    # since we want to be able to respond to the request right away
    ioloop.IOLoop.instance().add_timeout(datetime.timedelta(seconds=2),
                                         platformupdate.perform_update, version=version)

