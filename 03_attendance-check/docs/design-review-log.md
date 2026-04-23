# 設計書レビュー対応ログ（02_design.md）

本書は `02_design.md`（システム設計書）に対する Codex レビューの指摘と対応履歴を記録する。

---

## Round 1 — Codex レビュー（2026-04-23）

### 総合評価
**B** — 骨格は要件に沿うが、要件不整合・内部矛盾が残存。Phase4 進行前に固定が必要。

### 対応サマリ
- Critical: 3件すべて対応
- Major: 3件中 2件対応 / 1件は方針転換して対応
- Minor: 3件中 1件対応（残は見送り、理由後述）

### 指摘と対応

#### Critical

| # | 指摘 | 対応 | 反映箇所 |
|---|---|---|---|
| C1 | A-06 欠損時挙動が要件違反かつ内部矛盾（§4.3 と §7.1） | `applications.csv` 欠損と `shifts.csv` 欠損を分離。`shifts` 欠損時は A-06 残業分岐を 8h fallback で実行継続する旨を明文化 | §4.3、§7.1、§2.3 |
| C2 | サマリ分母（全N件）の定義が未固定 | `total_records = timesheet.csv の有効行数（skipped を除く）` を不変条件として明記。`MatchedCase`（staff-day）件数と混同しない旨を追記 | §4.2、§6.1 |
| C3 | `approver_status` の代表値決定ルール未定義で再現性喪失 | 代表値化をやめ、`MatchedCase.approver_statuses` として元ステータス集合を保持。A-07 判定用と表示用で参照ロジックを分離 | §3.2、§4.2、§7.1（A-07） |

#### Major

| # | 指摘 | 対応 | 反映箇所 |
|---|---|---|---|
| M1 | `clock_out < clock_in` を自動で翌日補正は危険 | 自動補正を廃止。入力 datetime を尊重し、`clock_out < clock_in` は WARN+skip（`SkippedRecordReporter` に登録）に変更 | §5.1 |
| M2 | `record_id` 前提と日次検知（A-05/A-07）の粒度不一致 | `AnomalyFinding` に `scope`（`record` / `day`）フィールドを追加。day スコープの識別子を `staff_id+date` と正式化 | §4.2、§3.2 |
| M3 | エラー分類ラベルと実挙動の不一致（WARN後 exit が混在） | `exit するものは ERROR/FATAL` に統一。§4.3 の `samples/{YYYYMM}/` 不在を `ERROR (exit 1)` に修正し、§8.1 と整合 | §4.3、§8.1 |

#### Minor

| # | 指摘 | 対応 |
|---|---|---|
| m1 | 出力順序のソートキー未定義 | `severity desc, date asc, staff_id asc, pattern_id asc` を §6.2 に追記 |
| m2 | チェックリスト出力の必須列契約が弱い | **見送り**。技術仕様書（Phase4）で writer I/F と共に規定する範囲（§1.3 の境界による） |
| m3 | 観測可能性が stdout 依存 | **見送り**。セミナーデモ最小実装方針、`skipped_records.csv` で監査は担保済み（§8.2） |

### 見送り理由
- m2: 設計書スコープは「モジュール分割・責務・データ受け渡し形式」まで（§1.3）。writer I/F の列契約は技術仕様書レベル。
- m3: `run_summary.json` 追加はデモ映え・最小実装方針と逆行。現行の stdout サマリと `skipped_records.csv` で要件を満たす。

---

## ラウンド2 (2026-04-23)

### 総合評価
**B**（R1と同評価）— R1で塞いだ論点の骨格は維持されているが、scope/day_key 導入時の副作用で **設計内の内部矛盾が3点** 残存。Phase4 進行前の固定対象として Critical 3件は必修。通知期限データ受渡しと `generate-samples` CLI契約も Major として併修。

### R1比較
- R1は「要件との外部整合性」中心の指摘が主体 → 全対応済
- R2は「R1で追加した scope/day_key/approver_statuses の内部整合性」に焦点が移行
- 骨格は安定、残課題は設計内の整合調整が中心。Phase4 前段の最終固めフェーズ

### 対応サマリ
- Critical: 3件すべて対応
- Major: 4件すべて対応
- Minor: 2件中 1件対応 / 1件見送り

### 指摘と対応

