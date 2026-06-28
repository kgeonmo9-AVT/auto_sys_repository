import os
import json
import smtplib
import hashlib
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
from pathlib import Path

# ── 설정 ──────────────────────────────────────────────────
EMAIL_USER = os.environ.get("EMAIL_USER", "")
EMAIL_PASS = os.environ.get("EMAIL_PASS", "")
EMAIL_TO   = os.environ.get("EMAIL_TO", EMAIL_USER)   # 수신자 (기본: 발신자 본인)
SEEN_FILE  = Path("seen_jobs.json")

AIRLINES = [
    # ── FSC ──
    {
        "name": "대한항공",
        "url": "https://koreanair.recruiter.co.kr/career/home",
        "api": "https://koreanair.recruiter.co.kr/app/jobnotice/list?careerType=&keywordType=all&keyword=&pageSize=20&pageNo=1",
        "type": "recruiter",
    },
    {
        "name": "아시아나항공",
        "url": "https://flyasiana.recruiter.co.kr/career/home",
        "api": "https://flyasiana.recruiter.co.kr/app/jobnotice/list?careerType=&keywordType=all&keyword=&pageSize=20&pageNo=1",
        "type": "recruiter",
    },
    # ── LCC ──
    {
        "name": "제주항공",
        "url": "https://jejuair.recruiter.co.kr/career/home",
        "api": "https://jejuair.recruiter.co.kr/app/jobnotice/list?careerType=&keywordType=all&keyword=&pageSize=20&pageNo=1",
        "type": "recruiter",
    },
    {
        "name": "진에어",
        "url": "https://jinair.recruiter.co.kr/app/jobnotice/list",
        "api": "https://jinair.recruiter.co.kr/app/jobnotice/list?careerType=&keywordType=all&keyword=&pageSize=20&pageNo=1",
        "type": "recruiter",
    },
    {
        "name": "티웨이항공",
        "url": "https://twayair.recruiter.co.kr/career/home",
        "api": "https://twayair.recruiter.co.kr/app/jobnotice/list?careerType=&keywordType=all&keyword=&pageSize=20&pageNo=1",
        "type": "recruiter",
    },
    {
        "name": "에어부산",
        "url": "https://airbusan.recruiter.co.kr/app/jobnotice/list",
        "api": "https://airbusan.recruiter.co.kr/app/jobnotice/list?careerType=&keywordType=all&keyword=&pageSize=20&pageNo=1",
        "type": "recruiter",
    },
    {
        "name": "에어서울",
        "url": "https://recruit.flyairseoul.com/",
        "type": "airseoul",
    },
    {
        "name": "이스타항공",
        "url": "https://recruit.eastarjet.com/announcement",
        "type": "eastar",
    },
    {
        "name": "에어프레미아",
        "url": "https://airpremia.career.greetinghr.com/ko/home",
        "type": "greetinghr",
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://www.google.com/",
}


# ── 크롤러 ────────────────────────────────────────────────

def fetch_recruiter(airline: dict) -> list[dict]:
    """recruiter.co.kr 공통 API"""
    try:
        r = requests.get(airline["api"], headers=HEADERS, timeout=10)
        data = r.json()
        jobs = []
        items = data.get("result", data.get("data", {}).get("list", []))
        if isinstance(data, dict):
            for key in ("result", "list", "jobList", "data"):
                val = data.get(key)
                if isinstance(val, list):
                    items = val
                    break
                if isinstance(val, dict):
                    for subkey in ("list", "jobList"):
                        sub = val.get(subkey)
                        if isinstance(sub, list):
                            items = sub
                            break
        for item in items:
            title = item.get("noticeTitle") or item.get("title") or item.get("jobTitle", "")
            job_id = str(item.get("noticeNo") or item.get("jobNo") or item.get("id", ""))
            deadline = item.get("endDate") or item.get("deadlineDate") or item.get("closeDate", "")
            link = f"{airline['url'].rstrip('/')}/../app/jobnotice/view?noticeNo={job_id}" if job_id else airline["url"]
            if title:
                jobs.append({"title": title, "id": job_id, "deadline": deadline, "link": airline["url"]})
        return jobs
    except Exception as e:
        print(f"[{airline['name']}] recruiter API 오류: {e}")
        return fetch_html_fallback(airline)


def fetch_html_fallback(airline: dict) -> list[dict]:
    """HTML 파싱 폴백"""
    try:
        r = requests.get(airline["url"], headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []
        for tag in soup.select("a[href]"):
            text = tag.get_text(strip=True)
            href = tag.get("href", "")
            if len(text) > 5 and any(k in text for k in ["채용", "모집", "공고", "지원"]):
                jobs.append({"title": text[:80], "id": hashlib.md5(text.encode()).hexdigest()[:8],
                             "deadline": "", "link": airline["url"]})
        return jobs[:10]
    except Exception as e:
        print(f"[{airline['name']}] HTML 폴백 오류: {e}")
        return []


def fetch_airseoul(airline: dict) -> list[dict]:
    try:
        r = requests.get(airline["url"], headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []
        for row in soup.select("table tr, .recruit-list li, .job-item, article"):
            text = row.get_text(" ", strip=True)
            if len(text) > 10 and any(k in text for k in ["모집", "채용", "공고"]):
                jobs.append({"title": text[:80], "id": hashlib.md5(text.encode()).hexdigest()[:8],
                             "deadline": "", "link": airline["url"]})
        return jobs[:10]
    except Exception as e:
        print(f"[에어서울] 오류: {e}")
        return []


def fetch_eastar(airline: dict) -> list[dict]:
    try:
        r = requests.get(airline["url"], headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []
        for tag in soup.select(".announcement-item, .recruit-item, table tr, li"):
            text = tag.get_text(" ", strip=True)
            if len(text) > 10 and any(k in text for k in ["모집", "채용", "공고", "지원"]):
                jobs.append({"title": text[:80], "id": hashlib.md5(text.encode()).hexdigest()[:8],
                             "deadline": "", "link": airline["url"]})
        return jobs[:10]
    except Exception as e:
        print(f"[이스타항공] 오류: {e}")
        return []


def fetch_greetinghr(airline: dict) -> list[dict]:
    try:
        api = "https://airpremia.career.greetinghr.com/api/v1/job-openings?status=open&page=1&per_page=20"
        r = requests.get(api, headers={**HEADERS, "Accept": "application/json"}, timeout=10)
        data = r.json()
        jobs = []
        items = data if isinstance(data, list) else data.get("data", data.get("items", []))
        for item in items:
            title = item.get("title") or item.get("name", "")
            job_id = str(item.get("id", hashlib.md5(title.encode()).hexdigest()[:8]))
            deadline = item.get("deadline") or item.get("end_date", "")
            if title:
                jobs.append({"title": title, "id": job_id, "deadline": deadline, "link": airline["url"]})
        return jobs
    except Exception as e:
        print(f"[에어프레미아] greetinghr API 오류: {e}")
        return fetch_html_fallback(airline)


FETCHERS = {
    "recruiter": fetch_recruiter,
    "airseoul":  fetch_airseoul,
    "eastar":    fetch_eastar,
    "greetinghr": fetch_greetinghr,
}


def crawl_all() -> dict[str, list[dict]]:
    results = {}
    for airline in AIRLINES:
        fetcher = FETCHERS.get(airline["type"], fetch_html_fallback)
        jobs = fetcher(airline)
        print(f"[{airline['name']}] {len(jobs)}건 수집")
        results[airline["name"]] = jobs
    return results


# ── 신규 공고 필터 ────────────────────────────────────────

def load_seen() -> set:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen: set):
    SEEN_FILE.write_text(json.dumps(sorted(seen)))


def filter_new(all_jobs: dict, seen: set) -> dict[str, list[dict]]:
    new = {}
    for airline, jobs in all_jobs.items():
        fresh = []
        for job in jobs:
            key = f"{airline}::{job['id']}::{job['title']}"
            if key not in seen:
                fresh.append(job)
        if fresh:
            new[airline] = fresh
    return new


# ── 메일 발송 ─────────────────────────────────────────────

def build_html(new_jobs: dict) -> str:
    today = datetime.now().strftime("%Y년 %m월 %d일")
    has_jobs = bool(new_jobs)

    if has_jobs:
        rows = ""
        for airline, jobs in new_jobs.items():
            for job in jobs:
                deadline_text = f"~{job['deadline']}" if job['deadline'] else "상시"
                rows += f"""
        <tr>
          <td style="padding:10px 14px;border-bottom:1px solid #f0f0f0;font-weight:600;color:#1a1a2e;white-space:nowrap">{airline}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #f0f0f0">
            <a href="{job['link']}" style="color:#2563eb;text-decoration:none">{job['title']}</a>
          </td>
          <td style="padding:10px 14px;border-bottom:1px solid #f0f0f0;color:#6b7280;white-space:nowrap;font-size:13px">{deadline_text}</td>
        </tr>"""
        total = sum(len(j) for j in new_jobs.values())
        header_text = f"신규 채용공고 {total}건"
        body = f"""
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <thead>
        <tr style="background:#f1f5f9">
          <th style="padding:10px 14px;text-align:left;color:#374151;font-size:12px;text-transform:uppercase;letter-spacing:.5px">항공사</th>
          <th style="padding:10px 14px;text-align:left;color:#374151;font-size:12px;text-transform:uppercase;letter-spacing:.5px">공고명</th>
          <th style="padding:10px 14px;text-align:left;color:#374151;font-size:12px;text-transform:uppercase;letter-spacing:.5px">마감일</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""
    else:
        header_text = "신규 채용공고 없음"
        body = """
    <p style="text-align:center;color:#6b7280;padding:32px 0;font-size:15px">
      오늘은 새로운 채용공고가 없습니다.<br>
      <span style="font-size:13px;color:#9ca3af">시스템은 정상 작동 중입니다 ✅</span>
    </p>"""

    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;font-family:'Apple SD Gothic Neo',sans-serif;background:#f8fafc">
<div style="max-width:640px;margin:32px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08)">
  <div style="background:linear-gradient(135deg,#1e3a8a,#2563eb);padding:28px 32px">
    <p style="margin:0;color:rgba(255,255,255,.7);font-size:13px">✈️ 항공사 채용 알림</p>
    <h1 style="margin:6px 0 0;color:#fff;font-size:22px">{header_text}</h1>
    <p style="margin:4px 0 0;color:rgba(255,255,255,.6);font-size:13px">{today} 기준</p>
  </div>
  <div style="padding:24px 32px">{body}</div>
  <div style="padding:16px 32px 24px;border-top:1px solid #f0f0f0">
    <p style="margin:0;color:#9ca3af;font-size:12px;text-align:center">이 메일은 GitHub Actions로 자동 발송되었습니다</p>
  </div>
</div>
</body></html>"""


def send_email(new_jobs: dict):
    if not EMAIL_USER or not EMAIL_PASS:
        print("⚠️  EMAIL_USER / EMAIL_PASS 환경변수가 없습니다.")
        return

    has_jobs = bool(new_jobs)
    total = sum(len(j) for j in new_jobs.values()) if has_jobs else 0
    subject = (f"✈️ 항공사 신규 채용공고 {total}건 ({datetime.now().strftime('%m/%d')})"
               if has_jobs else
               f"✈️ 항공사 채용공고 — 신규 없음 ({datetime.now().strftime('%m/%d')})")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_USER
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText(build_html(new_jobs), "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(EMAIL_USER, EMAIL_PASS)
        s.sendmail(EMAIL_USER, EMAIL_TO, msg.as_string())
    print(f"✅ 메일 발송 완료 → {EMAIL_TO}")


# ── 메인 ──────────────────────────────────────────────────

def main():
    print(f"\n{'='*50}")
    print(f"항공사 채용공고 크롤링 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")

    seen     = load_seen()
    all_jobs = crawl_all()
    new_jobs = filter_new(all_jobs, seen)

    if new_jobs:
        print(f"\n🆕 신규 공고 발견: {sum(len(j) for j in new_jobs.values())}건")
        for airline, jobs in new_jobs.items():
            for job in jobs:
                seen.add(f"{airline}::{job['id']}::{job['title']}")
        save_seen(seen)
    else:
        print("\n신규 공고 없음")

    send_email(new_jobs)
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
