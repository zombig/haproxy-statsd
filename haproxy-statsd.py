#!/usr/bin/python
"""
usage: report_haproxy.py [-h] [-c CONFIG]

Report haproxy stats to statsd

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        Config file location

Config file format
------------------
[haproxy-statsd]
haproxy_url = http://127.0.0.1:1936/;csv
haproxy_user =
haproxy_password =
statsd_host = 127.0.0.1
statsd_port = 8125
statsd_namespace = haproxy.(HOSTNAME)
"""
import requests
from requests.auth import HTTPBasicAuth
import csv
import socket
import argparse
import ConfigParser


def get_haproxy_report(url, user=None, password=None):
    auth = None
    if user:
        auth = HTTPBasicAuth(user, password)
    r = requests.get(url, auth=auth)
    r.raise_for_status()
    data = r.content.lstrip('# ')
    return csv.DictReader(data.splitlines())


def report_to_statsd(stat_rows,
                     host='127.0.0.1',
                     port=8125,
                     namespace='haproxy'):
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    stat_count = 0

    # Report for each row
    for row in stat_rows:
        path = '.'.join([namespace, row['pxname'], row['svname']])

        # Report each stat that we want in each row
        for stat in ['scur', 'smax', 'ereq', 'econ', 'rate', 'bin', 'bout']:
            val = row.get(stat) or 0
            udp_sock.sendto(
                '%s.%s:%s|g' % (path, stat, val), (host, port))
            stat_count += 1
    return stat_count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Report haproxy stats to statsd')
    parser.add_argument('-c', '--config',
                        help='Config file location',
                        default='./haproxy-statsd.conf')

    args = parser.parse_args()
    config = ConfigParser.ConfigParser({
        'haproxy_url': 'http://127.0.0.1:1936/;csv',
        'haproxy_user': '',
        'haproxy_password': '',
        'statsd_namespace': 'haproxy.(HOSTNAME)',
        'statsd_host': '127.0.0.1',
        'statsd_port': '8125',
    })
    config.add_section('haproxy-statsd')
    config.read(args.config)

    report_data = get_haproxy_report(
        config.get('haproxy-statsd', 'haproxy_url'),
        user=config.get('haproxy-statsd', 'haproxy_user'),
        password=config.get('haproxy-statsd', 'haproxy_password'))

    # Generate statsd namespace
    namespace = config.get('haproxy-statsd', 'statsd_namespace')
    if '(HOSTNAME)' in namespace:
        namespace = namespace.replace('(HOSTNAME)', socket.gethostname())

    report_num = report_to_statsd(
        report_data,
        namespace=namespace,
        host=config.get('haproxy-statsd', 'statsd_host'),
        port=config.getint('haproxy-statsd', 'statsd_port'))

    print("Reported %s stats" % report_num)
    exit(0)
