import os
import sys
import time
import argparse
import itertools
import datetime
from tzlocal.unix import get_localzone, get_localzone_name, reload_localzone
from paths import clean_filename
from pyicloud import PyiCloudService


def authenticate(api):
    if api.requires_2fa:
        print("Two-factor authentication required.")
        code = input("Enter the code you received of one of your approved devices: ")
        result = api.validate_2fa_code(code)
        print("Code validation result: %s" % result)

        if not result:
            print("Failed to verify security code")
            sys.exit(1)

        if not api.is_trusted_session:
            print("Session is not trusted. Requesting trust...")
            result = api.trust_session()
            print("Session trust result %s" % result)

            if not result:
                print("Failed to request trust. You will likely be prompted for the code again in the coming weeks")
    elif api.requires_2sa:
        import click
        print("Two-step authentication required. Your trusted devices are:")

        devices = api.trusted_devices
        for i, device in enumerate(devices):
            print(
                "  %s: %s" % (i, device.get('deviceName',
                                            "SMS to %s" % device.get('phoneNumber')))
            )

        device = click.prompt('Which device would you like to use?', default=0)
        device = devices[device]
        if not api.send_verification_code(device):
            print("Failed to send verification code")
            sys.exit(1)

        code = click.prompt('Please enter validation code')
        if not api.validate_verification_code(device, code):
            print("Failed to verify verification code")
            sys.exit(1)


def set_utime(download_path, created_date):
    """Set date & time of the file"""
    ctime = time.mktime(created_date.timetuple())
    os.utime(download_path, (ctime, ctime))


def update_mtime(photo, download_path):
    """Set the modification time of the downloaded file to the photo creation date"""
    if photo.created:
        created_date = None
        try:
            created_date = photo.created.astimezone(
                get_localzone())
        except (ValueError, OSError):
            # We already show the timezone conversion error in base.py,
            # when generating the download directory.
            # So just return silently without touching the mtime.
            return
        set_utime(download_path, created_date)


last_download_time_file = './last_download_time.txt'


def get_last_download_time(file):
    local_tz = get_localzone()
    min_datetime = datetime.datetime.min
    min_datetime_with_tz = local_tz.localize(min_datetime)
    if os.path.exists(file) and os.path.getsize(file) > 0:
        with open(file, 'r') as f:
            dt_str = f.read()
            # 将字符串转换为datetime对象
            if dt_str:
                try:
                    dt_from_str = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                    return dt_from_str
                except ValueError:
                    print(f"文件中存储的时间有误，请人为确认{dt_str}")
                    exit(1)
            else:
                return min_datetime_with_tz
    # 如果文件不存在或者为空，返回一个空的datetime对象
    else:
        return min_datetime_with_tz


def update_download_time(file, record_time):
    with open(file, 'w') as f:
        dt_str = record_time.strftime("%Y-%m-%d %H:%M:%S")
        f.write(dt_str)


def download_photos(api, album_name='All Photos', download_dir='/Users/chen/icloudpy/', num_photos=None):
    photos = api.photos.albums[album_name]
    photos_list = itertools.islice(photos, num_photos) if num_photos else photos
    current_download_time = get_localzone().localize(datetime.datetime.min)

    last_download_time = get_last_download_time(last_download_time_file)
    try:
        for photo in photos_list:
            #因为icloud的图片是按照由新到旧的，此处判断照片是否是之前下载过的，
            #为了简单直接比时间，不去判断实际文件
            photo_create_time = photo.created.astimezone(get_localzone())
            if photo_create_time < last_download_time:
                continue
            photo_name = clean_filename(photo.filename)
            photo_response = photo.download()
            if photo_response:
                temp_download_path = download_dir + photo_name + ".part"
                with open(temp_download_path, "wb") as file_obj:
                    for chunk in photo_response.iter_content(chunk_size=1024):
                        if chunk:
                            file_obj.write(chunk)
                os.rename(temp_download_path, download_dir + photo_name)
                update_mtime(photo, download_dir + photo_name)
                current_download_time = max(current_download_time, photo_create_time)
    except Exception:
        print("download error" + os.path.basename(__file__) + "  line：" + __line__)
    finally:
        update_download_time(last_download_time_file, current_download_time)

# default='502435856@qq.com',
def main():
    parser = argparse.ArgumentParser(description='Download photos from iCloud.', argument_default=argparse.SUPPRESS)
    parser.add_argument('--num_photos', type=int, default=None, help='the number of photos to download')
    parser.add_argument('--email', type=str,  default='502435856@qq.com', help='iCloud email address')
    parser.add_argument('--password', type=str, default='Alibaba202211', help='iCloud password')
    parser.add_argument('--output', type=str, default='./', help='output directory')
    args = parser.parse_args()

    api = PyiCloudService(args.email, args.password)
    authenticate(api)
    download_photos(api, download_dir=args.output, num_photos=args.num_photos)


if __name__ == '__main__':
    main()
