import argparse, logging
import json, base64, gzip
import re, html, codecs
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


def encrypt(data, password):
    key = password.encode('utf-8')
    try:
        cipher = AES.new(key, AES.MODE_CBC)
    except:
        logging.error(f"错误：{password}")
        exit(1)
    ct_bytes = cipher.encrypt(pad(data, AES.block_size))
    return json.dumps({
        "iv": base64.b64encode(cipher.iv).decode('utf-8'),
        "ct": base64.b64encode(ct_bytes).decode('utf-8')
    }).encode("utf-8")


def decrypt(data, password):
    key = password.encode('utf-8')
    data = json.loads(data)
    iv = base64.b64decode(data["iv"])
    ct = base64.b64decode(data["ct"])
    cipher = AES.new(key, AES.MODE_CBC, iv)
    pt = unpad(cipher.decrypt(ct), AES.block_size)
    return pt


def getNotError(response):
    logging.debug(f"Url: {response.url}")
    response.raise_for_status()
    text = response.text
    if text.find("<title>错误 - 7FA4</title>") != -1:
        match = re.search(
            r'<div class="ui negative icon message">\s*<i class="remove icon"></i>\s*<div class="content">\s*<div class="header" style="margin-bottom: 10px; ">\s*(.*)\s*</div>', text)
        if match:
            item = html.unescape(match.group(1))
            logging.error(f"错误：{item}")
        else:
            logging.error("未知错误")
        with open("error.html", "w", encoding="utf-8") as f:
            f.write(text)
        logging.warning("HTML保存在error.html")
        exit(1)
    else:
        return text
    

def getStatus(submissionid, cookies, headers):
    response = requests.get(
        f"http://jx.7fa4.cn:8888/submissions/?id={submissionid}",
        headers=headers, cookies=cookies
    )
    text = getNotError(response)
    match = re.search(
        r"const itemList *= *(\[.*\])",
        text,
        re.DOTALL
    )
    if match:
        match = json.loads(f"{match.group(1)}")
        for item in match:
            if item["info"]["submissionId"] == submissionid:
                return item["result"]["result"]
        else:
            logging.error(f"无法解析状态：{match}")
            exit(1)
    else:
        logging.error("无法解析状态")
        exit(1)


def revoke(submissionid, cookies, headers):
    while getStatus(submissionid, cookies, headers) != "Compile Error":
        pass
    response = requests.post(
        f"http://jx.7fa4.cn:8888/submission/{submissionid}/revoke",
        headers=headers, cookies=cookies
    )
    getNotError(response)
    logging.debug(f"Revoke成功")


def get_choice(prompt, default="yes", options=("yes", "no", "cancel")):
    prompt_options = "/".join(f"[{opt}]" if opt == default else opt for opt in options)
    while True:
        user_input = input(f"{prompt} ({prompt_options}) ").strip().lower()
        if not user_input:
            return default
        elif user_input in options:
            return user_input
        else:
            print(f"无效输入，请输入以下之一: {', '.join(options)}")


def upload(problemid, file, password, usersid):
    cookies = {"login": usersid}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    username = re.search(r"%5B%22(.+?)%22", usersid)
    if username:
        username = username.group(1)
        logging.debug(f"用户名：{username}")
    else:
        logging.error("无法解析用户名")
        exit(1)
    url = f'http://jx.7fa4.cn:8888/problem/{problemid}/submit?contest_id=&limit=true'
    with open(file, 'rb') as f:
        obj = f.read()
        obj = gzip.compress(obj)
        if password:
            obj = encrypt(obj, password)
        obj = base64.b64encode(obj).decode('utf-8')
        logging.debug(f"上传文件大小：{len(obj)}")
        logging.debug(f"上传文件：{obj}")
    obj = json.dumps({
        "filename": file,
        "object": obj
    })
    datas = {
        "language": "cpp17",
        "code": obj
    }
    files = {"answer": ('', '', 'application/octet-stream')}
    logging.debug("正在上传文件")
    response = requests.post(
        url, data=datas, cookies=cookies, headers=headers,
        files=files, allow_redirects=True
    )
    getNotError(response)
    logging.debug(f"上传成功")
    url = f"http://jx.7fa4.cn:8888/submissions?contest=&problem_id={problemid}&submitter={username}&min_score=0&max_score=100&language=&status="
    response = requests.get(
        url,
        headers=headers, cookies=cookies
    )
    match = re.search(
        r"const itemList *= *(\[.*\])",
        getNotError(response),
        re.DOTALL
    )
    if match:
        match = json.loads(f"{match.group(1)}")
        for item in match:
            if item["result"]["result"] == "Deleted":
                logging.warning(f"提交ID{item["info"]["submissionId"]}已被删除")
                choice = get_choice(f"是否跳过？（Yes寻找下一个，Cancel退出）", default="cancel", options=("yes", "cancel"))
                if choice == "cancel":
                    return
                else:
                    continue
            item = item['info']
            url = f"http://jx.7fa4.cn:8888/submission/{item["submissionId"]}"
            response = requests.get(
                url,
                headers=headers, cookies=cookies
            )
            text = getNotError(response)
            if text.find("继续访问") != -1:
                logging.warning(f"提交{item["submissionId"]}需要二帮")
                choice = get_choice(f"是否确认二帮？（Yes二帮，Cancel退出）", default="cancel", options=("yes", "cancel"))
                if choice == "cancel":
                    return
                else:
                    response = requests.get(
                        url + "?confirm=1",
                        headers=headers, cookies=cookies
                    )
            text = getNotError(response)
            text = re.search(
                r"const unformattedCode = *\"(.+?)\";",
                text,
                re.DOTALL
            ).group(1)
            text = re.sub(r'<[^>]+>', '', text)
            text = html.unescape(text)
            text = codecs.decode(text, "unicode_escape")
            if text != obj:
                continue
            revoke(item["submissionId"], cookies, headers)
            logging.info(f"上传成功，提交ID：{item["submissionId"]}")
            return item["submissionId"]
        else:
            logging.error("无法找到提交ID")


