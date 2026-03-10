"""
Flex Google SSO 최초 로그인 및 세션 저장 스크립트.

사용법:
    python src/auth_setup.py

실행하면 브라우저가 열립니다. Google 계정으로 Flex에 로그인한 뒤
터미널에서 Enter를 누르면 세션이 auth/session.json에 저장됩니다.

이후 이 파일을 클라우드 서버에 전송하면 자동 크롤링이 세션을 재사용합니다.
"""

import asyncio
import os
import sys

AUTH_SESSION_PATH = os.path.join(os.path.dirname(__file__), "..", "auth", "session.json")
FLEX_URL = "https://flex.team/time-tracking/my-work-record/members?departments="


async def setup_auth() -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[오류] playwright가 설치되지 않았습니다.")
        print("  pip install playwright && playwright install chromium")
        sys.exit(1)

    os.makedirs(os.path.dirname(AUTH_SESSION_PATH), exist_ok=True)

    async with async_playwright() as p:
        print("브라우저를 실행합니다...")
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        print(f"Flex 페이지로 이동합니다: {FLEX_URL}")
        await page.goto(FLEX_URL)

        print()
        print("=" * 60)
        print("브라우저에서 Google 계정으로 Flex에 로그인해주세요.")
        print("로그인 완료 후 이 터미널에서 Enter를 누르세요.")
        print("=" * 60)
        input()

        # 로그인 성공 여부 확인
        current_url = page.url
        if "login" in current_url or "accounts.google" in current_url:
            print("[경고] 로그인 페이지가 아직 표시됩니다. 로그인을 완료했는지 확인하세요.")
            input("로그인 완료 후 다시 Enter를 누르세요...")

        # 세션 저장
        await context.storage_state(path=AUTH_SESSION_PATH)
        await browser.close()

        print()
        print(f"[완료] 세션이 저장되었습니다: {AUTH_SESSION_PATH}")
        print()
        print("다음 단계:")
        print(f"  서버에 전송: scp {AUTH_SESSION_PATH} user@server:/app/auth/session.json")
        print("  서버에서 실행: docker-compose up -d")


if __name__ == "__main__":
    asyncio.run(setup_auth())