#### Critical

| # | 指摘 | 対応 | 反映箇所 |
|---|---|---|---|
| C1 | A-07 判定仕様が設計内で矛盾（`approver_statuses` の pending 在否判定と「個別申請レコード単位」判定が併記） | A-07 判定を **「申請行 (`application_id`) 単位」で統一** と明記。`approver_statuses` は表示専用に限定する旨を §3.2 に追記 | §3.2、§7.1（A-07） |
| C2 | 重複集約キーが day-scope を落としている（`scope`/`day_key` 導入後も Scorer 集約が `record_id` のみ） | `finding_key = record_id` (scope=record) / `day_key` (scope=day) を正式な集約キーとして §3.2・§7.2 に明記。Scorer/Writer/JSON で同キーを貫通 | §3.2（SeverityScorer）、§7.2 |
| C3 | SeverityScorer の I/F と例外条件実装が不整合（I/F は `AnomalyFinding[]` のみ入力だが、疑似コードは `case` 参照前提） | Scorer I/F を `Finding[] + case_index（MatchedCase lookup）` を受け取る形に変更。A-04/A-05 の例外条件は `case_index[day_key]` 経由で参照する旨を明示 | §3.2（SeverityScorer）、§7.2 |

#### Major

| # | 指摘 | 対応 | 反映箇所 |
|---|---|---|---|
| M1 | `approver_status` 廃止が過剰対応で外部I/Fとズレ | **内部 `approver_statuses` / 外部出力 `approver_status`（join済み文字列）** の二層定義を §3.2 に明記 | §3.2 |
| M2 | M-5 対応期限が Notification 設計に接続されていない | `config` で `response_deadline` を算出し、`DispatchCoordinatorReport` / `NotificationWriter` の必須入力に追加する旨を §3.2・§7.4 に記載 | §3.2、§7.4 |
| M3 | 依存関係に循環リスク（`config` → `cli` 依存の記述が逆） | モジュール表を修正。`cli → config` の一方向依存に訂正 | §3.1 |
| M4 | `generate-samples` CLI 契約不足 | `generate-samples` 引数表（`--month`, `--count`, `--data-class`, `--seed`, `--anomaly-rate`）を §6.1 に追記 | §6.1 |

#### Minor

| # | 指摘 | 対応 |
|---|---|---|
| m1 | `applications.csv` 欠損時の説明が A-06 休暇分岐のみで残業分岐と不一致 | §4.3 の分岐説明に「A-06 残業分岐も applications 欠損時は skip」を明記し §7.1（A-06）と整合 |
| m2 | 出力ソート規約に stdout サマリを含めており集計表示と一覧表示が混在 | **見送り**。§6.2 は「一覧出力」として適用対象を明示済み。stdout サマリの集計行（件数）は設計書スコープ外の描画詳細で、技術仕様書 Phase4 で整理する方がスジが良いため MAY 降格 |

### 見送り理由
- Minor m2: 設計書スコープ（§1.3）はモジュール分割・責務・データ受け渡し形式まで。stdout サマリの集計行描画は writer 内部の描画詳細に踏み込む領域で、技術仕様書レベルでの規定が適切。現行 §6.2 の「一覧出力」表現で実装時の混乱は生じない。

---

## ラウンド3 (2026-04-23) ※最終

### 総合評価
**B（条件付きで次フェーズ進行可）** — Codex R3。R1/R2 の反映は見える。ただし A-07 の集約粒度崩れと `client_site` のデータ起点欠落という **実装時に破綻する2点** を Critical として挙げられており、これを塞げば Phase4 着手可能の水準。

### R1 → R2 → R3 の推移
- R1: 要件との外部整合性（A-06 欠損、サマリ分母、approver 代表値） → 全塞ぎ
- R2: R1 で追加した scope/day_key/approver_statuses の内部整合 → 全塞ぎ
- R3: 粒度設計（A-07 の `scope="application"`）と入力スキーマ（`client_site`）の最後の穴埋め → 本ラウンドで全塞ぎ
- **論点は R1→R2→R3 で確実に狭まっており、最終の微調整フェーズに到達**

### 対応サマリ
- Critical: 2件すべて対応
- Major: 4件すべて対応
- Minor: 3件すべて対応

### 指摘と対応

#### Critical

