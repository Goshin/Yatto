# Yatto

Parse and play online video on local player

---

## Features

- Merge video segments as a single video files.
- Danmaku supported: Tudou, Acfun, Bilibili

## Requirements

- Python 3
- Mpv Player
- FFmpeg with FFprobe

## Usage

```shell
usage: Yatto.py [-h] [-q QUALITY] URL

positional arguments:
  URL

optional arguments:
  -h, --help            show this help message and exit
  -q QUALITY, --quality QUALITY
                        Specify video quality, 1 for normal quality, 2 for
                        high quality, 3 for ultra high quality
```

Examples:

```shell
$ python Yatto.py http://www.xxxxx.com/albumplay/92J2xqpSxWY.html
$ python Yatto.py -q=1 http://www.xxxxx.com/albumplay/92J2xqpSxWY.html
```

## License

The software is released under GNU General Public License.
