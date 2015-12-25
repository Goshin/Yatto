import argparse
import math
import re
import logging
import json
import subprocess
import io
import tempfile
import danmaku2ass
import traceback
import http.client as httplib
import urllib.request as urllib2
import urllib.parse

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, \
                      like Gecko) Chrome/47.0.2526.106 Safari/537.36"

logger = logging.getLogger(__name__)


def simple_get_url(url):
    return urllib2.urlopen(url).read()


class Flvcd(object):
    """ JavaScript from flvcd.com

    function createSc(a, t) {
        var b = "26499035657058937199857879755120";
        t = Math.floor(t / (600 * 1000));
        ret = "";
        for (var i = 0; i < a.length; i++) {
            var j = a.charCodeAt(i) ^ b.charCodeAt(i) ^ t;
            j = j % 'z'.charCodeAt(0);
            var c;
            if (j < '0'.charCodeAt(0)) {
                c = String.fromCharCode('0'.charCodeAt(0) + j % 9)
            } else if (j >= '0'.charCodeAt(0) && j <= '9'.charCodeAt(0)) {
                c = String.fromCharCode(j)
            } else if (j > '9'.charCodeAt(0) && j < 'A'.charCodeAt(0)) {
                c = '9'
            } else if (j >= 'A'.charCodeAt(0) && j <= 'Z'.charCodeAt(0)) {
                c = String.fromCharCode(j)
            } else if (j > 'Z'.charCodeAt(0) && j < 'a'.charCodeAt(0)) {
                c = 'Z'
            } else if (j >= 'z'.charCodeAt(0) && j <= 'z'.charCodeAt(0)) {
                c = String.fromCharCode(j)
            } else {
                c = 'z'
            }
            ret += c
        }
        return ret
    }
    """

    @staticmethod
    def create_sc(a, t, b):
        t = int(math.floor(int(t) / (600 * 1000)))
        ret = ""
        for i in range(len(a)):
            j = ord(a[i]) ^ ord(b[i]) ^ t
            j %= ord('z')
            if j < ord('0'):
                c = chr(ord('0') + j % 9)
            elif ord('0') <= j <= ord('9'):
                c = chr(j)
            elif ord('9') < j < ord('A'):
                c = '9'
            elif ord('A') <= j <= ord('Z'):
                c = chr(j)
            elif ord('Z') < j < ord('a'):
                c = 'Z'
            elif ord('z') <= j <= ord('z'):
                c = chr(j)
            else:
                c = 'z'
            ret += c
        return ret

    @staticmethod
    def fetch_page(url, quality=1):
        quality_dict = {1: 'normal', 2: 'high', 3: 'super'}
        url = 'http://www.flvcd.com/parse.php?go=1&kw={}&format={}'.format(url, quality_dict.get(quality))
        conn = httplib.HTTPConnection("www.flvcd.com", 80)
        h = {"Host": "www.flvcd.com",
             "User-Agent": DEFAULT_USER_AGENT}
        conn.request("GET", url, headers=h)
        result = conn.getresponse()
        page = result.read().decode('GBK')

        ad_flag_re = re.compile(r'height:50px; background-color:#FF9966;')
        if not ad_flag_re.search(page):
            return page

        aaa_re = re.compile(r'[a-zA-Z]+=\'(\w{32})\'')
        bbb_re = re.compile(r'[a-zA-Z]+=(\d{13})')
        b_re = re.compile(r'for\|(\d*)\|createSc')

        aaa = aaa_re.search(page)
        bbb = bbb_re.search(page)
        b = b_re.search(page)

        if not aaa or not bbb or not b:
            logger.error('Bypass flvcd AD failed')
            return ''

        g = Flvcd.create_sc(aaa.group(1), bbb.group(1), b.group(1))
        h['Cookie'] = 'go=' + g + '; avdGggggtt=' + bbb.group(1)

        conn.request("GET", url, headers=h)
        result = conn.getresponse()
        page = result.read().decode('GBK')

        return page

    """Function from MoonPlayer
    Link: https://github.com/coslyk/moonplayer/blob/master/src/plugins/moonplayer_utils.py
    License: GPL 3.0
    """

    @staticmethod
    def parse_page(content):
        url_re = re.compile(r'<a href="(http://.+?)".+?onclick=.+?>\s*http://')
        name_re = re.compile(r'document.title\s*=\s*"([^"]+)"')
        page = content
        ret = []

        # get name
        match = name_re.search(page)
        if not match:
            return
        name = match.group(1)

        # get urls
        match = url_re.search(page)
        while match:
            url = match.group(1)
            ret.append(url)  # url
            match = url_re.search(page, match.end(0))
        return name, ret

    @staticmethod
    def parse(url, quality):
        return Flvcd.parse_page(Flvcd.fetch_page(url, quality))


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


def convert_comments(danmaku_url, video_size):
    resp_comment = simple_get_url(danmaku_url)
    comment_in = io.StringIO(resp_comment.decode('utf-8', 'replace'))
    comment_out = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', newline='\r\n', prefix='tmp-danmaku2ass-',
                                              suffix='.ass', delete=False)
    logging.info('Invoking Danmaku2ASS, converting to %s' % comment_out.name)
    d2aflags = {}
    d2a_args = dict({'stage_width': video_size[0], 'stage_height': video_size[1], 'font_face': 'SimHei',
                     'font_size': math.ceil(video_size[1] / 21.6), 'text_opacity': 0.8,
                     'duration_marquee': min(max(6.75 * video_size[0] / video_size[1] - 4, 3.0), 8.0),
                     'duration_still': 5.0}, **d2aflags)
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
        command_line += ['--sub-fps=60', '--sub-ass', '--sub-file', comment_out.name]

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


def parse_tudou_danmaku(url):
    page = simple_get_url(url).decode('utf-8')
    iid_re = re.compile(r',iid: (\d+)')
    match = iid_re.search(page)
    danmaku_url = ''
    if match:
        logger.info('Tudou danmaku detected')
        danmaku_url = 'http://service.danmu.tudou.com/list?mat=0&mcount=5&ct=1001&uid=0&iid=' + match.group(1)
    return danmaku_url


def parse_video(url, quality):
    name, urls = Flvcd.parse(url, quality)
    danmaku_url = ''

    host = urllib.parse.urlparse(url).hostname
    if host.find('tudou.com') > -1:
        danmaku_url = parse_tudou_danmaku(url)

    return name, urls, danmaku_url


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url', metavar='URL')
    parser.add_argument('-q', '--quality', default=3, type=int,
                        help='Specify video quality, 1 for normal quality, 2 for high quality, 3 for ultra high quality')
    args = parser.parse_args()
    logging.basicConfig(level='INFO', format='%(asctime)s - %(levelname)s - %(message)s')

    logger.info('Parsing page...')
    name, video_url, danmaku_url = parse_video(args.url, args.quality)

    danmaku_file = ''
    if danmaku_url:
        # convert danmaku to ASS
        try:
            logger.info('Fetching danmaku')
            danmaku_file = convert_comments(danmaku_url, get_video_size(video_url))
        except Exception as e:
            traceback.print_exc()
            logger.error('download danmaku {} failed, {}'.format(danmaku_url, e))

    logger.info('Buffering video header, this may take a while')
    launch_player(name, video_url, danmaku_file)


if __name__ == '__main__':
    main()