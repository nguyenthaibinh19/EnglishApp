# Phase 18B.9D5A2D2 — WSL systemd isolation correction

Status: **FOCUSED RUN COMPLETE — OVERALL FAIL.** Not a VPS install. Not production activation. Canonical 15-module hashes unchanged.

Baseline main: `82f26bc8d95240671a4e030270e49fbe06d65814`. Accepted import branch `phase18b9/d5a2d0-p1-source-import` @ `98b590e` unchanged.

Lab: `D:\Tools\age-c2d5a2d2-isolation-20261116T2030Z-e7c4b921`  
Evidence: `/home/nguyenthaibinh19/language-guard/d5a2d2-evidence/results-r1` (copy under lab `results-r1/`)

## 1. Historical failure root causes

| Defect (D5A2B1) | Cause | Later related work | Still open for production? |
|---|---|---|---|
| Positive transfer FAIL (`magic`) | `lgd5a2b1-handoff@.service` had `StandardOutput=socket` without `StandardError=journal`; helper status lines entered the frame stream | B2 added `StandardError=journal` and showed LGS1; B3 encrypted; **B1 step remains not accepted** | Unit drafting must keep journal stderr; B1 not rewritten as accepted |
| Invalid cgroup FAIL | Intruder/shell did not observe leading `REFUSED` while stderr polluted the socket | B2 showed exact `REFUSED` + `refused-not-unit` under repaired units | Must be re-proven on production-shaped units; not assumed from B2 alone |
| Interrupted transfer FAIL | Short connection before worker exec; no `detail=incomplete` observed | B2 sequence read 4-byte `LGS1` then closed; helper logged `incomplete` | Must be re-proven for D5A2D2 acceptance |
| StateDirectory BLOCKED | Proposed oneshots outside approval; recursive chown unmeasured | D5A2D2 measured only a disposable WSL dir | **Not** VPS proof |

D5A2C templates already included `StandardError=journal` but used lab `/mnt/d/Tools/...` ExecStart paths and were never installed.

## 2. Unit draft changes

Production-shaped drafts (not installed):

- `units-production/language-guard-offbox-handoff.socket`
- `units-production/language-guard-offbox-handoff@.service` — `StandardError=journal`; helper `guard`; expected peer `language-guard-offbox-worker.service`; no OAuth on helper
- `units-production/language-guard-offbox-worker.service` — `lg-backup`; `LoadCredential=oauth-refresh`; no age identity; **no** `StateDirectory=`

WSL test units (unique names only): `lgd5a2d2-*` with lab users `lgd5a2d2-guard` / `lgd5a2d2-backup` and lab paths under `/var/lib/lgd5a2d2-e7c4b921-*`.

Canonical Python modules were copied into the lab `offbox/` for ExecStart only; SHA-256 matched the accepted inventory (15/15). No module bytes were edited.

## 3. Unit draft SHA-256

Production drafts:

```text
986151a9bc2c056f0b588c4df8032ef5f9227ab387f0c718309c3c1a6be94b19  language-guard-offbox-handoff.socket
3f73aa3f584b2a0f3fedac97524526054fc109c5c075b9ba201ca74494c4be17  language-guard-offbox-handoff@.service
45681cbae2aabeafffc763ee3838dbfdf98a674d95a2c7b9308a02eb8be1de6d  language-guard-offbox-worker.service
```

Installed WSL test unit hashes (from evidence `unit-sha256.txt`):

```text
c315ca404408c0a24f9041e5a56a950ae402cc1b2acb74cf7c3a334a6e166852  lgd5a2d2-handoff.socket
bb73b870d8022a919687ed99fbf09a87ee5e6915ccab7d9fc64db4518e374fae  lgd5a2d2-handoff@.service
b2a105777d1fc7689c371dfa5bec35431f7f36f51343ad24d8ca2e8300ec6d4a  lgd5a2d2-worker.service
e29b337b1a723e22a32dab125ec97393cb09d671b41d9479573ef51e4e15ec81  lgd5a2d2-intruder.service
8b8e8b06398070041c05e00cc6e0cad911ad686e580c3d7caa3d61bfec18123c  lgd5a2d2-cred-missing.service
993c014b244faea2757ae991a97e45d0af502dff4ef38724b393de93595bddf8  lgd5a2d2-statedir.service
```

