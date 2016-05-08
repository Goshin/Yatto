import argparse
import math
import re
import logging
import json
import subprocess
import io
import tempfile

from pip._vendor.requests.packages import chardet

import danmaku2ass
import traceback
import urllib.request as urllib2
import urllib.parse
import zlib

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, \
                      like Gecko) Chrome/47.0.2526.106 Safari/537.36"

logger = logging.getLogger(__name__)


def simply_get_url(url):
    request = urllib2.Request(url)
    request.add_header('User-Agent', DEFAULT_USER_AGENT)

    response = urllib2.urlopen(request)

    content_encoding = response.getheader('Content-Encoding')
    raw_data = response.read()
    if content_encoding == 'gzip' or raw_data.startswith(b'\x1F\x8B'):
        return zlib.decompress(raw_data, 16 + zlib.MAX_WBITS)
    elif content_encoding == 'deflate':
        decompressobj = zlib.decompressobj(-zlib.MAX_WBITS)
        return decompressobj.decompress(raw_data) + decompressobj.flush()
    else:
        return raw_data


def you_get(url, print_info, extra_args):
    try:
        command = ['you-get', '-u']
        if print_info:
            command.append('-i')
        if extra_args:
            command.append(extra_args)
        command.append(url)
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        try:
            output = process.communicate()[0]
            output = output.decode(chardet.detect(output).get('encoding', 'utf-8'), 'replace')
        except KeyboardInterrupt:
            process.terminate()
            return '', []
        if print_info:
            print(output)
            return '', []
        name_match = re.compile(r'title:\s*(.*?)(\r|\n)').search(output)
        name = name_match.group(1) if name_match else 'Unknown'
        url_re = re.compile(r'(http.*?)(\r|\n)')
        url_match = url_re.search(output)
        video_url = []
        while url_match:
            video_url.append(url_match.group(1))
            url_match = url_re.search(output, url_match.end(0))
        return name, video_url
    except Exception as e:
        logger.error('parse video failed {}'.format(e))
        return '', []