| # | 指摘 | 対応 | 反映箇所 |
|---|---|---|---|
| C1 | A-07 を「申請行単位で検知」と定義しているのに Scorer 集約が `day_key` で潰し、複数 pending 申請の滞留が欠落（M-2/M-4 の実効性低下） | `AnomalyFinding` に **`scope="application"`** を追加し、A-07 は `finding_key=f"application:{application_id}"` で集約。同一 staff×date に複数 pending 申請があっても申請単位で別 Finding として保持 | §3.2（scope/finding_key）、§4.2、§7.1（A-07） |
| C2 | `client_site` で出力・集計する設計なのに、入力 Loader の主要フィールド定義に `client_site` の起点がない（実装不能） | `StaffPunchLoader` 出力 `PunchRecord` に `client_site` を必須追加。`timesheet.csv` の必須列として §5.1 に明記し、欠損時は WARN + `unknown` フォールバックで行保持（skip せず） | §3.2（StaffPunchLoader）、§4.2、§5.1 |

#### Major

| # | 指摘 | 対応 | 反映箇所 |
|---|---|---|---|
| M1 | `finding_key` 衝突回避が「書式が違う前提」に依存 | `finding_key` を prefix 名前空間（`record:` / `day:` / `application:`）に統一。書式差依存を廃止し、設計的に衝突排除 | §3.2、§7.2 |
| M2 | `--assignee` / `--client` フィルタ時の分母定義が不明 | 「フィルタ後分母に再計算」として仕様固定。`total_records_filtered` を導入し、出力見出しに絞込条件を明示。JSON meta に `filters` を記録 | §4.2、§10.1 |
| M3 | `response_deadline` 算出が `as_of_date` 中心で対象月とズレる余地 | 真実源を `target_month`（`--month`）に変更。`config.resolve_response_deadline(target_month, holidays)` 型に修正 | §7.4 |
| M4 | `--no-mask-names` で real データの PII 平文出力が可能で防波堤として弱い | `--data-class real` + `--no-mask-names` 時は **`--confirm-unmask-real` フラグ必須**（未付与は exit 2）に強化 | §6.1、§9.1、§9.3 |

#### Minor

| # | 指摘 | 対応 |
|---|---|---|
| m1 | `config` が `HolidayCalendarLoader` へ依存しており層境界が逆流 | `config` を純粋計算ユーティリティに寄せ、`HolidayCalendar` オブジェクトを引数注入に変更（§3.1 モジュール表） |
| m2 | JSON に実行メタ（引数、skip 件数、rule-skip 理由）が薄く追跡性が弱い | `meta.month` / `as_of_date` / `response_deadline` / `filters` / `data_class` / `skipped_summary` / `rule_skipped` を §10.1 に追加 |
| m3 | A-06 の「scheduled_hours - 1h 休憩」定義が入力データ次第で解釈ブレ | `shifts.csv` の `scheduled_start/end` を「拘束時間（休憩含む）」として §5.1 に明記 |

### R3 見送り項目
なし。Critical/Major/Minor すべて対応。

---

## 最終残論点

R3 で全指摘対応済のため、Phase4 着手前の未解決論点は **なし**。ただし設計書スコープ（§1.3）の定義上、以下の3点は意図的に技術仕様書（Phase4）に委譲している：

1. **各モジュールの関数シグネチャ・クラス属性の型ヒント**（§1.3 で明示）
2. **単体テスト設計・カバレッジ方針**（§1.3 で明示）
3. **LLM プロンプト本文の具体定義**（MAY-1、§8.3 で「ルール辞書フォールバック」は確定済・本文は技術仕様へ）

### 将来拡張として §10.3 に接続点を残す項目（本フェーズ未実装）
- 重要度スコア表の YAML 外出し
- 36 協定・抵触日管理（月またぎ集計）
- 実 SaaS API 連携（Loader 差し替え）
- Slack/メール通知（MAY-4）

### 承認可能状態の判断
**Phase4 進行可**。R3 レビューで Codex が挙げた Critical 2件・Major 4件・Minor 3件すべてを反映し、設計書の内部整合・要件トレーサビリティ・3者ワークフロー設計思想は十分実用水準に到達。セミナーデモ最小実装前提での「十分実用的」判断として本ラウンドで設計レビューは終結。
