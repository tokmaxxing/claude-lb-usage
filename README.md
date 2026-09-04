# Claude LB Usage

Claude Code에서 내 API 키의 누적 사용량과 남은 한도를 확인하는 플러그인입니다.

## 준비

관리자에게 다음 정보를 받으세요.

- Claude LB 주소
- 본인 API 키 (`sk-clb-...`)

Claude LB를 사용 중이라면 일반적으로 `~/.claude/settings.json`에 이미 다음 설정이 있습니다.

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://claude-lb.example.com",
    "ANTHROPIC_AUTH_TOKEN": "sk-clb-...",
    "CLAUDE_LB_TIMEZONE": "Asia/Seoul"
  }
}
```

`CLAUDE_LB_TIMEZONE`은 선택 사항입니다. 설정하지 않으면 Claude Code가 실행되는 시스템의 로컬 시간대를 사용합니다. 원격 서버의 시간대가 UTC라면 실제 사용자의 시간대(예: `Asia/Seoul`)를 지정하세요. 기존 파일 전체를 교체하지 말고 필요한 항목만 병합한 뒤 Claude Code를 다시 시작하세요.

## Claude Code에서 설치

Claude Code를 실행한 뒤 다음 명령을 순서대로 입력하세요.

```text
/plugin marketplace add tokmaxxing/claude-lb-usage
/plugin install claude-lb-usage@claude-lb-tools
```

설치 화면에서 사용자 범위(`User scope`)를 선택하세요. 플러그인은 위의 Claude Code 연결 설정을 그대로 사용하므로 주소나 API 키를 다시 입력하지 않습니다.

설치 후 재로딩 안내가 표시되면 다음 명령을 실행하세요.

```text
/reload-plugins
```

## 사용: 모델 호출 없음

Claude Code에서 다음 명령을 실행하세요.

```text
/claude-lb-usage:usage
```

플러그인의 로컬 훅이 이 명령만 가로채 API를 조회하고 결과를 직접 그립니다. 명령은 모델에 전달되지 않으며, 다른 프롬프트나 `!` shell mode의 동작에는 영향을 주지 않습니다. 전역 `respondToBashCommands` 설정도 필요하지 않습니다.

```text
Claude LB Usage

Current session
█░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  1% used
$293.86 / $32,812.50 spent · $32,518.64 left
Resets 5:13pm (KST)

Current week (all models)
█░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  <1% used
$293.86 / $157,500.00 spent · $157,206.14 left
Resets Sep 11, 2:13pm (KST)
```

## 하단 상태줄 표시

플러그인 명령과 함께 남은 한도를 Claude Code 하단에 계속 표시하려면 터미널에서 다음을 실행하세요. Python 3.11 이상이 필요합니다.

```bash
git clone https://github.com/tokmaxxing/claude-lb-usage.git
cd claude-lb-usage
python3 install.py
```

설치 프로그램은 기존 `settings.json`의 다른 설정을 보존합니다. 다른 상태줄이 이미 설정되어 있다면 이를 덮어쓰지 않고 중단합니다. formatter만 설치하고 기존 상태줄을 유지하려면 다음과 같이 설치하세요.

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
- 플러그인은 API 키를 별도 설정으로 복사하거나 저장하지 않습니다.

## License

[MIT](LICENSE)
