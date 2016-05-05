# Yatto

Parse and play online video with danmaku on local player.

---

## Features

- Merge video segments as a single video file.
- Danmaku supported: Tudou, Acfun, Bilibili

## Requirements

- Python 3
- Mpv Player
- FFmpeg with FFprobe
- [You-Get](https://github.com/soimort/you-get)

## Usage

```shell
usage: yatto.py [-h] [-i] [-e EXTRA] URL

positional arguments:
  URL

optional arguments:
  -h, --help            show this help message and exit
  -i, --info            Show the format and quality information of the video
  -e EXTRA, --extra EXTRA
                        Specify the you-get options, like --extra="--format=hd"
```

Examples:

```shell
$ python Yatto.py http://www.xxxxx.com/albumplay/92J2xqpSxWY.html
```

To specify the video quality:

```shell
$ python Yatto.py -i http://www.xxxxx.com/albumplay/Lqfme5hSolM/wNMcatvqbWU.html
2016-05-05 20:34:45,789 - INFO - Parsing page...
title:               第678话 真
streams:             # Available quality and codecs
    [ DEFAULT ] _________________________________
    - format:        hd3
      container:     flv
      video-profile: 1080P
      size:          524.2 MiB (549712642 bytes)
    # download-with: you-get --format=hd3 [URL]

    - format:        hd2
      container:     flv
      video-profile: 超清
      size:          272.8 MiB (286074050 bytes)
    # download-with: you-get --format=hd2 [URL]

    - format:        mp4
      container:     mp4
      video-profile: 高清
      size:          144.5 MiB (151558876 bytes)
    # download-with: you-get --format=mp4 [URL]

    - format:        flvhd
      container:     flv
      video-profile: 标清
      size:          69.9 MiB (73280225 bytes)
    # download-with: you-get --format=flvhd [URL]

$ python Yatto.py --extra="--format=mp4" http://www.xxxxx.com/albumplay/Lqfme5hSolM/wNMcatvqbWU.html
```

## License

The software is released under GNU General Public License.
