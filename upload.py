import argparse, requests, logging, sys
import base64


def upload(problemid, file, password, usersid):
    url = (f'http://jx.7fa4.cn:8888/problem/{problemid}'
           '/submit?contest_id=&limit=false')
    with open(file, 'rb') as f:
        obj = f.read()
        obj = base64.b64encode(obj).decode('utf-8')
    obj = f"{{\"file\":\"{file}\",\"object\":\"{obj}\"}}"
    data = {
        "language": "cp17",
        "code": obj
    }
    headers = {
        "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome"
            "/114.0.0.0 Safari/537.36",
        "Content-Type": "multipart/form-data"
    }
    cookies = {
        "connect.sid": usersid
    }
    logging.info("正在上传文件")
    response = requests.post(
        url, data=data, headers=headers, cookies=cookies
    )
    response.raise_for_status()
    print(response.text)


if __name__ == '__main__':
    root_logger = logging.getLogger()
    stream_handler = logging._StderrHandler()
    file_handler = logging.FileHandler('upload.log')

    formatter = logging.Formatter('%(asctime)s-%(levelname)s:\n%(message)s')
    stream_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)
    
    parser = argparse.ArgumentParser(
        description="7FA4二进制文件上传器"
    )
    
    def show_error(message):
        logging.error(f"参数错误：{message}")
        parser.print_help()
        parser.exit(1)
        
    parser.error = show_error
    parser.add_argument(
        "file", type=str,
        help="要上传的文件（最大1M）"
    )
    parser.add_argument(
        "usersid", type=str,
        help="用户的SID（从Cookie上复制connect.sid）"
    )
    parser.add_argument(
        "--problemid",
        type=int,
        help="题目号",
        default=73558
    )
    parser.add_argument(
        '--password',
        type=str,
        default=None,
        help="加密密码，默认不加密",
    )
    parser.add_argument(
        "-l", "--log-level",
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help="日志级别"
    )
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level)
    upload(
        args.problemid,
        args.file,
        args.password,
        args.usersid
    )
    