## 4. Focused test results (one run)

Automated score (`results-r1/score.txt`): **OVERALL=FAIL**

| Test | Score | Raw evidence notes |
|---|---|---|
| A positive transfer | **FAIL** | Attempt `d5a2d2-positive-r1` reached `state=ENCRYPTED`; worker `Result=success` / `ExecMainStatus=0`. Helper `decision=accepted` / `frame-sent` lines were **not** present in the collected journal (helper instance journals not captured; `systemctl` warned about invalid unit name `@`). Formal score required those journal lines → FAIL |
| B stderr isolated | **PASS** | Interrupt prefix `hex=4c475331` (`LGS1`). Helper unit has `StandardError=journal` |
| C unauthorized peers | **PASS** | `normal-connect=errno=13`, `guard-connect=errno=13` |
| D invalid cgroup | **FAIL** | `intruder-result.txt`: `exact-refused=true bytes=7 first4=52454655 leaf=lgd5a2d2-intruder.service`. Score required `refused-not-unit` in collected journal → FAIL |
| E interrupted fail-closed | **FAIL** | Prefix is `LGS1`; source SHA unchanged. Collected journal lacks `detail=incomplete` → FAIL |
| F missing credentials | **PASS** | `ActiveState=failed`, `ExecMainStatus=243` |
| G StateDirectory disposable | **PASS** | Before: dir/marker `root:root`. After start: dir `755` and marker owned by backup uid/gid `991:981`. **WSL disposable only — not VPS proof** |
| H existing unchanged + inactive | **PASS** | Historical `lgd5a2b1-*` metadata unchanged; new units not left active |

Accepted source SHA unchanged: **YES**  
New WSL units inactive after stop: **YES** (socket disabled; services static/inactive; cred-missing recorded `failed` but not running)

## 5. WSL identity mapping

```text
lgd5a2d2-guard uid=992 gid=982
lgd5a2d2-backup uid=991 gid=981
```

These are new WSL lab identities. They are not VPS `guard` / `lg-backup` and not the older `lgd5a2b1-*` accounts.

## 6. Remaining production risks

1. Formal D5A2D2 acceptance gate **FAIL** — helper journal collection gap blocks proving A/D/E to the written score rules.
2. `StateDirectory=` on a pre-existing directory **did** re-own contents to the service user on WSL; must not be applied to `/var/lib/language-guard-backup` on the VPS without a separate measurement plan.
3. Production Python version and `accounts.db` journal mode still unread.
4. No accepted production unit set is installed anywhere; drafts remain local.
5. OAuth / age materials / Drive activation remain out of scope.
6. Import branch still not merged.

## 7. Proposed production unit definitions

See lab `units-production/`. Key rules: `StandardError=journal` on handoff; helper never loads OAuth; worker uses `LoadCredential`; no private age identity; no `StateDirectory=` on the existing backup directory; ExecStart under `/opt/language-guard/...`; live upload remains fail-closed until a later gate.

## 8. Recommendations for later VPS readiness

1. Authorized follow-up to fix helper-journal collection (no unrestricted repair of the failed score) and re-score A/D/E with captured `lgd5a2d2-handoff@*` journals — only if Leader assigns it.
2. Keep production drafts free of `StateDirectory=` until a VPS-specific disposable experiment is approved.
3. Do not merge the import branch or install units on the VPS from this FAIL result.

## Authorization confirmation

No VPS/SSH, Google API, OAuth change, production DB access, canonical source edit, import-branch merge, or Cloud Sync activation occurred.
