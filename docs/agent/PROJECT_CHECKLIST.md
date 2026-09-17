# CHAOS Project Final Checklist

## Trước khi bắt đầu coding
- [ ] Git repo initialized
- [ ] Python version chosen and documented
- [ ] uv/venv/toolchain works
- [ ] `.env.example` exists
- [ ] secrets excluded by `.gitignore`
- [ ] baseline tests run
- [ ] `CHAOS_STATE.md` created

## Trước mỗi milestone
- [ ] Scope understood
- [ ] Relevant specs read
- [ ] Current state verified against code/Git
- [ ] Acceptance criteria known
- [ ] Security impact considered

## Sau mỗi task
- [ ] Test
- [ ] Verify
- [ ] Update `CHAOS_STATE.md`
- [ ] Record changed files
- [ ] Record next action
- [ ] Record blockers

## Trước release
- [ ] Unit/integration/E2E/regression pass
- [ ] Security review
- [ ] No secrets
- [ ] Packaging verified on Ubuntu + Windows
- [ ] Install/uninstall tested
- [ ] Upgrade/migration tested
- [ ] Logs sanitized
- [ ] Critical permissions tested
- [ ] Browser prompt-injection defenses tested
- [ ] Backup/recovery strategy tested where applicable
- [ ] State/docs updated
