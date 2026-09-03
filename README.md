# claude-lb usage for Claude Code

Claude Code에서 현재 `claude-lb` 고객 API 키의 누적 사용량과 남은 한도를 확인하는 독립형 연동 도구입니다. `claude-lb` 서버 소스가 private이어도 이 저장소만 배포하면 고객이 직접 설정할 수 있습니다.

제공 기능:

- `/lb-usage`: 누적 요청·토큰·비용과 모든 키별 한도 표시
- statusline: 가장 많이 사용된 글로벌 비용 한도 또는 토큰 한도를 60초 간격으로 표시
- Claude Code marketplace plugin: `/claude-lb-usage:usage`
- user/project 범위 설치 및 안전한 제거
- 셸 환경 변수와 Claude Code `settings.json`의 `env` 모두 지원

## 요구 사항

- Python 3.11 이상
- `GET /v1/usage/self`를 제공하는 claude-lb 배포
- 고객별 `sk-clb-...` API 키

## 독립 설치기 사용

저장소를 받은 뒤 사용자 전체 범위로 설치:

```bash
git clone https://github.com/tokmaxxing/claude-lb-usage.git
cd claude-lb-usage
python3 install.py
```

프로젝트에만 설치하려면:

```bash
python3 install.py --scope project
```

기존 statusline을 유지하고 `/lb-usage`만 설치하려면:

```bash
python3 install.py --no-statusline
```

설치기는 기존 `settings.json`의 `env`를 포함한 다른 설정을 보존합니다. 다른 statusline이나 같은 이름의 외부 파일이 있으면 중단하며, 의도적으로 교체할 때만 `--force`를 사용합니다.

### 고객 연결 설정

일반적인 Claude Code 구성처럼 사용자 설정 `~/.claude/settings.json`의 `env`에 넣을 수 있습니다. 이미 다른 설정이 있다면 아래 `env` 항목만 병합합니다:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://claude-lb.example.com",
    "ANTHROPIC_AUTH_TOKEN": "sk-clb-..."
  }
}
```

Claude Code는 `settings.json.env` 값을 각 세션과 statusline/skill 명령의 환경에 적용하므로 별도 formatter 설정은 필요하지 않습니다. 설정을 바꾼 뒤 Claude Code를 새로 시작하고 `/lb-usage`를 실행하거나 하단 statusline을 확인합니다.

API 키를 사용자 설정 파일에 평문으로 두지 않으려면 Claude Code를 실행하는 셸에서 설정해도 됩니다:

```bash
export ANTHROPIC_BASE_URL="https://claude-lb.example.com"
export ANTHROPIC_AUTH_TOKEN="sk-clb-..."
claude
```

Claude Code 연결 설정과 사용량 조회 설정을 분리해야 할 때만 전용 변수를 사용합니다. 전용 변수가 있으면 `ANTHROPIC_*`보다 우선합니다:

```bash
export CLAUDE_LB_BASE_URL="https://claude-lb.example.com"
export CLAUDE_LB_API_KEY="sk-clb-..."
```

동일한 전용 변수도 `settings.json.env`에 넣을 수 있습니다. 원본 JSON은 설치된 formatter에 `--json`을 전달해 확인할 수 있습니다. formatter를 Claude Code 밖에서 직접 실행할 때는 `settings.json.env`가 자동 주입되지 않으므로, 그 터미널에도 변수를 export해야 합니다.

제거:

```bash
python3 install.py --uninstall
# 또는 프로젝트 범위
python3 install.py --uninstall --scope project
```

제거기는 이 도구가 관리하는 파일과 statusline 항목만 삭제합니다.

## Claude Code 플러그인으로 사용

로컬 marketplace를 등록하고 플러그인을 설치할 수 있습니다:

```bash
claude plugin marketplace add .
claude plugin install claude-lb-usage@claude-lb-tools
```

그다음 `/claude-lb-usage:usage`를 실행합니다. 플러그인 설정 화면에서 `base_url`과 `api_key`를 입력할 수 있으며, `api_key`는 sensitive 옵션으로 선언되어 Claude Code의 보안 저장소를 사용합니다. 환경 변수 방식도 그대로 지원합니다.

플러그인 기본 설정은 일반 `statusLine`을 설정할 수 없으므로, statusline까지 필요하면 위의 독립 설치기를 한 번 실행해야 합니다.

GitHub 저장소에서는 로컬 경로 대신 다음처럼 등록할 수 있습니다:

```bash
claude plugin marketplace add tokmaxxing/claude-lb-usage
claude plugin install claude-lb-usage@claude-lb-tools
```

## 서버 API 계약

formatter는 API 키를 `x-api-key` 헤더로 전달하여 다음 endpoint를 호출합니다:

```text
GET {CLAUDE_LB_BASE_URL}/v1/usage/self
```

base URL이 이미 `/v1`으로 끝나면 `/usage/self`만 추가합니다. 기대하는 응답 예시:

```json
{
  "request_count": 42,
  "total_tokens": 123456,
  "cached_input_tokens": 12000,
  "total_cost_usd": 4.21,
  "limits": [
    {
      "limit_type": "cost_usd",
      "limit_window": "monthly",
      "max_value": 50000000,
      "current_value": 4210000,
      "remaining_value": 45790000,
      "used_percent": 8.42,
      "model_filter": null,
      "reset_at": "2026-10-01T00:00:00Z"
    }
  ]
}
```

`cost_usd` 한도의 원시 값은 microdollar이고 formatter가 달러로 변환합니다. 토큰 한도의 원시 값은 토큰입니다.

## 개발 및 검증

```bash
python3 -m unittest discover -s tests -v
ruff check .
shellcheck install.sh
claude plugin validate .
```

## 보안

- 독립 설치기는 API 키 값을 새로 기록하거나 복사하지 않으며 기존 `settings.json.env`를 그대로 보존합니다.
- `~/.claude/settings.json`에 API 키를 넣으면 로컬 파일에 평문으로 저장됩니다. 이 파일이나 프로젝트 설정을 저장소에 커밋하지 마세요.
- 플러그인 `api_key` 옵션은 `sensitive: true`로 선언되어 있습니다.
- 오류 메시지와 출력에는 API 키를 포함하지 않습니다.
- 고객에게 upstream 공유 계정의 rate-limit 정보를 노출하지 말고, 서버가 고객 키별 한도만 반환하도록 구성해야 합니다.

## License

[MIT](LICENSE)
