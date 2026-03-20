import time
import requests


def wait_for_internet(urls, timeout, interval, max_wait, logger=None):
    log = logger or (lambda message: None)
    log("Waiting for VPN/Internet connectivity...")

    start_time = time.time()

    while time.time() - start_time < max_wait:
        for url in urls:
            try:
                response = requests.get(url, timeout=timeout)
                if response.status_code == 200:
                    log(f"Internet connectivity detected via {url}")
                    return True
            except requests.RequestException:
                continue

        log(f"Internet not available yet, retrying in {interval}s...")
        time.sleep(interval)

    log(f"Internet not available after {max_wait}s")
    return False
