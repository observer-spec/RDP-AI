"""Browser + desktop handlers (extracted from server.py)."""
import base64
import os
import subprocess
from typing import Any, Dict

from .browser import get_browser_page
from .config import WORKSPACE_DIR, log_history


async def handle_take_screenshot(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", "desktop")
    full_page = args.get("full_page", False)

    if target == "browser":
        page, err = await get_browser_page()
        if err:
            return {"error": err}
        try:
            screenshot_bytes = await page.screenshot(type="jpeg", quality=80, full_page=full_page)
            b64_img = base64.b64encode(screenshot_bytes).decode("utf-8")
            log_history("TAKE_SCREENSHOT: Browser captured")
            return {
                "success": True,
                "target": "browser",
                "current_url": page.url,
                "image_format": "jpeg",
                "screenshot_base64": b64_img,
            }
        except Exception as e:
            return {"error": f"Browser screenshot failed: {str(e)}"}
    else:
        try:
            out_path = os.path.join(WORKSPACE_DIR, "desktop_screenshot.jpg")
            subprocess.run(
                f"DISPLAY=:99 scrot -q 80 {out_path} 2>/dev/null || DISPLAY=:99 import -window root {out_path} 2>/dev/null",
                shell=True,
            )
            if os.path.exists(out_path):
                with open(out_path, "rb") as f:
                    b64_img = base64.b64encode(f.read()).decode("utf-8")
                return {
                    "success": True,
                    "target": "desktop",
                    "image_format": "jpeg",
                    "screenshot_base64": b64_img,
                }
            else:
                return {"error": "No virtual X11 display active or scrot tool missing."}
        except Exception as e:
            return {"error": str(e)}


async def handle_browser_open(args: Dict[str, Any]) -> Dict[str, Any]:
    url = args.get("url", "")
    wait_until = args.get("wait_until", "domcontentloaded")
    capture_screenshot = args.get("capture_screenshot", True)

    page, err = await get_browser_page()
    if err:
        return {"error": err}

    try:
        await page.goto(url, wait_until=wait_until, timeout=30000)
        title = await page.title()
        text_content = await page.evaluate("() => document.body ? document.body.innerText.slice(0, 5000) : ''")

        res: Dict[str, Any] = {
            "title": title,
            "url": page.url,
            "text_preview": text_content,
            "status": "loaded",
        }

        if capture_screenshot:
            screenshot_bytes = await page.screenshot(type="jpeg", quality=75)
            res["screenshot_base64"] = base64.b64encode(screenshot_bytes).decode("utf-8")

        log_history(f"BROWSER_GOTO: {url} (Title: {title[:40]})")
        return res
    except Exception as e:
        return {"error": f"Browser navigation failed: {str(e)}"}


async def handle_browser_interact(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action")
    selector = args.get("selector")
    text = args.get("text", "")
    script = args.get("script", "")

    page, err = await get_browser_page()
    if err:
        return {"error": err}

    try:
        if action == "click":
            await page.click(selector, timeout=10000)
            return {"success": True, "action": "click", "selector": selector}
        elif action == "type":
            await page.fill(selector, text, timeout=10000)
            return {"success": True, "action": "type", "selector": selector}
        elif action == "evaluate_js":
            result = await page.evaluate(script)
            return {"success": True, "action": "evaluate_js", "result": result}
        elif action == "screenshot":
            screenshot_bytes = await page.screenshot(type="jpeg", quality=75)
            return {
                "success": True,
                "screenshot_base64": base64.b64encode(screenshot_bytes).decode("utf-8"),
            }
        elif action == "get_html":
            html = await page.content()
            return {"html_length": len(html), "html_preview": html[:4000]}
        elif action == "scroll":
            await page.evaluate("window.scrollBy(0, 600)")
            return {"success": True, "action": "scroll"}
        else:
            return {"error": f"Unknown browser action: {action}"}
    except Exception as e:
        return {"error": str(e)}
