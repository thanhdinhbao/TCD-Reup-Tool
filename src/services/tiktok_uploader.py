"""TikTok Studio uploader using Selenium + GPMLogin CDP with auto-matching ChromeDriver."""
import os
import re
import time
import json
import logging
import urllib.request
from typing import Optional, Dict, Any, Tuple

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError:
    webdriver = None

logger = logging.getLogger(__name__)

TIKTOK_UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload?from=webapp&tab=video"


def get_chrome_version_from_port(port: int) -> str:
    """Detect running Chrome version on given remote debugging port."""
    try:
        url = f"http://127.0.0.1:{port}/json/version"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            browser_str = data.get("Browser", "")  # e.g. "Chrome/154.0.8037.98"
            m = re.search(r"Chrome/(\d+)", browser_str)
            if m:
                return m.group(1)
    except Exception as e:
        logger.debug(f"Could not query /json/version on port {port}: {e}")
    return ""


def get_matching_chromedriver(major_version: str) -> Optional[str]:
    """Find or download matching ChromeDriver for the running Chrome major version."""
    if not major_version:
        return None

    # 1. Search in local selenium cache
    cache_dir = os.path.expandvars(r"%USERPROFILE%\.cache\selenium\chromedriver\win64")
    if os.path.exists(cache_dir):
        for folder in os.listdir(cache_dir):
            if folder.startswith(f"{major_version}."):
                exe = os.path.join(cache_dir, folder, "chromedriver.exe")
                if os.path.exists(exe):
                    logger.info(f"Found matching cached ChromeDriver for v{major_version}: {exe}")
                    return exe

    # 2. Use SeleniumManager to download/locate matching driver
    try:
        from selenium.webdriver.common.selenium_manager import SeleniumManager
        sm = SeleniumManager()
        paths = sm.binary_paths(["--browser", "chrome", "--browser-version", major_version])
        driver_path = paths.get("driver_path")
        if driver_path and os.path.exists(driver_path):
            logger.info(f"SeleniumManager resolved matching ChromeDriver for v{major_version}: {driver_path}")
            return driver_path
    except Exception as e:
        logger.warning(f"SeleniumManager could not resolve driver for v{major_version}: {e}")

    return None


