import requests
from ipaddress import ip_network
import concurrent.futures
import re

# ------------------------------
# 配置
# ------------------------------
NETWORK_FILE = "network.txt"
PORTS = [80, 3000, 3001, 8080, 5000, 8000, 443, 8443]
TIMEOUT = 2

OUTPUT_FILE = "scan_result.txt"

# ------------------------------
# Next.js 特征
# ------------------------------
NEXT_PATHS = [
    "/_next/",
    "/_next/static/",
    "/_next/static/chunks/",
]

# ------------------------------
# Dify 特征
# ------------------------------
DIFY_PATHS = [
    "/v1/ping",
    "/console/",
    "/signin",
]

# ------------------------------
# React 特征
# ------------------------------
REACT_PATHS = [
    "/static/js/main.js",
    "/asset-manifest.json",
    "/manifest.json",
]

REACT_REGEX_JS = re.compile(r"main\.[a-z0-9]+\.js")
REACT_REGEX_CHUNK = re.compile(r"[a-z0-9]+\.chunk\.js")


# ============ Next.js 检测 ============
def check_nextjs(ip, port):
    base_url = f"http://{ip}:{port}"

    try:
        r = requests.get(base_url, timeout=TIMEOUT)
        headers = {k.lower(): v.lower() for k, v in r.headers.items()}

        if "x-powered-by" in headers and "next.js" in headers["x-powered-by"]:
            return True, "Header: x-powered-by: next.js"
        if "x-nextjs-cache" in headers:
            return True, "Header: x-nextjs-cache"
    except:
        pass

    for path in NEXT_PATHS:
        try:
            r = requests.get(base_url + path, timeout=TIMEOUT)
            if r.status_code == 200 and "_next" in r.text:
                return True, f"Path: {path}"
        except:
            pass

    return False, None


# ============ Dify 检测 ============
def check_dify(ip, port):
    base_url = f"http://{ip}:{port}"

    try:
        r = requests.get(base_url, timeout=TIMEOUT)
        headers = {k.lower(): v.lower() for k, v in r.headers.items()}
        body = r.text.lower()

        if "x-dify-version" in headers:
            return True, "Header: x-dify-version"
        if "dify" in headers.get("x-powered-by", ""):
            return True, "Header: x-powered-by"
        if "dify" in body or "ai application platform" in body:
            return True, "HTMLKeyword: Dify"
    except:
        pass

    for path in DIFY_PATHS:
        try:
            r = requests.get(base_url + path, timeout=TIMEOUT)
            if r.status_code == 200 and ("dify" in r.text.lower() or "version" in r.text.lower()):
                return True, f"Path: {path}"
        except:
            pass

    return False, None


# ============ React 检测 ============
def check_react(ip, port):
    base_url = f"http://{ip}:{port}"

    for path in REACT_PATHS:
        try:
            r = requests.get(base_url + path, timeout=TIMEOUT)
            if r.status_code == 200:
                return True, f"Path: {path}"
        except:
            pass

    try:
        r = requests.get(base_url, timeout=TIMEOUT)
        body = r.text.lower()

        if "react" in body or "react-dom" in body or "create-react-app" in body:
            return True, "HTMLKeyword: react"

        if REACT_REGEX_JS.search(body) or REACT_REGEX_CHUNK.search(body):
            return True, "JSChunk: main.*.js / chunk.js"
    except:
        pass

    return False, None


# ============ 总服务检测 ============
def check_services(ip, port):
    found, detail = check_nextjs(ip, port)
    if found:
        return "Next.js", detail

    found, detail = check_dify(ip, port)
    if found:
        return "Dify", detail

    found, detail = check_react(ip, port)
    if found:
        return "React", detail

    return None, None


# ============ 读取 network.txt ============
def load_networks():
    networks = []
    try:
        with open(NETWORK_FILE, "r", encoding="utf-8") as f:
            for line in f:
                net = line.strip()
                if net:
                    networks.append(net)
        print(f"读取到 {len(networks)} 个网段：")
        for n in networks:
            print(" -", n)
    except FileNotFoundError:
        print("错误：无法找到 network.txt")
        exit(1)

    return networks


# ============ 扫描主程序 ============
def scan_network():
    networks = load_networks()
    results = []

    # 遍历所有网段
    for net in networks:
        print(f"\n开始扫描网段：{net}")
        ips = [str(ip) for ip in ip_network(net).hosts()]

        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            future_to_target = {
                executor.submit(check_services, ip, port): (ip, port)
                for ip in ips for port in PORTS
            }

            for future in concurrent.futures.as_completed(future_to_target):
                ip, port = future_to_target[future]
                try:
                    service, detail = future.result()
                    if service:
                        url = f"http://{ip}:{port}"
                        results.append(url)
                        print(f"[✔] {url}  →  {service} ({detail})")
                except:
                    pass

    # 写入 txt（只写 URL）
    if results:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            for url in results:
                f.write(url + "\n")

        print(f"\nURL 已保存到：{OUTPUT_FILE}")
    else:
        print("未找到任何服务")


if __name__ == "__main__":
    scan_network()