"""Functions(get_video_size, convert_comments, launch_player) from BiliDan
Link: https://github.com/m13253/BiliDan/blob/master/bilidan.py
License: MIT

Copyright (C) 2014

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""


def get_video_size(media_urls):
    try:
        if media_urls[0].startswith('http:') or media_urls[0].startswith('https:'):
            ffprobe_command = ['ffprobe', '-icy', '0', '-loglevel', 'repeat+error', '-print_format', 'json',
                               '-select_streams', 'v', '-show_streams', '-timeout', '60000000', '-user-agent',
                               DEFAULT_USER_AGENT, '--', media_urls[0]]
        else:
            ffprobe_command = ['ffprobe', '-loglevel', 'repeat+error', '-print_format', 'json', '-select_streams', 'v',
                               '-show_streams', '--', media_urls[0]]
        ffprobe_process = subprocess.Popen(ffprobe_command, stdout=subprocess.PIPE)
        try:
            ffprobe_output = json.loads(ffprobe_process.communicate()[0].decode('utf-8', 'replace'))
        except KeyboardInterrupt:
            logging.warning('Cancelling getting video size, press Ctrl-C again to terminate.')
            ffprobe_process.terminate()
            return 0, 0
        width, height, widthxheight = 0, 0, 0
        for stream in dict.get(ffprobe_output, 'streams') or []:
            if dict.get(stream, 'width') * dict.get(stream, 'height') > widthxheight:
                width, height = dict.get(stream, 'width'), dict.get(stream, 'height')
        return width, height
    except Exception as e:
        logger.error('get video size failed {}'.format(e))
        return 0, 0


def convert_comments(danmaku_url_or_raw, video_size):
    if isinstance(danmaku_url_or_raw, str):
        resp_comment = simply_get_url(danmaku_url_or_raw)
    else:
        resp_comment = danmaku_url_or_raw
    comment_in = io.StringIO(resp_comment.decode('utf-8', 'replace'))
    comment_out = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', newline='\r\n', prefix='tmp-danmaku2ass-',
                                              suffix='.ass', delete=False)
    logging.info('Invoking Danmaku2ASS, converting to %s' % comment_out.name)
    d2aflags = {}
    d2a_args = dict({'stage_width': video_size[0], 'stage_height': video_size[1], 'font_face': 'SimHei',
                     'font_size': math.ceil(video_size[1] / 21.6), 'text_opacity': 0.8,
                     'duration_marquee': min(max(6.75 * video_size[0] / video_size[1] - 4, 3.0), 8.0),
                     'duration_still': 5.0, 'reserve_blank': video_size[1] // 10}, **d2aflags)
    for i, j in ((('stage_width', 'stage_height', 'reserve_blank'), int),
                 (('font_size', 'text_opacity', 'comment_duration', 'duration_still', 'duration_marquee'), float)):
        for k in i:
            if k in d2aflags:
                d2a_args[k] = j(d2aflags[k])
    try:
        danmaku2ass.Danmaku2ASS([comment_in], comment_out, **d2a_args)
    except Exception as e:
        logging.error('Danmaku2ASS failed, comments are disabled. {}'.format(e))
    comment_out.flush()
    comment_out.close()  # Close the temporary file early to fix an issue related to Windows NT file sharing
    return comment_out


def launch_player(video_name, media_urls, comment_out):
    command_line = ['mpv', '--autofit', '950x540']
    command_line += ['--force-media-title', video_name]
    if len(media_urls) > 1:
        command_line += ['--cache=1000', '--cache-backbuffer=1000', '--cache-secs=5', '--merge-files']
    if comment_out and comment_out.name:
        command_line += ['--no-video-aspect', '--sub-ass', '--sub-file', comment_out.name]

    command_line += media_urls
    player_process = subprocess.Popen(command_line)
    try:
        player_process.wait()
    except KeyboardInterrupt:
        logging.info('Terminating media player...')
        try:
            player_process.terminate()
            try:
                player_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                logging.info('Killing media player by force...')
                player_process.kill()
        except Exception:
            pass
            raise
        return player_process.returncode


def parse_youku_danmaku(url):
    page = simply_get_url(url).decode('utf-8')
    video_id_match = re.search(r'videoId\s+=\s+\'(\d+)', page)
    video_seconds_match = re.search(r'videoSeconds\s+=\s+Math\.round\((\d+)', page)
    if not video_id_match or not video_seconds_match:
        return ''

    video_id = video_id_match.group(1)
    video_seconds = int(video_seconds_match.group(1)) / 60
    logger.info('Youku danmaku detected')

    danmaku_pool = {'result': []}
    # Download and merge every 5 minute danmaku segments
    segments_num = (int(video_seconds) + 1) // 5
    for i in range(0, int(video_seconds) + 1, 5):
        logger.info('Processing danmaku segment {}/{}'.format(i // 5, segments_num))
        danmaku_url = 'http://service.danmu.youku.com/list?mat={}&mcount=5&ct=1001&uid=0&iid={}'.format(i, video_id)
        segment_raw = simply_get_url(danmaku_url).decode('utf-8')
        segment = json.loads(segment_raw or '{}')
        if not segment.get('count', 0):
            continue
        danmaku_pool['result'].extend(segment.get('result', []))

    return json.dumps(danmaku_pool).encode('utf-8')


def parse_tudou_danmaku(url):
    page = simply_get_url(url).decode('utf-8')
    iid_match = re.search(r',iid: (\d+)', page)
    time_match = re.search(r',time: \'(\d+)', page)
    if not iid_match or not time_match:
        return ''

    iid = iid_match.group(1)
    time = time_match.group(1)
    logger.info('Tudou danmaku detected')

    danmaku_pool = {'result': []}
    # Download and merge every 5 minute danmaku segments
    segments_num = (int(time) + 1) // 5
    for i in range(0, int(time) + 1, 5):
        logger.info('Processing danmaku segment {}/{}'.format(i // 5, segments_num))
        danmaku_url = 'http://service.danmu.tudou.com/list?mat={}&mcount=5&ct=1001&uid=0&iid={}'.format(i, iid)
        segment_raw = simply_get_url(danmaku_url).decode('utf-8')
        segment = json.loads(segment_raw or '{}')
        if not segment.get('count', 0):
            continue
        danmaku_pool['result'].extend(segment.get('result', []))

    return json.dumps(danmaku_pool).encode('utf-8')


def parse_bilibili_danmaku(url):
    page = simply_get_url(url).decode('utf-8')
    cid_re = re.compile(r'cid=(\d+)')
    match = cid_re.search(page)
    danmaku_url = ''
    if match:
        logger.info('Bilibili danmaku detected')
        danmaku_url = 'http://comment.bilibili.com/{}.xml'.format(match.group(1))
    return danmaku_url


def parse_acfun_danmaku(url):
    page = simply_get_url(url).decode('utf-8')
    cid_re = re.compile(r'''data-vid=['"](\d+)['"]''')
    match = cid_re.search(page)
    danmaku_url = ''
    if match:
        logger.info('Acfun danmaku detected')
        danmaku_url = 'http://danmu.aixifan.com/V2/' + match.group(1)
    return danmaku_url


danmaku_parsers = {'tudou.com': parse_tudou_danmaku, 'bilibili.com': parse_bilibili_danmaku,
                   'acfun': parse_acfun_danmaku, 'youku': parse_youku_danmaku}


def parse_video(url, print_info, extra_args):
    name, urls = you_get(url, print_info, extra_args)
    danmaku_url = ''

    danmaku_parser = None
    host = urllib.parse.urlparse(url).hostname
    for k, v in danmaku_parsers.items():
        if host.find(k) > -1:
            danmaku_parser = v
            break

    if danmaku_parser and not print_info:
        danmaku_url = danmaku_parser(url)

    return name, urls, danmaku_url


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url', metavar='URL')
    parser.add_argument('-i', '--info', default=False, action='store_true',
                        help='Show the format and quality information of the video')
    parser.add_argument('-e', '--extra', default='', type=str,
                        help='Specify the you-get options, like --extra="--format=hd"')
    args = parser.parse_args()
    logging.basicConfig(level='INFO', format='%(asctime)s - %(levelname)s - %(message)s')

    logger.info('Parsing page...')
    name, video_url, danmaku = parse_video(args.url, args.info, args.extra)

    if args.info:
        return

    danmaku_file = ''
    if danmaku:
        # convert danmaku to ASS
        try:
            logger.info('Fetching danmaku')
            danmaku_file = convert_comments(danmaku, get_video_size(video_url))
        except Exception as e:
            traceback.print_exc()
            logger.error('Download danmaku failed, {}'.format(e))

    if not len(video_url):
        logger.error('Parse video page failed')
        exit(0)

    logger.info('Buffering video header, this may take a while')
    launch_player(name, video_url, danmaku_file)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info('Canceled')