class TikTokUploader:
    def __init__(
        self,
        gpm_profile_id: str = "",
        remote_debugging_address: str = "127.0.0.1:9222",
        driver_path: str = ""
    ):
        self.gpm_profile_id = gpm_profile_id
        self.remote_debugging_address = remote_debugging_address
        self._cached_driver_path = driver_path
        self._cached_driver = None
        self._cached_profile_id = None

    def _create_driver_for_address(self, address: str, driver_path: Optional[str] = None) -> Any:
        """Create a Selenium driver attached to remote address using GPMLogin's matching driver_path."""
        options = Options()
        options.add_experimental_option("debuggerAddress", address)

        service = None

        # 1. ƯU TIÊN 1: Lấy trực tiếp driver_path từ JSON trả về khi gọi API start_profile của GPMLogin
        resolved_driver = driver_path or self._cached_driver_path
        if resolved_driver and os.path.exists(resolved_driver):
            logger.info(f"Đang dùng ChromeDriver gốc từ GPMLogin API: {resolved_driver}")
            service = Service(executable_path=resolved_driver)
        else:
            # 2. Dự phòng: Dò version từ cổng remote debugging nếu không có driver_path
            port = None
            if ":" in address:
                port_str = address.split(":")[-1]
                if port_str.isdigit():
                    port = int(port_str)

            if port:
                major_ver = get_chrome_version_from_port(port)
                if major_ver:
                    logger.info(f"Target GPM Chrome version is {major_ver}. Matching ChromeDriver...")
                    options.set_capability("browserVersion", major_ver)
                    matching_exe = get_matching_chromedriver(major_ver)
                    if matching_exe:
                        service = Service(executable_path=matching_exe)

        if service:
            return webdriver.Chrome(service=service, options=options)
        return webdriver.Chrome(options=options)

    def prewarm_profile(self, profile_id: str, gpm_client=None) -> Tuple[bool, str]:
        """
        Pre-launches GPM Profile and pre-navigates to TikTok Studio in advance.
        Eliminates browser startup and navigation latency during video upload.
        """
        if not profile_id or not gpm_client:
            return False, "Thiếu profile_id hoặc gpm_client"

        # Check if already pre-warmed
        if self._cached_driver and self._cached_profile_id == profile_id:
            try:
                _ = self._cached_driver.current_url
                logger.info(f"GPM Profile {profile_id} is already pre-warmed and ready.")
                return True, "Profile đã mở sẵn và sẵn sàng"
            except Exception:
                self._cached_driver = None

        try:
            ok, data, msg = gpm_client.start_profile(profile_id)
            if not ok or not isinstance(data, dict):
                return False, f"Không thể mở GPM profile: {msg}"

            port = data.get("remote_debugging_port")
            driver_path = data.get("driver_path")
            if not port:
                return False, "GPM không trả về cổng remote debugging"

            self.remote_debugging_address = f"127.0.0.1:{port}"
            self.gpm_profile_id = profile_id
            if driver_path:
                self._cached_driver_path = driver_path
                logger.info(f"Đã nhận driver_path từ GPMLogin start_profile API: {driver_path}")

            if not webdriver:
                return True, "GPM đã mở (không có Selenium)"

            # Create driver with matching version using driver_path from GPM API
            driver = self._create_driver_for_address(
                self.remote_debugging_address,
                driver_path=driver_path or self._cached_driver_path
            )
            driver.set_page_load_timeout(25)

            # Scan window handles and navigate visible tab to upload page
            self.ensure_upload_tab(driver)

            self._cached_driver = driver
            self._cached_profile_id = profile_id
            logger.info(f"✨ Đã mở sẵn GPM Profile [{profile_id[:8]}...] trên cổng {port} tại trang Upload.")
            return True, f"Mở sẵn GPM Profile (Cổng {port})"
        except Exception as e:
            logger.error(f"Lỗi khi pre-warm GPM profile {profile_id}: {e}")
            return False, str(e)

    def ensure_upload_tab(self, driver) -> bool:
        """
        Quét toàn bộ window handles trong trình duyệt GPMLogin,
        bỏ qua các handle ngầm của extension (chrome-extension://),
        chuyển tiêu điểm sang cửa sổ hiển thị và mở trang TikTok Studio Upload.
        """
        target_url = TIKTOK_UPLOAD_URL
        handles = getattr(driver, "window_handles", [])
        visible_handle = None

        # 1. Quét tìm tab đã mở sẵn TikTok Upload
        for h in handles:
            try:
                driver.switch_to.window(h)
                curr = (driver.current_url or "").lower()
                if curr.startswith("chrome-extension://") or curr.startswith("devtools://"):
                    continue
                if "tiktokstudio/upload" in curr:
                    logger.info(f"Đã phát hiện tab TikTok Upload đang mở: Handle {h}")
                    return True
                if not visible_handle:
                    visible_handle = h
            except Exception as e:
                logger.debug(f"Lỗi kiểm tra handle {h}: {e}")

        # 2. Nếu có tab trình duyệt thường (ví dụ tiktok.com hoặc newtab), chuyển sang tab đó và mở trang upload
        if visible_handle:
            try:
                driver.switch_to.window(visible_handle)
                logger.info(f"Chuyển sang tab hiển thị (Handle: {visible_handle}), mở trang TikTok Upload...")
                driver.get(target_url)
                return True
            except Exception as e:
                logger.warning(f"Lỗi mở trang upload trên handle {visible_handle}: {e}")

        # 3. Nếu không có tab thường nào (chỉ có extension), tạo một tab mới và mở trang upload
        try:
            logger.info("Tạo tab trình duyệt mới để mở trang TikTok Upload...")
            driver.switch_to.new_window('tab')
            driver.get(target_url)
            return True
        except Exception:
            try:
                driver.execute_script("window.open('');")
                handles_after = getattr(driver, "window_handles", [])
                if handles_after:
                    driver.switch_to.window(handles_after[-1])
                    driver.get(target_url)
                    return True
            except Exception as e:
                logger.error(f"Không thể mở tab TikTok Upload: {e}")
                return False
        return False

    def check_and_click_turn_on(self, driver, timeout: float = 1.5) -> bool:
        """
        Sau khi chọn video, kiểm tra xem có popup hiển thị nút 'Turn on'
        (data-type='primary', data-size='medium', Button__root--size-medium) hay không và nhấn nút.
        Tối ưu timeout xuống 1.5s (poll mỗi 0.2s) để tránh lãng phí thời gian khi không có popup.
        """
        selectors = [
            "button.Button__root--size-medium.Button__root--type-primary",
            "button[data-size='medium'][data-type='primary']",
            "button[data-size='medium'].Button__root--type-primary",
            "//button[contains(@class, 'Button__root') and (contains(., 'Turn on') or contains(., 'Bật'))]",
            "//button[contains(., 'Turn on') or contains(., 'Bật')]",
        ]
        t_end = time.time() + timeout
        while time.time() < t_end:
            for sel in selectors:
                try:
                    if sel.startswith("//"):
                        elements = driver.find_elements(By.XPATH, sel)
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in elements:
                        if el.is_displayed():
                            logger.info(f"Phát hiện nút 'Turn on' ({sel}), đang nhấn...")
                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", el)
                            time.sleep(0.1)
                            try:
                                el.click()
                            except Exception:
                                driver.execute_script("arguments[0].click();", el)
                            logger.info("Đã nhấn nút 'Turn on' thành công!")
                            time.sleep(0.2)
                            return True
                except Exception:
                    pass
            time.sleep(0.2)
        logger.debug("Không thấy nút 'Turn on' (hoặc popup không xuất hiện).")
        return False

    def press_escape(self, driver, times: int = 2) -> None:
        """Nhấn phím ESC (mặc định 2 lần) để tắt các modal/tooltip thừa với độ trễ tối thiểu."""
        logger.debug(f"Nhấn phím ESC {times} lần để đóng các dialog/overlay thừa...")
        for _ in range(times):
            try:
                driver.switch_to.active_element.send_keys(Keys.ESCAPE)
            except Exception:
                try:
                    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                except Exception:
                    pass
            time.sleep(0.1)

    def check_and_click_post_now(self, driver, timeout: float = 2.5) -> bool:
        """
        Sau khi nhấn Post, đợi và nhấn nút xác nhận 'Post now' (TUXButton-primary) nếu có dialog xác nhận xuất hiện.
        Tối ưu timeout xuống 2.5s (poll mỗi 0.25s) thay vì treo 12-15s khi không có popup.
        """
        selectors = [
            "button.TUXButton.TUXButton--primary",
            "button.TUXButton--primary",
            "button.TUXButton",
            "//button[contains(@class, 'TUXButton') and (.//div[contains(@class, 'TUXButton-label') and (contains(text(), 'Post now') or contains(text(), 'Đăng ngay') or contains(text(), 'Post'))] or contains(@class, 'TUXButton--primary'))]",
            "//button[.//div[contains(@class, 'TUXButton-label') and (contains(text(), 'Post now') or contains(text(), 'Đăng ngay'))]]",
            "//button[contains(., 'Post now') or contains(., 'Đăng ngay')]",
        ]
        t_end = time.time() + timeout
        while time.time() < t_end:
            for sel in selectors:
                try:
                    if sel.startswith("//"):
                        elements = driver.find_elements(By.XPATH, sel)
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in elements:
                        if el.is_displayed():
                            logger.info(f"Phát hiện nút xác nhận 'Post now' ({sel}), đang nhấn...")
                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", el)
                            time.sleep(0.1)
                            try:
                                el.click()
                            except Exception:
                                driver.execute_script("arguments[0].click();", el)
                            logger.info("Đã nhấn nút 'Post now' (TUXButton) thành công!")
                            time.sleep(0.3)
                            return True
                except Exception:
                    pass
            time.sleep(0.25)
        logger.debug("Không thấy nút popup 'Post now' (video có thể đã được đăng trực tiếp).")
        return False

    def click_post_button(self, driver, timeout: int = 30) -> bool:
        """
        Cuộn xuống trang TikTok Studio, định vị nút Post theo data-e2e và CSS classes
        (độc lập với ngôn ngữ hiển thị), đợi video tải xong và nhấn nút Đăng.
        Tối ưu: Polling siêu tốc mỗi 0.25s ngay khi nút chuyển sang trạng thái sẵn sàng.
        """
        post_selectors = [
            "button[data-e2e='post_video_button']",
            "button[data-e2e*='post_video']",
            "button[data-e2e*='post']",
            "button.Button__root--type-primary[data-size='large']",
            "button.Button__root.Button__root--type-primary",
            "button.Button__root--type-primary",
        ]

        t_end = time.time() + timeout
        # 1. Cuộn trang xuống đáy ngay lập tức để nút hiển thị trong DOM
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        except Exception:
            pass

        while time.time() < t_end:
            for sel in post_selectors:
                try:
                    buttons = driver.find_elements(By.CSS_SELECTOR, sel)
                    for btn in buttons:
                        if not btn.is_displayed():
                            continue

                        # Kiểm tra trạng thái xử lý/khóa của nút
                        aria_disabled = btn.get_attribute("aria-disabled")
                        data_disabled = btn.get_attribute("data-disabled")
                        data_loading = btn.get_attribute("data-loading")
                        btn_class = btn.get_attribute("class") or ""

                        if aria_disabled == "true" or data_disabled == "true" or data_loading == "true" or "disabled" in btn_class.lower():
                            continue

                        # Cuộn nút vào giữa màn hình và click ngay lập tức
                        driver.execute_script(
                            "arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});",
                            btn
                        )
                        time.sleep(0.1)

                        # Nhấn nút (hỗ trợ cả click thông thường và JS click dự phòng)
                        try:
                            btn.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", btn)

                        logger.info(f"Đã cuộn xuống và nhấn nút POST thành công (Selector: {sel})!")
                        return True
                except Exception as e:
                    logger.debug(f"Selector {sel} lookup error: {e}")

            time.sleep(0.25)

        logger.warning("Hết thời gian chờ nút Post TikTok Studio (hoặc nút chưa sẵn sàng).")
        return False

    def reset_to_upload_page(self, driver) -> bool:
        """
        Sau khi post xong 1 video, đưa trình duyệt quay lại trang upload TikTok Studio
        (https://www.tiktok.com/tiktokstudio/upload?from=webapp&tab=video)
        để sẵn sàng 0s cho lần đăng video tiếp theo.
        Tối ưu: Polling chủ động tìm nút 'Upload another' ngay lập tức thay vì sleep cứng 2.5s.
        """
        logger.info("🔄 Đang chuyển trình duyệt quay lại trang Upload TikTok Studio để tối ưu thời gian cho lần sau...")
        try:
            # 1. Thử tìm ngay nút 'Upload another video' / 'Đăng video khác' trên modal thành công
            upload_another_selectors = [
                "button[data-e2e*='upload_another']",
                "button[data-e2e*='post_another']",
                "//button[contains(., 'Upload another') or contains(., 'Đăng video khác') or contains(., 'Upload more')]",
                "//div[contains(text(), 'Upload another') or contains(text(), 'Đăng video khác')]"
            ]
            t_wait = time.time() + 2.0
            while time.time() < t_wait:
                for sel in upload_another_selectors:
                    try:
                        if sel.startswith("//"):
                            btns = driver.find_elements(By.XPATH, sel)
                        else:
                            btns = driver.find_elements(By.CSS_SELECTOR, sel)
                        for b in btns:
                            if b.is_displayed():
                                b.click()
                                logger.info("Đã bấm nút 'Upload another video' trên popup thành công.")
                                time.sleep(0.2)
                                return True
                    except Exception:
                        pass
                time.sleep(0.2)

            # 2. Điều hướng trực tiếp về trang upload
            driver.get(TIKTOK_UPLOAD_URL)
            logger.info("Đã chuyển tab trình duyệt quay lại trang Upload TikTok Studio sẵn sàng!")
            return True
        except Exception as e:
            logger.debug(f"Lỗi khi quay lại trang upload: {e}")
            return False

    def upload_video(
        self,
        video_path: str,
        caption: str = "",
        auto_post: bool = False,
        profile_id: str = "",
        gpm_client=None
    ) -> Tuple[bool, float, str]:
        """
        Uploads video to TikTok Studio via pre-warmed or active GPMLogin CDP session.
        Returns (success: bool, elapsed_seconds: float, message: str).
        """
        t_start = time.perf_counter()

        if not os.path.exists(video_path):
            logger.error(f"Upload file not found: {video_path}")
            return False, 0.0, "File video không tồn tại"

        if not webdriver:
            logger.warning("Selenium not installed; upload simulated.")
            return True, 0.5, "Selenium không có sẵn (mô phỏng thành công)"

        # 1. Use pre-warmed driver or connect
        driver = None
        if self._cached_driver and self._cached_profile_id == profile_id:
            try:
                _ = self._cached_driver.current_url
                driver = self._cached_driver
                logger.info("Sử dụng GPM browser đã mở sẵn (0s độ trễ mở trình duyệt)!")
            except Exception:
                self._cached_driver = None

        if not driver:
            driver_path = None
            if gpm_client and profile_id:
                ok, data, msg = gpm_client.start_profile(profile_id)
                if ok and isinstance(data, dict):
                    port = data.get("remote_debugging_port")
                    driver_path = data.get("driver_path")
                    if port:
                        self.remote_debugging_address = f"127.0.0.1:{port}"
                    if driver_path:
                        self._cached_driver_path = driver_path
                        logger.info(f"Đã nhận driver_path từ GPMLogin start_profile API: {driver_path}")

            try:
                driver = self._create_driver_for_address(
                    self.remote_debugging_address,
                    driver_path=driver_path or self._cached_driver_path
                )
                driver.set_page_load_timeout(30)
                self._cached_driver = driver
                self._cached_profile_id = profile_id
            except Exception as e:
                return False, time.perf_counter() - t_start, f"Lỗi kết nối CDP: {e}"

        try:
            # Ensure we are on the visible upload tab
            self.ensure_upload_tab(driver)

            # Tối ưu hóa 3: Chặn các network trackers và script analytics nặng nề của TikTok qua CDP
            try:
                driver.execute_cdp_cmd("Network.setBlockedURLs", {
                    "urls": [
                        "*analytics*",
                        "*byteoversea.com/tiktok/falcon/*",
                        "*log.byteoversea.com*",
                        "*mon.musical.ly*"
                    ]
                })
                driver.execute_cdp_cmd("Network.enable", {})
            except Exception:
                pass

            # 2. Locate file input element
            file_input = None
            try:
                file_input = WebDriverWait(driver, 6).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
                )
            except Exception:
                # Search within iframes if present
                for frame in driver.find_elements(By.TAG_NAME, "iframe"):
                    try:
                        driver.switch_to.frame(frame)
                        file_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
                        if file_input:
                            break
                    except Exception:
                        driver.switch_to.default_content()

            if not file_input:
                return False, time.perf_counter() - t_start, "Không tìm thấy nút upload video trên TikTok Studio"

            abs_path = os.path.abspath(video_path)
            logger.info(f"Đang truyền đường dẫn file vào TikTok Studio: {abs_path}")
            file_input.send_keys(abs_path)

            # Đợi ngắn 0.4s để TikTok React state nhận file
            time.sleep(0.4)

            # 1. Sau khi chọn video: Kiểm tra nhanh nút 'Turn on' (nếu có popup hỏi bản quyền/âm thanh/phụ đề)
            self.check_and_click_turn_on(driver, timeout=1.5)

            # 2. Nhấn phím ESC để tắt triệt để các modal/tooltip thừa
            self.press_escape(driver, times=2)

            # 3. Fill caption if provided (điền ngay trong lúc TikTok xử lý video ở background)
            if caption:
                try:
                    caption_boxes = driver.find_elements(By.CSS_SELECTOR, "div[contenteditable='true'], .public-DraftEditor-content, textarea")
                    if caption_boxes:
                        box = caption_boxes[0]
                        box.click()
                        time.sleep(0.1)
                        clean_caption = caption.strip()
                        if "#" not in clean_caption:
                            clean_caption += " #fyp #trending #viral"
                        box.send_keys(Keys.CONTROL + "a")
                        box.send_keys(Keys.BACKSPACE)
                        box.send_keys(clean_caption)
                except Exception as e:
                    logger.warning(f"Lỗi điền caption: {e}")

            # 4. Auto post
            if auto_post:
                logger.info("Chế độ Tự động đăng BẬT: Đang cuộn xuống tìm nút Post (data-e2e='post_video_button')...")
                post_ok = self.click_post_button(driver, timeout=30)
                if post_ok:
                    logger.info("Đã bấm nút ĐĂNG (Post) video lên TikTok Studio thành công.")
                    # 5. Sau đó kiểm tra nhanh nút xác nhận 'Post now' (TUXButton--primary) nếu có
                    self.check_and_click_post_now(driver, timeout=2.5)

                    # 6. Quay trở lại trang upload ngay để tối ưu thời gian cho video kế tiếp (0s trễ)
                    self.reset_to_upload_page(driver)
                else:
                    logger.warning("Không thể tự động bấm nút Đăng (có thể cần xác nhận thủ công hoặc video chưa xử lý xong).")

            elapsed = time.perf_counter() - t_start
            logger.info(f"Tải video lên TikTok Studio thành công trong {elapsed:.2f}s!")
            return True, elapsed, "Tải lên TikTok thành công"

        except Exception as e:
            elapsed = time.perf_counter() - t_start
            logger.error(f"Lỗi upload TikTok: {e}")
            return False, elapsed, str(e)

    def close_browser(self, gpm_client=None) -> bool:
        """
        Gracefully closes Selenium session and shuts down the running GPM Profile
        to save RAM and CPU when outside active scheduled hours.
        """
        closed = False
        if self._cached_driver:
            try:
                self._cached_driver.quit()
                closed = True
            except Exception as e:
                logger.debug(f"Error quitting Selenium driver: {e}")
            finally:
                self._cached_driver = None

        if self._cached_profile_id and gpm_client:
            try:
                gpm_client.stop_profile(self._cached_profile_id)
                closed = True
            except Exception as e:
                logger.debug(f"Error stopping GPM profile via API: {e}")
            finally:
                self._cached_profile_id = None

        return closed

    def start_and_upload(
        self,
        profile_id: str,
        video_path: str,
        caption: str = "",
        auto_post: bool = False,
        gpm_client=None,
        close_after: bool = False
    ) -> bool:
        """Backward compatible wrapper."""
        ok, elapsed, msg = self.upload_video(
            video_path=video_path,
            caption=caption,
            auto_post=auto_post,
            profile_id=profile_id,
            gpm_client=gpm_client
        )
        return ok