def download(submissionid, password, usersid):
    cookies = {"login": usersid}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    url = f"http://jx.7fa4.cn:8888/submission/{submissionid}"
    response = requests.get(
        url,
        headers=headers, cookies=cookies
    )
    text = getNotError(response)
    if text.find("继续访问") != -1:
        logging.warning(f"提交{submissionid}需要二帮")
        choice = get_choice(f"是否确认二帮？（Yes二帮，Cancel退出）", default="cancel", options=("yes", "cancel"))
        if choice == "cancel":
            return
        else:
            response = requests.get(
                url + "?confirm=1",
                headers=headers, cookies=cookies
            )
            text = getNotError(response)
    text = re.search(
        r"const unformattedCode = *\"(.+?)\";",
        text,
        re.DOTALL
    ).group(1)
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    text = codecs.decode(text, "unicode_escape")
    text = json.loads(text)
    obj = text["object"]
    filename = text["filename"]
    obj = base64.b64decode(obj)
    if password:
        obj = decrypt(obj, password)
    obj = gzip.decompress(obj)
    with open(f"{filename}", "wb") as f:
        f.write(obj)
    logging.debug(f"下载文件：{filename}")
    return obj


if __name__ == '__main__':
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    stream_handler = logging._StderrHandler()
    file_handler = logging.FileHandler('uploader.log')
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s-%(levelname)s:\n%(message)s')
    stream_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)
    
    parser = argparse.ArgumentParser(description="7FA4二进制文件上传器")
    old_help = parser.print_help
    
    def show_error(message):
        logging.error(f"参数错误：{message}")
        parser.print_help()
        parser.exit(1)
    
    def print_help():
        old_help()
        upload_parser.print_help()
        download_parser.print_help()
        
    parser.error = show_error
    parser.print_help = print_help
    subparsers = parser.add_subparsers(
        title="操作",
        dest="command"
    )
    parser.add_argument(
        "usersid", type=str,
        help="用户的Cookie（从Cookie上复制login）"
    )
    upload_parser = subparsers.add_parser(
        "upload",
        help="上传文件"
    )
    download_parser = subparsers.add_parser(
        "download",
        help="下载文件"
    )
    upload_parser.add_argument(
        "file", type=str,
        help="要上传的文件（最大1M）"
    )
    upload_parser.add_argument(
        "--problem-id",
        dest="problemid",
        type=int,
        help="题目号（注意会二帮，默认输出排列，请输入号数如73558）",
        default=73558
    )
    upload_parser.add_argument(
        '--password',
        dest="password",
        type=str,
        default="",
        help="加密密码，默认不加密，注意长度为16/32字节",
    )
    download_parser.add_argument(
        "submissionid", type=int,
        help="提交ID"
    )
    download_parser.add_argument(
        "--password",
        dest="password",
        type=str,
        default="",
        help="解密密码，默认没有密码",
    )
    parser.add_argument(
        "-l", "--log-level",
        dest="log_level",
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help="日志级别"
    )
    args = parser.parse_args()
    stream_handler.setLevel(getattr(logging, args.log_level))
    match args.command:
        case "upload":
            upload(
                args.problemid,
                args.file,
                args.password,
                args.usersid
            )
        case "download":
            download(
                args.submissionid,
                args.password,
                args.usersid
            )
    
