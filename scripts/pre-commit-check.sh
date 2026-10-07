#!/usr/bin/env bash
# =============================================================================
# Cocklebur Git Pre-Commit Security Leak Check
# =============================================================================
set -e

# 1. 檢查暫存區 (Staged) 檔名，禁止提交機敏環境設定檔、憑證與金鑰檔案
BLOCKED_PATTERNS=(
  "(^|/)deploy/deploy\.env$"
  "(^|/)deploy/k8s/overlays/.*/\.env$"
  "(^|/)deploy/k8s/overlays/.*/env-config\.env$"
  "(^|/)\.env$"
  "(^|/)secret\.env$"
  "\.(pem|key|p12|pfx)$"
  "(^|/)[^/]*kubeconfig\.(yaml|yml)$"
  "(^|/)kubeconfig$"
)

STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)

if [[ -z "$STAGED_FILES" ]]; then
  exit 0
fi

FAILED=0

for file in $STAGED_FILES; do
  for pattern in "${BLOCKED_PATTERNS[@]}"; do
    if echo "$file" | grep -Eq "$pattern"; then
      # 排除範本與腳本 (*.example, *.sh, *.py)
      if [[ "$file" =~ \.example$ ]] || [[ "$file" =~ \.(sh|py)$ ]]; then
        continue
      fi
      echo "❌ [Security Alert] 禁止提交機敏檔案: $file (匹配規則: $pattern)"
      FAILED=1
    fi
  done
done

# 2. 檢查暫存區程式碼內容 (Staged Content Diff)，防止提交內部網域、私鑰或真實密鑰
# 注意：排除 pre-commit 檢查腳本本身，避免自檢誤報
LEAK_PATTERNS=(
  "oops\.wtf"
  "jujube"
  "91jhtOrjnWEhetE3BKuRklW"
  "-XCKpWHYKR0x9EYSG5eEp"
  "ghp_[a-zA-Z0-9]{20,}"
  "BEGIN (RSA|OPENSSH|EC|DSA|PGP|PRIVATE) KEY"
)

# 取得排除 pre-commit 腳本後的 diff 內容
DIFF_OUTPUT=$(git diff --cached -U0 -- . ':!scripts/pre-commit-check.sh' ':!.git/hooks/pre-commit')

for pattern in "${LEAK_PATTERNS[@]}"; do
  MATCHES=$(echo "$DIFF_OUTPUT" | grep -E "^\+[^+]" | grep -E -e "$pattern" || true)
  if [[ -n "$MATCHES" ]]; then
    echo "❌ [Security Alert] 偵測到暫存內容中包含機敏字串/內部資訊 (規則: $pattern):"
    echo "$MATCHES" | head -n 5 | sed 's/^/   /'
    FAILED=1
  fi
done

if [[ $FAILED -eq 1 ]]; then
  echo ""
  echo "🚨 Commit 已被 pre-commit hook 攔截！請移除機敏檔案/內容後再重試。"
  echo "   (若為測試需要跳過此檢查，請使用 git commit --no-verify)"
  exit 1
fi

echo "✅ [Security Check] 暫存區安全性檢查通過 (無機敏檔案與內部資訊洩漏)"
exit 0
