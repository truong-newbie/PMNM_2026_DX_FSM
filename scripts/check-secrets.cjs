#!/usr/bin/env node
/* eslint-disable no-console */
/**
 * Pre-commit secret scanner.
 *
 * Quét staged files cho các pattern nhạy cảm:
 *   - AWS access keys, secret keys
 *   - GitHub personal access tokens (ghp_*)
 *   - OpenAI keys (sk-*)
 *   - Generic password/secret assignments
 *   - PEM private keys
 *   - Keycloak client secrets (hardcoded)
 *   - Demo passwords nếu KHÔNG nằm trong allowlist
 *
 * Bypass: git commit --no-verify
 *
 * Tham khảo GitGuardian patterns:
 *   https://www.gitguardian.com/
 */

const { execSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = process.cwd();

// ─── Config ────────────────────────────────────────────────────────────────

// Allowlist: các file được phép chứa demo credentials trong docs
const ALLOWLIST_FILES = new Set([
  'docs/SECURITY.md',
  '.secrets.allowlist',
]);

// Allowlist: các string pattern KHÔNG tính là secret (dùng cho placeholder docs)
const ALLOWLIST_PATTERNS = [
  /<DEMO_PASSWORD>/g,
  /\$\{[A-Z_]+(?:_PASSWORD|_SECRET|_KEY)?:\?set in \.env\}/g,
  /\$\{[A-Z_]+_PLACEHOLDER\}/g,
  /<your[-_ ]?(password|secret|key)>/gi,
  /example\.com/gi,
  /yourname/gi,
];

// ─── Secret patterns ───────────────────────────────────────────────────────

const SECRET_PATTERNS = [
  {
    name: 'AWS Access Key ID',
    regex: /\b(AKIA|ASIA)[0-9A-Z]{16}\b/g,
  },
  {
    name: 'AWS Secret Key',
    regex: /\baws_secret_access_key\s*=\s*["']?[A-Za-z0-9/+=]{40}["']?/g,
  },
  {
    name: 'GitHub Personal Access Token',
    regex: /\bghp_[A-Za-z0-9]{36,}\b/g,
  },
  {
    name: 'GitHub OAuth Token',
    regex: /\bgho_[A-Za-z0-9]{36,}\b/g,
  },
  {
    name: 'GitHub App Token',
    regex: /\b(ghu|ghs)_[A-Za-z0-9]{36,}\b/g,
  },
  {
    name: 'OpenAI API Key',
    regex: /\bsk-[A-Za-z0-9]{32,}\b/g,
  },
  {
    name: 'Stripe API Key',
    regex: /\b(sk|pk)_(test|live)_[A-Za-z0-9]{24,}\b/g,
  },
  {
    name: 'Slack Token',
    regex: /\bxox[baprs]-[A-Za-z0-9-]{10,}\b/g,
  },
  {
    name: 'Google API Key',
    regex: /\bAIza[0-9A-Za-z\-_]{35}\b/g,
  },
  {
    name: 'Generic Password (in code/.env)',
    regex: /(password|passwd|pwd|secret|api_?key|auth_?token)\s*[:=]\s*["']([^"'\$\{][^"']{6,})["']/gi,
  },
  {
    name: 'Keycloak client secret (dx-fsm-api)',
    regex: /\bKEYCLOAK_CLIENT_SECRET\s*[:=]\s*["']?([A-Za-z0-9_\-]{8,})["']/g,
  },
  {
    name: 'Postgres password (hardcoded)',
    regex: /postgresql:\/\/[a-zA-Z0-9_]+:([A-Za-z0-9_\-]{6,})@/g,
  },
  {
    name: 'PEM Private Key',
    regex: /-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----/g,
  },
  {
    name: 'JWT (hardcoded token)',
    regex: /\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b/g,
  },
];

// ─── Helpers ───────────────────────────────────────────────────────────────

function getStagedFiles() {
  try {
    const out = execSync(
      'git diff --cached --name-only --diff-filter=ACMR',
      { encoding: 'utf8', cwd: ROOT }
    );
    return out
      .split('\n')
      .map((f) => f.trim())
      .filter(Boolean)
      .filter((f) => fs.existsSync(path.join(ROOT, f)));
  } catch (err) {
    console.error('❌ Failed to list staged files:', err.message);
    return [];
  }
}

function isAllowlisted(file) {
  if (ALLOWLIST_FILES.has(file)) return true;
  // Allow demo passwords ONLY trong file doc (README, docs/, *.md)
  // CHẶN nếu trong code (.py, .ts, .js, .yml ngoài .github/, .env, etc.)
  return false;
}

function stripAllowlistedPatterns(content) {
  let stripped = content;
  for (const pattern of ALLOWLIST_PATTERNS) {
    stripped = stripped.replace(pattern, '<ALLOWLISTED>');
  }
  return stripped;
}

function scanFile(file) {
  const fullPath = path.join(ROOT, file);
  const content = fs.readFileSync(fullPath, 'utf8');
  const stripped = stripAllowlistedPatterns(content);

  const findings = [];
  for (const { name, regex } of SECRET_PATTERNS) {
    const matches = stripped.matchAll(regex);
    for (const m of matches) {
      const lineNumber = stripped.substring(0, m.index).split('\n').length;
      const line = content.split('\n')[lineNumber - 1] || '';
      findings.push({ rule: name, line: lineNumber, snippet: line.trim().substring(0, 120) });
    }
  }
  return findings;
}

// ─── Main ──────────────────────────────────────────────────────────────────

function main() {
  const files = getStagedFiles();
  if (files.length === 0) {
    console.log('✓ No staged files to scan.');
    process.exit(0);
  }

  console.log(`🔍 Scanning ${files.length} staged file(s) for secrets...\n`);

  let totalFindings = 0;
  for (const file of files) {
    if (isAllowlisted(file)) {
      console.log(`  ⏭️  ${file} (allowlisted)`);
      continue;
    }

    const findings = scanFile(file);
    if (findings.length > 0) {
      console.error(`\n❌ ${file}`);
      for (const f of findings) {
        console.error(`   line ${f.line}: [${f.rule}]`);
        console.error(`     ${f.snippet}`);
      }
      totalFindings += findings.length;
    }
  }

  if (totalFindings > 0) {
    console.error(`\n${'='.repeat(60)}`);
    console.error(`❌ COMMIT BLOCKED: ${totalFindings} potential secret(s) detected.`);
    console.error('');
    console.error('  Actions:');
    console.error('    1. Remove the secret from the code');
    console.error('    2. Use environment variables or Keycloak admin');
    console.error('    3. If this is a false positive, add the file to');
    console.error('       ALLOWLIST_FILES in scripts/check-secrets.cjs');
    console.error('    4. Bypass (NOT RECOMMENDED): git commit --no-verify');
    console.error('');
    console.error('  Rotate any leaked secrets IMMEDIATELY in:');
    console.error('    - Keycloak admin → Clients → dx-fsm-api → Credentials → Regenerate');
    console.error('    - .env (already gitignored)');
    console.error('    - Production secret store (Vault, AWS Secrets Manager, etc.)');
    console.error('='.repeat(60));
    process.exit(1);
  }

  console.log(`\n✓ No secrets detected. Safe to commit.`);
  process.exit(0);
}

main();
