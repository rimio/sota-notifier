#
# Copyright (c) 2023 Vasile Vilvoiu (YO7JBP) <vasi@vilvoiu.ro>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#

#
# See SOTA API here: https://api2.sota.org.uk/docs/index.html
#

import argparse
import urllib3
import json
import time
import subprocess
import re
import mpu


summits = dict()


def get_spots(num):
    http = urllib3.PoolManager()
    resp = http.request('GET', 'https://api2.sota.org.uk/api/spots/{}/all'.format(num))
    spots = json.loads(resp.data)
    return spots


def get_summit(assocCode, summitCode):
    # cached?
    global summits
    if (assocCode, summitCode) in summits.keys():
        return summits[(assocCode, summitCode)]
    # fetch
    http = urllib3.PoolManager()
    resp = http.request('GET', 'https://api2.sota.org.uk/api/summits/{}/{}'.format(assocCode, summitCode))
    summit = json.loads(resp.data)
    # cache
    summits[(assocCode, summitCode)] = summit
    return summit


def spot_to_string(spot, summit, distance):
    tstr = time.strftime('%H%Mz', time.strptime(spot['timeStamp'], '%Y-%m-%dT%H:%M:%S.%f'))
    text = '[{}] {} at {} on {}/{} @ {}m, {:.0f}km away, {}MHz {}'.format(
            spot['id'],
            spot['callsign'],
            tstr,
            spot['associationCode'],
            spot['summitCode'],
            summit['altM'],
            distance,
            spot['frequency'],
            str.upper(spot['mode']))
    return text


def spot_to_notification(spot, summit, distance):
    tstr = time.strftime('%H%Mz', time.strptime(spot['timeStamp'], '%Y-%m-%dT%H:%M:%S.%f'))
    text = '{} at {}\n\nOn {}/{}, {:.0f}km away\n\n{}MHz {}'.format(
            spot['callsign'],
            tstr,
            spot['associationCode'],
            spot['summitCode'],
            distance,
            spot['frequency'],
            str.upper(spot['mode']))
    return text


def handle_spot(spot, curr_loc, threshold):
    # fetch summit
    assocCode = spot['associationCode']
    summitCode = spot['summitCode']
    summit = get_summit(assocCode, summitCode)
    summitLoc = (float(summit['latitude']), float(summit['longitude']))
    distance = mpu.haversine_distance(curr_loc, summitLoc)

    if distance > threshold:
        return # too far away

    # build strings
    print(spot_to_string(spot, summit, distance))
    text = spot_to_notification(spot, summit, distance)

    # notify
    subprocess.Popen(['notify-send', '-a', 'SOTA notifier', text])


def main():
    parser = argparse.ArgumentParser(description='SOTA desktop notifier')
    parser.add_argument('location', type=str, help='base station location, as decimal "latitude,longitude" string')
    parser.add_argument('-d', '--distance', type=float, default=2000, help='maximum distance of spots, in kilometers')
    parser.add_argument('-i', '--interval', type=int, default=60, help='interval between retrieval of spots, in seconds')
    args = parser.parse_args()

    # location
    match = re.fullmatch('^(.+)[,](.+)$', args.location)
    if len(match.groups()) != 2:
        print('Invalid location, expecting decimal "latitude,longitude"')
        return
    location = (float(match.groups()[0]), float(match.groups()[1]))
    print('Location set at: {}, {}'.format(location[0], location[1]))

    # get latest spot
    baseline = get_spots(1)
    assert len(baseline) == 1
    latest = baseline[0]['id']
    print('Latest spot id: {}'.format(latest))

    # keep waiting
    while True:
        time.sleep(args.interval)

        # retrieve (potential) new spots
        spots = get_spots(-1 * max(1, args.interval / 3600))

        # determine new spots
        for spot in reversed(spots):
            if spot['id'] > latest:
                handle_spot(spot, location, args.distance)

        # keep latest
        if len(spots) > 0:
            latest = spots[0]['id']


if __name__ == "__main__":
    main()
