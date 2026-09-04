# Claude LB Usage

Claude Code에서 내 API 키의 누적 사용량과 남은 한도를 확인하는 플러그인입니다.

## 준비

관리자에게 다음 정보를 받으세요.

- Claude LB 주소
- 본인 API 키 (`sk-clb-...`)

## Claude Code에서 설치

Claude Code를 실행한 뒤 다음 명령을 순서대로 입력하세요.

```text
/plugin marketplace add tokmaxxing/claude-lb-usage
/plugin install claude-lb-usage@claude-lb-tools
```

설치 화면에서 사용자 범위(`User scope`)를 선택하고 다음 값을 입력합니다.

- `base_url`: 관리자에게 받은 Claude LB 주소
- `api_key`: 본인 API 키

설치 후 재로딩 안내가 표시되면 다음 명령을 실행하세요.

```text
/reload-plugins
```

## 사용

Claude Code에서 다음 명령을 실행하세요.

```text
/claude-lb-usage:usage
```

누적 요청 수, 토큰, 비용, 남은 한도와 초기화 시간이 표시됩니다.

## settings.json으로 연결 설정

Claude LB를 이미 `~/.claude/settings.json`에서 사용 중이라면 다음과 같이 설정할 수 있습니다.

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://claude-lb.example.com",
    "ANTHROPIC_AUTH_TOKEN": "sk-clb-..."
  }
}
```

기존 설정이 있다면 파일 전체를 교체하지 말고 `env` 항목만 병합하세요. 변경 후 Claude Code를 다시 시작해야 적용됩니다.

## 하단 상태줄 표시

플러그인 명령과 함께 남은 한도를 Claude Code 하단에 계속 표시하려면 터미널에서 다음을 실행하세요. Python 3.11 이상이 필요합니다.

```bash
git clone https://github.com/tokmaxxing/claude-lb-usage.git
cd claude-lb-usage
python3 install.py
```

설치 프로그램은 `/lb-usage` 명령도 추가하고, 기존 `settings.json`의 다른 설정은 보존합니다. 다른 상태줄이 이미 설정되어 있다면 이를 덮어쓰지 않고 중단합니다. 기존 상태줄을 유지하려면 다음과 같이 설치하세요.

```bash
python3 install.py --no-statusline
```

제거하려면:

```bash
python3 install.py --uninstall
```

## 보안

- API 키를 저장소나 공유 설정에 커밋하지 마세요.
- `settings.json`의 API 키는 로컬 파일에 평문으로 저장됩니다.
- 플러그인 설치 화면에서 입력한 API 키는 민감정보 옵션으로 처리됩니다.

## License

[MIT](LICENSE)
