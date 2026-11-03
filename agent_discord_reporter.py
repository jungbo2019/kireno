#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Antigravity AI Agent - Discord Real-time Task Reporter
Reports AI Developer actions, progress, deployments, and verification directly to Discord channel.
Target Server: 정보맨님의 서버 (#일반) - https://discord.gg/Kym2WKGDX
"""

import os
import sys
import json
import urllib.request
import datetime

# Configure UTF-8 for Windows console
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'discord_agent_config.json')

def get_agent_webhook_url():
    # 1. Check environment variable
    url = os.environ.get('DISCORD_AGENT_WEBHOOK_URL')
    if url:
        return url.strip()

    # 2. Check config file
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                if cfg.get('webhook_url'):
                    return cfg['webhook_url'].strip()
        except Exception:
            pass

    return None

def report_to_discord(title, details, status="COMPLETE", public_url="https://fiction-america-enrollment-metal.trycloudflare.com"):
    """
    Sends an agent work progress report to Discord #일반 channel.
    """
    webhook_url = get_agent_webhook_url()
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    color = 0x00FF88 if status == "COMPLETE" else (0xFEE75C if status == "IN_PROGRESS" else 0xED4245)

    embed = {
        "title": f"🤖 [AI 업무 보고] {title}",
        "description": details,
        "color": color,
        "fields": [
            {"name": "작업 상태", "value": f"**{status}**", "inline": True},
            {"name": "보고 일시", "value": now_str, "inline": True},
            {"name": "외부 공개 쇼룸 URL", "value": f"[전세계 접속 링크]({public_url})", "inline": False},
            {"name": "관리자 9단계 관제 센터", "value": f"[SOP & 라이프사이클]({public_url}/admin/guides)", "inline": False}
        ],
        "footer": {
            "text": "Antigravity AI Developer Agent | E:/kireno"
        }
    }

    payload = {
        "username": "Antigravity AI 개발자",
        "avatar_url": "https://upload.wikimedia.org/wikipedia/commons/8/8a/Google_Gemini_logo.svg",
        "embeds": [embed]
    }

    # Always log locally first
    log_entry = {
        "timestamp": now_str,
        "title": title,
        "details": details,
        "status": status,
        "sent_to_discord": bool(webhook_url)
    }
    
    log_file = os.path.join(os.path.dirname(__file__), 'agent_discord_log.jsonl')
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

    if not webhook_url:
        print(f"[로컬 기록 완료] 디스코드 웹훅 미등록 상태입니다. (로컬 로그에 보관됨: {title})")
        print("💡 정보맨님의 서버 #일반 채널 [웹훅 URL]을 등록하시면 즉시 디스코드 채널로 실시간 브리핑됩니다.")
        return False

    try:
        req_data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            webhook_url,
            data=req_data,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Antigravity-Agent-Reporter/1.0'
            }
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            print(f"[디스코드 발송 성공] 상태 코드: {res.getcode()} ({title})")
            return True
    except Exception as e:
        print(f"[디스코드 발송 실패] {e}")
        return False

def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'set-webhook' and len(sys.argv) > 2:
            hook = sys.argv[2]
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump({'webhook_url': hook}, f, indent=2)
            print(f"[설정 완료] 디스코드 에이전트 웹훅 URL이 등록되었습니다: {hook[:40]}...")
            return
        elif cmd == 'report':
            t = sys.argv[2] if len(sys.argv) > 2 else "작업 진행 보고"
            d = sys.argv[3] if len(sys.argv) > 3 else "상세 작업 내용이 기록되었습니다."
            report_to_discord(t, d)
            return

    # Default test report
    report_to_discord(
        "9단계 비즈니스 관제 센터 & 글로벌 공개 URL 배포 완료",
        "• 전세계 접속 가능한 HTTPS 공개 URL 가동\n• SNS광고->모객->결제->재고->운송->상황->진행여부->이후관리->추가매출 9단계 관제 센터(/admin/guides) 구축\n• 3중 백업 동기화 완료"
    )

if __name__ == '__main__':
    main()
