#!/usr/bin/env python3
"""
항공정비사 채용공고 자동 알림 스크립트
- 매일 오전 8시 cron으로 실행
- 각 항공사 채용 페이지 크롤링
- 항공정비사 관련 공고 발견 시 Gmail 발송
"""

import smtplib
import json
import os
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────
# ✅ 설정 (여기만 수정하세요)
# ─────────────────────────────────────────
GMAIL_ADDRESS = "kkm981119@gmail.com"         # 발신 Gmail 주소
GMAIL_APP_PASSWORD = "tjlt qpzf tozu gbdn"   # Gmail 앱 비밀번호 (16자리)
RECIPIENT_EMAIL = "rjsah8671@naver.com"      # 수신 이메일 주소

# 이전에 발견한 공고 ID 저장 파일 (중복 알림 방지)
SEEN_JOBS_FILE = os.path.join(os.path.dirname(__file__), "seen_jobs.json")

# 검색 키워드
KEYWORDS = ["정비", "항공정비", "기술", "MRO", "엔지니어", "mechanic", "maintenance"]
# ─────────────────────────────────────────


AIRLINES = [
    {
        "name": "대한항공",
        "type": "recruiter",
        "api_url": "https://koreanair.recruiter.co.kr/api/jobnotice/list",
        "base_url": "https://koreanair.recruiter.co.kr/app/jobnotice/view?id=",
    },
    {
        "name": "아시아나항공",
        "type": "recruiter",
        "api_url": "https://flyasiana.recruiter.co.kr/api/jobnotice/list",
        "base_url": "https://flyasiana.recruiter.co.kr/app/jobnotice/view?id=",
    },
    {
        "name": "제주항공",
        "type": "recruiter",
        "api_url": "https://jejuair.recruiter.co.kr/api/jobnotice/list",
        "base_url": "https://jejuair.recruiter.co.kr/app/jobnotice/view?id=",
    },
    {
        "name": "진에어",
        "type": "recruiter_list",
        "list_url": "https://jinair.recruiter.co.kr/app/jobnotice/list",
        "api_url": "https://jinair.recruiter.co.kr/api/jobnotice/list",
        "base_url": "https://jinair.recruiter.co.kr/app/jobnotice/view?id=",
    },
    {
        "name": "티웨이항공",
        "type": "recruiter",
        "api_url": "https://twayair.recruiter.co.kr/api/jobnotice/list",
        "base_url": "https://twayair.recruiter.co.kr/app/jobnotice/view?id=",
    },
    {
        "name": "에어부산",
        "type": "recruiter_list",
        "list_url": "https://airbusan.recruiter.co.kr/app/jobnotice/list",
        "api_url": "https://airbusan.recruiter.co.kr/api/jobnotice/list",
        "base_url": "https://airbusan.recruiter.co.kr/app/jobnotice/view?id=",
    },
    {
        "name": "에어서울",
        "type": "airseoul",
        "list_url": "https://recruit.flyairseoul.com/",
    },
    {
        "name": "이스타항공",
        "type": "eastar",
        "list_url": "https://recruit.eastarjet.com/announcement",
    },
    {
        "name": "에어프레미아",
        "type": "greetinghr",
        "list_url": "https://airpremia.career.greetinghr.com/ko/home",
        "api_url": "https://api.greetinghr.com/companies/airpremia/postings",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ─── 유틸 ────────────────────────────────

def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_seen_jobs(data):
    with open(SEEN_JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_relevant(title: str) -> bool:
    title_lower = title.lower()
    return any(kw.lower() in title_lower for kw in KEYWORDS)


# ─── 크롤러 ──────────────────────────────

def fetch_recruiter(airline: dict) -> list:
    """recruiter.co.kr 공통 API"""
    jobs = []
    try:
        params = {"page": 1, "size": 50}
        res = requests.get(airline["api_url"], params=params, headers=HEADERS, timeout=10)
        data = res.json()
        items = data.get("data", {}).get("list", []) or data.get("list", [])
        for item in items:
            title = item.get("title", "") or item.get("noticeName", "")
            job_id = str(item.get("id", "") or item.get("noticeId", ""))
            if title and job_id and is_relevant(title):
                jobs.append({
                    "airline": airline["name"],
                    "title": title,
                    "url": airline["base_url"] + job_id,
                    "deadline": item.get("endDate", "미정"),
                })
    except Exception as e:
        print(f"[{airline['name']}] recruiter API 오류: {e}")
    return jobs


def fetch_eastar(airline: dict) -> list:
    """이스타항공 - HTML 파싱"""
    jobs = []
    try:
        res = requests.get(airline["list_url"], headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        # 공고 리스트 파싱 (사이트 구조에 따라 조정 필요)
        for row in soup.select("table tbody tr, .job-item, .recruit-item"):
            title_el = row.select_one("td, .title, .subject")
            if title_el:
                title = title_el.get_text(strip=True)
                if is_relevant(title):
                    link_el = row.select_one("a")
                    url = link_el["href"] if link_el else airline["list_url"]
                    if url.startswith("/"):
                        url = "https://recruit.eastarjet.com" + url
                    jobs.append({
                        "airline": airline["name"],
                        "title": title,
                        "url": url,
                        "deadline": "확인 필요",
                    })
    except Exception as e:
        print(f"[{airline['name']}] 크롤링 오류: {e}")
    return jobs


def fetch_airseoul(airline: dict) -> list:
    """에어서울 - HTML 파싱"""
    jobs = []
    try:
        res = requests.get(airline["list_url"], headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        for row in soup.select("tr, .job-list-item, .recruit-list li"):
            title_el = row.select_one("td, .tit, .title")
            if title_el:
                title = title_el.get_text(strip=True)
                if is_relevant(title):
                    link_el = row.select_one("a")
                    url = link_el["href"] if link_el else airline["list_url"]
                    if url.startswith("/"):
                        url = "https://recruit.flyairseoul.com" + url
                    jobs.append({
                        "airline": airline["name"],
                        "title": title,
                        "url": url,
                        "deadline": "확인 필요",
                    })
    except Exception as e:
        print(f"[{airline['name']}] 크롤링 오류: {e}")
    return jobs


def fetch_greetinghr(airline: dict) -> list:
    """에어프레미아 - greetinghr API"""
    jobs = []
    try:
        res = requests.get(airline["api_url"], headers=HEADERS, timeout=10)
        items = res.json() if isinstance(res.json(), list) else res.json().get("data", [])
        for item in items:
            title = item.get("title", "") or item.get("name", "")
            if is_relevant(title):
                jobs.append({
                    "airline": airline["name"],
                    "title": title,
                    "url": item.get("url", airline["list_url"]),
                    "deadline": item.get("deadline", "미정"),
                })
    except Exception as e:
        print(f"[{airline['name']}] greetinghr API 오류: {e}")
    return jobs


def crawl_all() -> list:
    all_jobs = []
    for airline in AIRLINES:
        t = airline["type"]
        if t in ("recruiter", "recruiter_list"):
            all_jobs.extend(fetch_recruiter(airline))
        elif t == "eastar":
            all_jobs.extend(fetch_eastar(airline))
        elif t == "airseoul":
            all_jobs.extend(fetch_airseoul(airline))
        elif t == "greetinghr":
            all_jobs.extend(fetch_greetinghr(airline))
        time.sleep(1)  # 서버 부하 방지
    return all_jobs


# ─── 이메일 발송 ──────────────────────────

def build_email_html(jobs: list) -> str:
    rows = ""
    for j in jobs:
        rows += f"""
        <tr>
          <td style="padding:8px;border:1px solid #ddd;font-weight:bold;">{j['airline']}</td>
          <td style="padding:8px;border:1px solid #ddd;">
            <a href="{j['url']}" style="color:#0066cc;">{j['title']}</a>
          </td>
          <td style="padding:8px;border:1px solid #ddd;color:#555;">{j['deadline']}</td>
        </tr>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;">
      <h2 style="color:#003580;">✈️ 항공정비사 채용공고 알림</h2>
      <p>📅 기준일시: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}</p>
      <p>총 <strong>{len(jobs)}건</strong>의 항공정비사 관련 공고가 발견되었습니다.</p>
      <table style="border-collapse:collapse;width:100%;margin-top:16px;">
        <thead>
          <tr style="background:#003580;color:white;">
            <th style="padding:10px;text-align:left;width:15%;">항공사</th>
            <th style="padding:10px;text-align:left;">공고명</th>
            <th style="padding:10px;text-align:left;width:15%;">마감일</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <p style="margin-top:20px;font-size:12px;color:#999;">
        본 메일은 자동 발송된 채용 알림입니다.
      </p>
    </body></html>
    """


def send_email(jobs: list):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"✈️ 항공정비사 채용공고 {len(jobs)}건 - {datetime.now().strftime('%Y.%m.%d')}"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(build_email_html(jobs), "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, RECIPIENT_EMAIL, msg.as_string())
    print(f"✅ 이메일 발송 완료: {len(jobs)}건")


# ─── 메인 ────────────────────────────────

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 채용공고 크롤링 시작...")
    seen = load_seen_jobs()
    all_jobs = crawl_all()

    # 신규 공고 필터링 (중복 제거)
    new_jobs = []
    for job in all_jobs:
        key = f"{job['airline']}_{job['title']}"
        if key not in seen:
            new_jobs.append(job)
            seen[key] = datetime.now().strftime("%Y-%m-%d")

    print(f"신규 공고: {len(new_jobs)}건 / 전체 관련 공고: {len(all_jobs)}건")

    if new_jobs:
        send_email(new_jobs)
        save_seen_jobs(seen)
    else:
        print("새로운 항공정비사 공고 없음 — 메일 미발송")


if __name__ == "__main__":
    main()
