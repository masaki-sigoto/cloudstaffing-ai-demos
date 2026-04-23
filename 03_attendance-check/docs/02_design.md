# システム設計書: 勤怠チェック自動化（Attendance Check Automation）

本書は要件定義書 `docs/01_requirements.md` の MUST/SHOULD/MAY を実装に落とし込むための **中粒度の設計書** である。クラウドスタッフィング（人材派遣管理SaaS）の月次締め業務を支える **3者ワークフロー（スタッフ／派遣元／派遣先）** を設計思想に強く反映し、「締め前アラート」として機能するルールエンジン型デモツールの構造を定義する。

---

## 1. 設計の目的と範囲

### 1.1 本書の位置付け
- **What（要件）** は `docs/01_requirements.md` に定義済み。本書はそれを **How（設計）** に変換する中間成果物である。
- セミナー実演用モック（「動けば正義」方針）であることを前提とし、**過剰設計を避け、Python標準ライブラリで実装可能な最小構造** を採る。
- コードレベルの詳細（関数シグネチャ、クラス属性、テストケース）は Phase4 の技術仕様書に委ねる。本書では **モジュール分割・責務・データの受け渡し形式** までを規定する。

### 1.2 要件定義書との対応
| 要件ID | 内容 | 本設計書での主担当セクション |
|---|---|---|
| M-1 | 勤怠×申請データ突合 | §3（`StaffPunchLoader`/`LeaveRequestLoader`/`ShiftPlanLoader`/`ClientApprovalMatcher`）、§4、§5 |
| M-2 | 異常検知（A-01〜A-10） | §3（`AnomalyRuleEngine`）、§7.1 |
| M-3 | 重要度判定（3軸スコアリング） | §3（`SeverityScorer`）、§7.2 |
| M-4 | チェックリスト自動生成 | §3（`DispatchCoordinatorReport`）、§6.2 |
| M-5 | コーディネーターへの通知 | §3（`NotificationWriter`）、§6.2、§9 |
| M-6 | サマリ表示 | §3（`SummaryRenderer`）、§6.1 |
| S-1〜S-4 | JSON出力・フィルタ・サンプル生成・カラー | §3（`JsonResultWriter`/`SampleDataGenerator`）、§6.1 |
| MAY-1 | LLM推奨アクション文生成 | §3（`RecommendationComposer`）、§8.3 |
| 5.1 | 実データ防波堤 | §6.1、§9.3 |

### 1.3 技術仕様書との境界
- **本設計書で決めること**: モジュール分割、データフロー、CLI 体系、ルール追加方式、重要度スコア表、出力ファイル命名規約、エラー分類。
- **技術仕様書（Phase4）に委ねること**: 各モジュール内部の関数シグネチャ／クラス定義、単体テスト設計、LLM プロンプト本文、型ヒントの付与方針。

---

## 2. アーキテクチャ概要

### 2.1 設計思想
- **パイプライン型**: CSV ロード → 突合 → 異常検知 → 重要度付与 → グルーピング → 出力、という **単方向のデータフロー** で構成し、段階ごとに中間 dataclass を通す。
- **ルール駆動**: 異常検知（A-01〜A-10）を **ルールオブジェクトの配列** として宣言し、エンジン本体はルール追加に対して閉じた構造にする（OCP を軽く意識）。
- **3者ワークフロー反映**: 出力側コンポーネント（チェックリスト／通知）を **派遣元コーディネーター別** と **派遣先事業所別** の2軸で分岐させ、派遣元→派遣先→スタッフの差戻し起票資料として直接使える粒度にする。
- **決定的実行**: MUST 機能はすべて決定的（同一入力＋同一 `--as-of-date` で同一出力）。非決定性は MAY-1（LLM）のみに局所化。

### 2.2 システム全体像

```
                    ┌──────────────────────────┐
                    │   CLI Entry (src/main.py) │
                    │  subcommand: check /       │
                    │              generate-samples │
                    └─────────────┬────────────┘
                                  │  parsed args (month, as_of_date, data_class, ...)
                                  ▼
        ┌───────────────────── Loader Layer ─────────────────────┐
        │ StaffPunchLoader    LeaveRequestLoader  ShiftPlanLoader │
        │  (timesheet.csv)      (applications.csv)   (shifts.csv) │
        │                       HolidayCalendarLoader (holidays.csv)│
        └──────────────┬────────────────────────────────────────┘
                       │  typed rows (dataclass list)
                       ▼
        ┌──────────── Matching Layer ────────────┐
        │ ClientApprovalMatcher                    │
        │   staff_id × date で punch / leave /     │
        │   overtime / shift を合流               │
        └──────────────┬────────────────────────┘
                       │  MatchedCase (per staff × date)
                       ▼
        ┌──────────── Detection Layer ───────────┐
        │ AnomalyRuleEngine                        │
        │   Rule[A-01] Rule[A-02] ... Rule[A-10]   │
        │   （1ルール = 1クラス、プラグイン追加容易） │
        └──────────────┬────────────────────────┘
                       │  AnomalyFinding[]
                       ▼
        ┌──────────── Scoring Layer ─────────────┐
        │ SeverityScorer                           │
        │   3軸（給与・請求・法令）→ 高/中/低      │
        │   例外条件（A-04降格、A-05据え置き等）   │
        └──────────────┬────────────────────────┘
                       │  ScoredFinding[]
                       ▼
        ┌──────────── Masking Layer (optional) ──┐
        │ PiiMaskingFilter  (--mask-names 時のみ)  │
        └──────────────┬────────────────────────┘
                       │
        ┌──────────── Output Layer ──────────────┐
        │ SummaryRenderer      (標準出力ヘッダ)   │
        │ DispatchCoordinatorReport  (派遣元担当別)│
        │ ClientSiteReport           (派遣先事業所別)│
        │ NotificationWriter   (output/notifications/) │
        │ JsonResultWriter     (output/result_*.json) │
        │ RecommendationComposer (MAY-1, LLM or dict) │
        │ SkippedRecordReporter (output/skipped_records.csv) │
        └────────────────────────────────────────┘
```

### 2.3 ハッピーパス（処理の流れ）

1. CLI が `check --month 2026-04 --as-of-date 2026-04-28 --data-class dummy` を受理。
2. `--data-class` ガードを通過後、ディレクトリ `samples/202604/` を探索。
3. Loader Layer が3ファイル＋`holidays.csv`（任意）を読み込み、不正行は WARN+skip。
4. Matching Layer が `staff_id × date` キーで合流し `MatchedCase` リストを生成。
5. Detection Layer が 10 ルールを順に適用し `AnomalyFinding` を発行。
6. Scoring Layer が 3 軸スコア → 高/中/低 に丸め、例外条件（A-04降格／A-05据え置き）を適用。
7. Masking Layer が `--mask-names` 有効時に `staff_name`／`assignee_name` をイニシャル化。
8. Output Layer がサマリ・チェックリスト・通知ファイル・JSON・skipped_records.csv を出力。
9. 終了コード 0 で完了、処理時間を末尾表示。

---

## 3. コンポーネント構成

### 3.1 モジュール一覧

| # | モジュール名 | 責務 | 主な依存 |
|---|---|---|---|
| 1 | `cli` | 引数解析、サブコマンド振り分け、`--data-class` ガード、`--as-of-date` 解決。`config` を呼び出して締め日・営業日・対応期限を取得 | argparse（標準）、`config` |
| 2 | `config` | パス規約・締め日算出・営業日判定・M-5 対応期限算出の共通ロジック（**純粋計算ユーティリティ**、`cli` にも `HolidayCalendarLoader` にも依存しない。R3対応：休日データは呼出側で `HolidayCalendarLoader` を使って読み込み、`HolidayCalendar` オブジェクトとして `config` 関数に **注入** する構造に寄せる） | （依存なし。`HolidayCalendar` 型のみを引数として受理） |
| 3 | `StaffPunchLoader` | `timesheet.csv` を打刻イベント行モデルで読み込む（1行=1出退勤ペア） | csv, datetime |
| 4 | `LeaveRequestLoader` | `applications.csv` を読み込み、`type`（leave/overtime）・`status` を正規化 | csv |
| 5 | `ShiftPlanLoader` | `shifts.csv` を読み込み、シフト跨ぎを翌日日付で保持 | csv, datetime |
| 6 | `HolidayCalendarLoader` | `holidays.csv`（任意）を読み込み、営業日判定 API を提供 | csv |
| 7 | `ClientApprovalMatcher` | `staff_id × date` で punch / leave / overtime / shift を合流し `MatchedCase` を生成。派遣先承認ステータスを `approver_status` として付与 | 3〜6 |
| 8 | `AnomalyRuleEngine` | ルールクラスの配列を順次適用。各 `Rule` は `detect(matched_case) -> list[AnomalyFinding]` を実装 | 7 |
| 9 | `rules/`（A-01〜A-10） | 各異常パターンのルール実装。1ファイル=1ルール | 8 |
| 10 | `SeverityScorer` | 3軸スコア表に基づき重要度を確定。複数パターン該当時は最大値、例外条件も適用 | 8 |
| 11 | `RecommendationComposer` | 推奨アクション文を生成（既定はルール辞書、MAY-1 で LLM オーバーライド） | 10 |
| 12 | `PiiMaskingFilter` | `--mask-names` 有効時に氏名イニシャル化 | 10 |
| 13 | `DispatchCoordinatorReport` | 派遣元コーディネーター（`assignee_id`）別グルーピング＋整形 | 10〜12 |
| 14 | `ClientSiteReport` | 派遣先事業所（`client_id`＋`client_site`）別グルーピング＋整形 | 10〜12 |
| 15 | `SummaryRenderer` | ヘッダー・強調サマリ・カラー出力（S-4） | 10 |
| 16 | `NotificationWriter` | `output/notifications/{assignee_id}_{assignee_slug}.txt` 書き出し | 13 |
| 17 | `JsonResultWriter` | `output/result_{YYYYMM}.json`（S-1） | 10 |
| 18 | `SkippedRecordReporter` | ロード時スキップの集計＋ `output/skipped_records.csv` 出力 | 3〜6 |
| 19 | `SampleDataGenerator` | ダミーCSV自動生成（S-3）。`generate-samples` サブコマンドで起動 | csv, random |

### 3.2 主要コンポーネントの入出力インタフェース（論理レベル）

`StaffPunchLoader`
- 入力: `samples/{YYYYMM}/timesheet.csv` のパス
- 出力: `list[PunchRecord]`（`record_id, staff_id, staff_name, client_id, client_name, client_site, date, clock_in, clock_out, break_minutes, assignee_id, assignee_name`）
- 副作用: 行不正時に `SkippedRecordReporter` に登録
- **`client_site` 欠損時の扱い（R3対応）**: `client_site` は `timesheet.csv` の必須列（§5.1 参照）。値が空または欠損の場合は WARN + `client_site="unknown"` にフォールバックして行は保持する（skip ではない。3者ワークフロー上の「派遣先事業所別出力」を成立させるため）。該当 skip/fallback は `SkippedRecordReporter` に `reason="client_site missing, filled as unknown"` で登録。

`ClientApprovalMatcher`
- 入力: `PunchRecord[]`, `LeaveApplication[]`, `ShiftPlan[]`
- 出力: `list[MatchedCase]`（1件 = 同一 `staff_id × date` に属する打刻・申請・シフト・派遣先承認ステータスの束）
- 備考: A-05 対応のため、1 `MatchedCase` は複数 `PunchRecord` を保持しうる
- **approver_statuses 仕様**（代表値化しない）:
  - `MatchedCase.approver_statuses: list[str]` に当該 `staff_id × date` に属する申請の status 集合を原形保持する（例: `["pending", "approved"]`）。
  - 用途は **表示専用**。ソート済み `" / "` 結合で出力（例: `"approved / pending"`）。空集合時は `"-"`。
  - **A-07 判定には使用しない**。A-07 は個別申請レコード（`application_id` 単位）で `applied_at` を参照して判定する（§7.1 参照）。`approver_statuses` を in 判定に使うと、同一日の複数申請の `applied_at` が異なるケースを取り違える。
  - **内外I/F二層定義**: 内部中間データは `approver_statuses: list[str]`。外部出力（JSON・通知・チェックリスト）は後方互換のため `approver_status: str`（上記 `" / "` 結合済み文字列、空集合時は `"-"`）を保持する。**表示用 join ロジックは出力層のみが所有** し、ルール・Scorer からは参照させない。
  - 旧仕様の単一代表値 `approver_status`（list の最頻値を代表値化する方式）は廃止。

`AnomalyRuleEngine`
- 入力: `MatchedCase[]`, `as_of_date`, `HolidayCalendar`
- 出力: `list[AnomalyFinding]`（`record_id?, application_id?, scope, day_key, pattern_id, pattern_name, staff_id, date, client_id, client_site, assignee_id, approver_statuses, raw_context`）
- 仕様: ルールごとに独立適用。1 `MatchedCase` から複数 Finding が出うる（後段 `SeverityScorer` で重複集約）
- **scope 仕様**:
  - `scope="record"`: 個別打刻行で検知するルール（A-01/A-02/A-03/A-04/A-09/A-10）。`record_id` を必須保持。
  - `scope="day"`: 日次（staff×date）で検知するルール（A-05/A-06/A-08）。`record_id` は `None`、`day_key = f"{staff_id}_{date:%Y-%m-%d}"` を識別子とする。
  - `scope="application"`: 個別申請行で検知するルール（**A-07 専用**）。`application_id` を必須保持し、同一 `staff_id × date` に複数 pending 申請がある場合でも申請単位で別 Finding を発行する（R3対応：日集約での滞留欠落を防ぐため day 集約から除外）。
- **`finding_key` 仕様（正式な集約キー、prefix 名前空間で衝突排除）**:
  - `finding_key` は必ず `scope` prefix 付きで生成する:
    - `scope="record"` → `f"record:{record_id}"`
    - `scope="day"` → `f"day:{day_key}"`
    - `scope="application"` → `f"application:{application_id}"`
  - `AnomalyFinding` の派生プロパティとして保持（`SeverityScorer` は `finding.finding_key` 単一属性のみを集約に使う）。
  - 下流の `SeverityScorer` / `DispatchCoordinatorReport` / `ClientSiteReport` / `JsonResultWriter` / `NotificationWriter` はすべて `finding_key` で貫通させ、prefix による名前空間分離で scope を跨いだ衝突は設計的に排除される（R3対応：書式差依存の衝突回避を廃止）。

`SeverityScorer`
- 入力: `AnomalyFinding[]`, `case_index: dict[day_key, MatchedCase]`（例外条件判定用の参照インデックス）
- 出力: `list[ScoredFinding]`（`AnomalyFinding + severity + score_breakdown{payroll, billing, legal} + recommended_action`）
- 仕様:
  - **例外条件（A-04降格／A-05据え置き）は `case_index[finding.day_key]` 経由で `MatchedCase` を参照して評価** する。Finding 単独では shift span 等の情報を持たないため、`AnomalyRuleEngine` 実行時の `MatchedCase` 配列から `day_key` をキーに dict 化したものを Scorer に渡す（`§7.2` の疑似コード参照）。
  - 同一 `finding_key` に複数 Finding が集まった場合、**最高 severity を採用し、`pattern_id` は主パターン1件 + `additional_patterns[]` に併記** する（§7.2 参照）。

`DispatchCoordinatorReport` / `NotificationWriter`
- 入力: `ScoredFinding[]`（担当者別にグルーピング済み）, `response_deadline: date`（§7.4 で算出した M-5 対応期限。`config` モジュールが `as_of_date` と `holidays.csv` から決定）
- 出力: テキストファイル。命名規則は §5.3 参照
- 仕様:
  - 通知本文のヘッダに `response_deadline`（例: `対応期限: 2026-04-28（火）`）を必須表示する。
  - `assignee_slug` が空文字化した場合は `unknown` にフォールバック。

### 3.3 分離の根拠
- **Loader と Matcher を分離** する理由: CSV スキーマ変更時の影響をローダーだけに閉じ込め、ルールエンジンを安定化させるため。
- **Rule ごとにクラス化** する理由: 要件 §5「異常検知ルールはモジュール化し、ルール追加が容易な構造」を直接満たすため。新規パターン追加は `rules/` 配下にファイルを1つ足し、`AnomalyRuleEngine` のルールリストに登録するだけで完結する。
- **Masking を独立層に** する理由: 実データ投入時（§5.1）の防波堤として、出力直前に一元的に氏名マスクを掛けるため。ルール本体やローダーには氏名依存ロジックを持たせない。
- **通知・JSON・チェックリストを別モジュールに** する理由: セミナーで「通知だけ見せる」「JSON だけ出す」など見せ方を柔軟に切り替えたいため。

---

## 4. データフロー

### 4.1 3者ワークフロー視点でのデータフロー

本ツールは派遣元担当者が主ユーザーだが、**出力は派遣先承認者・スタッフへの差戻し起票情報** として使われる。この 3 者へのデータ流路を設計フロー上で明示する。

```
[派遣管理SaaS側マスタ]         [スタッフ]             [派遣先 承認者]
  assignee_id 紐付け         打刻（timesheet.csv）   approve/reject
  client_id 紐付け           申請（applications.csv）  （applications.csv の status に反映）
        │                          │                          │
        └────────────┬─────────────┴────────────┬─────────────┘
                     ▼                          ▼
              [samples/YYYYMM/ に CSV として集約]
                     │
                     ▼
            ┌─────────────────────┐
            │ Loader & Matcher    │
            │ （3者のデータを合流） │
            └─────────┬───────────┘
                      ▼
            ┌─────────────────────┐
            │ AnomalyRuleEngine   │
            │ + SeverityScorer    │
            └─────────┬───────────┘
                      ▼
          ┌───────────┴────────────────────────┐
          ▼                                    ▼
  [派遣元コーディネーター別出力]      [派遣先事業所別出力]
  NotificationWriter                  ClientSiteReport
  → 担当者が担当スタッフに確認         → 派遣先承認者への再承認依頼資料
  → スタッフに打刻訂正依頼             → 承認待ち滞留（A-07）の可視化
```

- **派遣元視点のフロー**: `DispatchCoordinatorReport` → `NotificationWriter` が担当者ごとの対応リストを出力。
- **派遣先視点のフロー**: `ClientSiteReport` が事業所別に「承認待ち滞留」「未承認 + 打刻不備」を括って出力し、派遣先承認者への連絡資料に直接使える粒度にする。
- **スタッフ視点のフロー**: 各 Finding に `staff_id` と `recommended_action`（打刻訂正／申請訂正）が含まれ、派遣元担当が差戻し起票するための最小情報を保持する。

### 4.2 中間データ形式

**サマリ分母の不変条件（最優先）**:

- `total_records` = `timesheet.csv` の有効行数（row count、`SkippedRecordReporter` 登録済みの skip 行を除く）。
- サマリ表示「全 N 件中 M 件検知」は `N = total_records`（= `PunchRecord[]` の length）を基準とする。
- `MatchedCase` 件数（staff-day 粒度）は **分母に使用しない**。`MatchedCase` は集約単位であり `total_records` とは一致しない。
- **`--assignee` / `--client` フィルタ時の分母仕様（R3対応）**: フィルタ適用時は **「フィルタ後分母に再計算」** する（`total_records_filtered` = フィルタ条件に一致する `PunchRecord[]` の length）。出力見出しには `全 N 件中 M 件検知（assignee=U-001 で絞込）` のように絞込条件と分母再計算の旨を明示する。JSON `meta.filters` にも適用済みフィルタを記録（§10.1 の meta 拡張参照）。

**中間データテーブル**:

| 中間データ | 生成元 | 主要フィールド |
|---|---|---|
| `PunchRecord` | `StaffPunchLoader` | record_id, staff_id, date, clock_in, clock_out, break_minutes, assignee_id, client_id, client_name, **client_site**（必須、欠損時 `unknown` フォールバック） |
| `LeaveApplication` | `LeaveRequestLoader` | application_id, staff_id, date, type, status, applied_at, approved_at |
| `ShiftPlan` | `ShiftPlanLoader` | staff_id, date, scheduled_start, scheduled_end |
| `MatchedCase` | `ClientApprovalMatcher` | staff_id, date, punches[], leaves[], overtimes[], shift, **approver_statuses**（派遣先承認ステータス集合、§3.2 参照） |
| `AnomalyFinding` | `AnomalyRuleEngine` | record_id?, **scope**（`record` / `day`）, **day_key**（`{staff_id}_{date}`、scope=day 時の識別子）, pattern_id, pattern_name, staff_id, staff_name, client_id, client_name, client_site, assignee_id, assignee_name, approver_statuses, raw_context |
| `ScoredFinding` | `SeverityScorer` | AnomalyFinding の全フィールド + severity（high/medium/low）+ score_breakdown + recommended_action |

### 4.3 エラー時の分岐フロー

| エラー種別 | 分岐 |
|---|---|
| `--data-class` 未指定 | 即 exit (code=2)。ロード処理に到達しない |
| `samples/{YYYYMM}/` ディレクトリ不在 | ERROR 表示後 exit (code=1) |
| `timesheet.csv` 不在 | ERROR、exit (code=1)（必須ファイル） |
| `applications.csv` 不在 | WARN、`applications` 依存パターン（**A-06 休暇分岐／A-06 残業分岐／A-07**）を skip して処理継続。A-06 残業分岐は `shifts.csv` の有無に関わらず申請照合が不能になるため skip（`shifts.csv` 欠損時の 8h fallback は `applications.csv` がある場合にのみ適用、§7.1 参照） |
| `shifts.csv` 不在 | WARN、`shifts` 依存パターン（A-08・A-09）を skip。ただし **A-06 残業分岐は `scheduled_hours = 8h` の fallback で実行継続**（§7.1 参照） |
| CSV 行の列欠損／日付パース失敗 | WARN、行単位 skip。`SkippedRecordReporter` に理由付きで登録 |
| LLM 呼出失敗（MAY-1） | ルール辞書にフォールバック。MUST 機能は成立継続 |

---

## 5. データモデル / スキーマ

### 5.1 入力 CSV スキーマ
要件定義書 §7.3 に準拠。本設計書では追加で **正規化後のメモリ内表現** を規定する。

- `date` は Python `datetime.date`、`clock_in`/`clock_out`/`applied_at`/`approved_at` は `datetime.datetime`（JST naïve で扱い、TZ 変換は行わない）。
- **入力 datetime は尊重する**。`clock_out < clock_in` になった場合は **自動補正せず WARN + skip**（`SkippedRecordReporter` に `reason="clock_out before clock_in"` で登録）。シフト跨ぎのケースは `shifts.csv` 側で明示日付を持たせて入力することで表現する（暗黙の翌日補正は廃止、誤検知防止のため）。
- `break_minutes` は `int >= 0`。負値は WARN + skip。
- **`client_site` 列（`timesheet.csv` 必須、R3対応）**: 派遣先事業所（`ClientSiteReport` の出力起点）。欠損時は WARN + `client_site="unknown"` にフォールバックして保持（行 skip ではない）。`shifts.csv` / `applications.csv` 側には `client_site` 列は持たせず、`staff_id × date` キーで `PunchRecord.client_site` を伝播する。
- **`scheduled_start` / `scheduled_end`（`shifts.csv`）の解釈**: 「拘束時間（休憩を含む）」として扱う。A-06 残業分岐の `threshold` は `shift_scheduled_hours - 1h休憩` で実働時間換算する（§7.1 A-06 参照）。

### 5.2 ディレクトリ構成（付録Aに対応）

```
ai-demos/03_attendance-check/
├── docs/
│   ├── 01_requirements.md
│   └── 02_design.md                    # 本書
├── src/
│   ├── main.py                         # CLI エントリ
│   ├── cli.py
│   ├── config.py
│   ├── loaders/
│   │   ├── staff_punch_loader.py
│   │   ├── leave_request_loader.py
│   │   ├── shift_plan_loader.py
│   │   └── holiday_calendar_loader.py
│   ├── matching/
│   │   └── client_approval_matcher.py
│   ├── detection/
│   │   ├── anomaly_rule_engine.py
│   │   └── rules/
│   │       ├── a01_clock_out_missing.py
│   │       ├── a02_clock_in_missing.py
│   │       ├── a03_break_insufficient.py
│   │       ├── a04_continuous_24h.py
│   │       ├── a05_multi_clock.py
│   │       ├── a06_application_mismatch.py
│   │       ├── a07_approval_pending_stale.py
│   │       ├── a08_night_unscheduled.py
│   │       ├── a09_shift_deviation.py
│   │       └── a10_duplicate_punch.py
│   ├── scoring/
│   │   └── severity_scorer.py
│   ├── masking/
│   │   └── pii_masking_filter.py
│   ├── output/
│   │   ├── summary_renderer.py
│   │   ├── dispatch_coordinator_report.py
│   │   ├── client_site_report.py
│   │   ├── notification_writer.py
│   │   ├── json_result_writer.py
│   │   └── skipped_record_reporter.py
│   ├── recommendation/
│   │   └── recommendation_composer.py
│   └── generate_samples/
│       └── sample_data_generator.py
├── samples/
│   └── 202604/
│       ├── timesheet.csv
│       ├── applications.csv
│       ├── shifts.csv
│       └── holidays.csv                # 任意
└── output/
    ├── notifications/
    │   ├── U-001_sato.txt
    │   └── U-002_takahashi.txt
    ├── checklist/
    │   ├── by_coordinator_202604.txt
    │   └── by_client_site_202604.txt
    ├── result_202604.json
    └── skipped_records.csv
```

### 5.3 出力命名規則
| 出力 | パス | 命名規則 |
|---|---|---|
| コーディネーター別通知 | `output/notifications/{assignee_id}_{assignee_slug}.txt` | `assignee_slug` は `[A-Za-z0-9-]` に限定。空文字なら `unknown`。例: `U-999_unknown.txt` |
| コーディネーター別チェックリスト | `output/checklist/by_coordinator_{YYYYMM}.txt` | 月単位で1ファイル |
| 派遣先事業所別チェックリスト | `output/checklist/by_client_site_{YYYYMM}.txt` | 月単位で1ファイル |
| JSON 結果 | `output/result_{YYYYMM}.json` | S-1 |
| スキップ監査 | `output/skipped_records.csv` | 毎実行時に上書き |

### 5.4 設定ファイル
- **MUST 範囲では設定ファイルを持たない**（最小実装方針）。
- 重要度スコア表（§7.2）と推奨アクション文のデフォルト辞書はソースコード内定数として保持する。YAML 外出しは将来拡張として §10.3 で言及するに留める。

---

## 6. インタフェース設計

### 6.1 CLI 体系

サブコマンド2つ：

| サブコマンド | 用途 |
|---|---|
| `check` | 勤怠チェック本処理（MUST 全機能） |
| `generate-samples` | ダミーCSV生成（S-3） |

`check` サブコマンドの引数：

| 引数 | 必須 | 型 | 既定値 | 説明 |
|---|---|---|---|---|
| `--month` | ○ | `YYYY-MM` | なし | 対象月。`samples/{YYYYMM}/` を探索 |
| `--as-of-date` | × | `YYYY-MM-DD` | 月末締め日 or 実行 JST 日付の早い方 | 判定基準日（A-07 等）。デモ再現性のため固定推奨 |
| `--data-class` | ○ | `dummy` / `real` | なし（未指定は即エラー終了） | データ分類ガード |
| `--allow-real-data` | `--data-class real` 時のみ必須 | flag | false | 二段ガード |
| `--mask-names` / `--no-mask-names` | × | flag | `real` 時 ON / `dummy` 時 OFF | 氏名イニシャル化。**`--data-class real` のときに `--no-mask-names` を使う場合は、追加で `--confirm-unmask-real` フラグが必須**（R3対応：PII平文出力の明示同意ゲート。未付与時は exit 2） |
| `--assignee` | × | string | なし | S-2: 担当者絞り込み（名前または assignee_id） |
| `--client` | × | string | なし | S-2: 案件絞り込み（`client_name` または `client_id`） |
| `--llm` | × | flag | false | MAY-1: 推奨アクション文を LLM で生成 |
| `--no-color` | × | flag | false | S-4: カラー出力無効化 |

`generate-samples` サブコマンドの引数：

| 引数 | 必須 | 型 | 既定値 | 説明 |
|---|---|---|---|---|
| `--month` | ○ | `YYYY-MM` | なし | 出力先 `samples/{YYYYMM}/` を決定 |
| `--data-class` | ○ | `dummy` のみ許容 | なし | 実データ生成禁止のためダミー以外は即エラー終了（セーフガード） |
| `--count` | × | int | 50 | スタッフ数（×営業日数で timesheet 行数が決定） |
| `--seed` | × | int | 42 | 乱数シード。同一 seed で同一出力を保証（再現性担保） |
| `--anomaly-rate` | × | float (0.0〜1.0) | 0.15 | 異常パターン混入率。セミナー演出用 |
| `--overwrite` | × | flag | false | 既存 `samples/{YYYYMM}/` がある場合、`--overwrite` 無指定は FATAL（誤上書き防止） |

### 6.2 ファイル I/O 規約
- 入力は `samples/{YYYYMM}/` 配下のみ読み取り。それ以外のパスは受け付けない（誤読み込み防止）。
- 出力は `output/` 配下のみ書き込み。実行時に不在なら作成する。
- 通知ファイルは **追記ではなく毎回上書き**（デモ再現性のため）。
- **出力順序（ソートキー）**: 全ての一覧出力（通知／チェックリスト／JSON／stdout サマリ）は `severity desc, date asc, staff_id asc, pattern_id asc` の固定順で並べ、実行間の再現性を担保する。

### 6.3 終了コード

| コード | 意味 |
|---|---|
| 0 | 正常終了（検知0件でも 0） |
| 1 | 致命的エラー（`samples/{YYYYMM}/` 不在、`timesheet.csv` 不在など） |
| 2 | 引数エラー（`--data-class` 未指定、`real` + `--allow-real-data` 欠落など） |

### 6.4 Claude Code スラッシュコマンド
`/attendance-check` は `python src/main.py check` に引数を素通しする薄いラッパ。実装詳細は技術仕様書に委ねる。

---

## 7. アルゴリズム設計

### 7.1 異常検知ルール（A-01〜A-10）実装方式

各ルールは共通インタフェースを実装する（疑似コード）：

```
class AnomalyRule:
    pattern_id: str        # "A-01" 等
    pattern_name: str
    def detect(case: MatchedCase, ctx: DetectionContext) -> list[AnomalyFinding]
```

`DetectionContext` は `as_of_date`, `HolidayCalendar`, shifts 欠損フラグを保持する共有オブジェクト。

ルール個別実装方針：

| ID | 実装ポイント |
|---|---|
| A-01 | `punch.clock_in is not None and punch.clock_out is None` |
| A-02 | `punch.clock_in is None and punch.clock_out is not None` |
| A-03 | `worked_minutes = (clock_out - clock_in) - break_minutes`。`6h < worked <= 8h and break<45` または `worked > 8h and break<60` |
| A-04 | `clock_out - clock_in >= 24h`。シフト跨ぎ判定は `shifts.csv` の `scheduled_end - scheduled_start` を照合し、24h以上ならスコア降格対象として `raw_context["shift_span_hours"]` にメモ |
| A-05 | 同一 `MatchedCase` 内の `punches` で `clock_in` と `clock_out` が両方埋まった行が2以上 |
| A-06 | 休暇分岐: `applications.csv` 読込済みが前提。`leave.status == approved and len(punches) > 0`。`applications.csv` 欠損時はこの分岐を skip。残業分岐: 実働が `threshold + 30min` を超過した際に起動。`threshold = shift_scheduled_hours - 1h休憩`（`shifts.csv` ありの場合）または `8h`（`shifts.csv` 欠損時の fallback）。`overtime` 申請の status を `approved > pending > rejected` 順で採用し、`rejected` / 行なしを「申請なし」とする。`applications.csv` 欠損時はこの分岐も skip（fallback 対象は `shifts` 欠損のみ） |
| A-07 | **申請行単位（`application_id` 粒度）で判定・Finding 発行**（R3対応：`scope="application"`、`finding_key=f"application:{application_id}"`）。`status == pending` の `leave` / `overtime` 申請 1 行ごとに `business_days_between(applied_at.date(), as_of_date) >= 3` を評価し、条件成立ごとに Finding を1件発行する。`MatchedCase.approver_statuses`（集合）は表示専用であり判定には **使用しない**。Finding の `day_key` は `{staff_id}_{date}`、`application_id` は必須フィールドとして保持（`raw_context["application_id"]` にも併記）。**同一 staff_id × date に複数 pending 申請がある場合でも申請単位で別 Finding として残る**（day 集約で潰れない、R3 Critical 1 対応） |
| A-08 | 22:00〜翌05:00 の打刻が `shift.scheduled_start 〜 shift.scheduled_end` の範囲外 |
| A-09 | `abs(clock_in - scheduled_start) > 60min or abs(clock_out - scheduled_end) > 60min` |
| A-10 | 同一種別（in/out）で5分以内の打刻が複数 |

ルール追加容易性：新ルールは `rules/axx_*.py` を作成し `AnomalyRuleEngine` の `RULES = [A01(), A02(), ...]` リストに追記するだけ。

### 7.2 重要度判定（SeverityScorer）

- 3軸スコア表（`payroll`, `billing`, `legal`）をソース内定数として持ち、パターン ID をキーに引く。
- 各軸は `3=高 / 2=中 / 1=低 / 0=影響なし`。
- **採用スコア = max(payroll, billing, legal)** → `3→high / 2→medium / 1→low`。
- 例外条件の適用順（いずれも `case_index[finding.day_key]` 経由で `MatchedCase` を参照）：
  1. A-04: `case.shift.span_hours >= 24h` のとき `high → medium` に降格
  2. A-05: `case.within_scheduled(case.client_id) == True` のとき `low` に据え置き（誤検知抑制）
  3. A-08: 予定時間内に収まる場合はそもそも Finding を発行しない（ルール側で弾く）
- **同一 `finding_key` に複数 Finding が集約された場合**: 最高 severity を採用し、主パターン1件 + `additional_patterns: list[str]`（例: `["A-06","A-09"]`）に併記（JSON/通知で同様に保持）。集約キーは scope により prefix 付き `record:{id}` / `day:{key}` / `application:{id}` を使用（§3.2 参照、R3対応で prefix 名前空間に統一）。

疑似コード：

```
def score_all(findings: list[AnomalyFinding],
              case_index: dict[str, MatchedCase]) -> list[ScoredFinding]:
    # 1. finding_key で集約
    buckets: dict[str, list[AnomalyFinding]] = group_by(findings,
                                                        key=lambda f: f.finding_key)
    scored: list[ScoredFinding] = []
    for key, group in buckets.items():
        case = case_index[group[0].day_key]   # 例外条件評価用（record / day / application の全 scope で day_key は必ず埋まる）
        per_finding_scores = [resolve_score(f, case) for f in group]
        max_score = max(per_finding_scores)
        severity = {3:"high", 2:"medium", 1:"low"}[max_score]
        primary = pick_primary(group)         # severity 最大、同値なら pattern_id 辞書順
        scored.append(ScoredFinding(
            finding_key=key,
            primary=primary,
            additional_patterns=[f.pattern_id for f in group if f is not primary],
            severity=severity,
            score_breakdown=SCORE_TABLE[primary.pattern_id],
        ))
    return scored

def resolve_score(finding: AnomalyFinding, case: MatchedCase) -> int:
    base = SCORE_TABLE[finding.pattern_id]   # {"payroll":3,"billing":3,"legal":2}
    if finding.pattern_id == "A-04" and case.shift and case.shift.span_hours >= 24:
        return 2
    if finding.pattern_id == "A-05" and case.within_scheduled(case.client_id):
        return 1
    return max(base.values())
```

### 7.3 営業日計算
`HolidayCalendar.business_days_between(start, end)` は [start, end] を半開区間 `(start, end]` として差分を取る。月をまたぐ場合（A-07 の `applied_at` が前月のケース）も同一式で処理。`holidays.csv` が無い場合は土日のみを非営業日扱い。

### 7.4 計算例（要件 §7 の数値例を設計観点で再定義）

- **A-07 の3営業日判定**: `applied_at=2026-04-20(月), as_of_date=2026-04-28(火)`。営業日は 21,22,23（木）,24(金),27(月),28(火) の6日 → 3営業日以上経過で検知。
- **M-5 対応期限（`response_deadline`）**: 締め日 2026-04-30（木）の2営業日前 → 28（火）。金曜祝日等あれば `holidays.csv` を参照して逆算。
  - **算出責務（R3対応：真実源を `--month` に変更）**: `config.resolve_response_deadline(target_month, holidays) -> date` が単一の真実源。`target_month`（`--month` 引数の `YYYY-MM`）から月末締め日を導出し、そこから営業日ベースで2営業日前を逆算する。`as_of_date` は「判定基準日（今日時点）」であり対応期限の起点ではないため、引数から外す（`as_of_date` が対象月からズレても `response_deadline` は常に対象月末基準に固定）。
  - **データ受け渡し経路**: `cli` → `DispatchCoordinatorReport` / `ClientSiteReport` / `NotificationWriter` / `JsonResultWriter` の全ての出力層へ `response_deadline` を必須引数として引き渡す。各出力のヘッダ／JSON `meta.response_deadline` に反映され、派遣元担当者が即座に対応期限を把握できる粒度にする。

---

## 8. エラーハンドリング・異常系設計

### 8.1 エラー分類

| レベル | 例 | 挙動 |
|---|---|---|
| FATAL | `--data-class` 未指定、`samples/{YYYYMM}/` 不在、`timesheet.csv` 不在 | stderr にメッセージ、即 exit（コード 1 or 2） |
| WARN | 個別行の列欠損、日付パース失敗、`applications.csv` / `shifts.csv` 不在 | stderr に WARN、当該行/パターンを skip、処理継続 |
| INFO | 検知0件、LLM フォールバック | stdout にメッセージ、正常終了 |

### 8.2 スキップ記録の監査性
- WARN で skip した行は **全て `SkippedRecordReporter` に登録** し、`output/skipped_records.csv`（列: `file, line_no, staff_id?, date?, reason`）に書き出す。
- 実行末尾のサマリに `スキップ件数: N件（内訳: 日付不正=M件 / 列欠損=K件 / ...）` を表示。

### 8.3 LLM フォールバック（MAY-1）
- `--llm` 有効時に LLM 呼出が失敗した場合、`RecommendationComposer` は **ルール辞書 `DEFAULT_ACTIONS[pattern_id]`** に自動フォールバック。
- フォールバック発生時は WARN を1回だけ表示（多数回の場合も1回に集約）。
- MUST 機能（M-1〜M-6）は LLM 不使用でも全て成立する。

### 8.4 回復可能／不可能の判断基準
- **回復不可能**: 入力の存在自体が崩れている（ディレクトリ不在、timesheet.csv 不在、引数矛盾） → FATAL 終了。
- **回復可能**: 個別レコードの不整合、オプショナルファイルの不在 → WARN ＋ skip で継続（検知精度は落ちるがデモは成立）。

---

## 9. セキュリティ・プライバシー設計

### 9.1 PII マスキング
- 対象フィールド: `staff_name`, `assignee_name`。
- 方式: `PiiMaskingFilter` が `ScoredFinding` 配列を出力層直前でインプレース変換し、氏名を **先頭1文字 + "."**（例: 鈴木太郎 → 鈴.）にイニシャル化。
- `--data-class real` 時は既定 ON、`--no-mask-names` で明示解除可。ただし **`real` + `--no-mask-names` の組合せは `--confirm-unmask-real` フラグが無い限り exit 2（R3対応：追加同意ゲート）**。`--data-class dummy` 時は既定 OFF。
- マスキングは **表示用のみ**。JSON 出力の `staff_id` 等の ID フィールドはマスクしない（突合性確保のため）。

### 9.2 ファイル出力先の制限
- 出力は `output/` 配下のみ。`os.path.realpath` で検証し、シンボリックリンクで抜け出そうとした場合は FATAL。
- 通知ファイル名に **生の個人名を含めない**（`assignee_slug` は英数ハイフンのみ、日本語・記号は `unknown` フォールバック）。

### 9.3 実データ投入禁止の担保
- §5.1 の二段ガードを `cli` モジュールの引数パース直後に検証。
  - `--data-class` 未指定 → exit 2
  - `--data-class real` かつ `--allow-real-data` なし → exit 2
  - `--data-class dummy` のときは `--allow-real-data` があっても無視（dummy 優先）
  - **`--data-class real` かつ `--no-mask-names` かつ `--confirm-unmask-real` なし → exit 2**（R3対応：PII平文出力の明示同意ゲート。`real` データのマスク解除は意図せず設定で起こらないよう、追加フラグでの明示同意を必須化）
- 起動時に「本ツールはダミーデータ前提のモックです」旨を標準出力へ表示（`--data-class real` 時は文言を切り替え）。

### 9.4 免責表示
- 標準出力ヘッダーに「デモ用モック／実運用品質を担保しない」旨を 1 行表示。

---

## 10. 観測可能性・運用設計

### 10.1 ログ出力方針
- 標準出力: セミナー映え優先の進捗表示（`[1/3] スタッフ打刻データ読み込み中...`）。S-4 有効時は重要度に応じた ANSI カラー。
- 標準エラー: WARN/FATAL のみ。フォーマットは `[WARN] {module}: {message}` / `[ERROR] {module}: {message}`。
- 保存: 実行ログファイルは持たない（モック方針）。監査性は `output/skipped_records.csv` で担保。
- **JSON 実行メタ（R3対応）**: `JsonResultWriter` の出力 JSON 先頭に `meta` オブジェクトを置き、追跡性を確保する。必須フィールド:
  - `meta.month`（`--month` 値）
  - `meta.as_of_date`（判定基準日）
  - `meta.response_deadline`（M-5 対応期限、§7.4）
  - `meta.filters`（`{assignee?: str, client?: str}`、未指定時は空オブジェクト）
  - `meta.data_class`（`dummy` / `real`）
  - `meta.skipped_summary`（`{total: N, by_reason: {reason: count}}`）
  - `meta.rule_skipped`（ファイル欠損で skip したルール一覧、例: `[{"pattern_id": "A-08", "reason": "shifts.csv missing"}]`）

### 10.2 デモ時の見せ方との整合
- サマリ表示が 3 秒以内（要件 §8）: 1,000件規模で標準ライブラリのみなら十分到達可能な設計。パフォーマンス計測用の簡易タイマを `main.py` 末尾に実装し、「完了: 処理時間 X.X秒」を表示。
- 「AIが拾った N 件」の演者口上（要件 §1.1）は `SummaryRenderer` のヘッダー定型文として保持。実体はルールエンジン。

### 10.3 将来拡張への接続点
- **ルール追加**: `rules/` にファイル追加 + `RULES` リストへの登録のみ。エンジン本体は変更不要。
- **設定ファイル化**: 重要度スコア表を YAML 外出しする場合、`SeverityScorer` のコンストラクタ引数として注入できる構造を残す（MUST 範囲では内蔵定数）。
- **36協定・抵触日管理**（§4.2 スコープ外）: `AnomalyRuleEngine` に新ルール群として追加可能な余地を残す。月またぎ集計が必要になるため、`MatchedCase` を `MonthlyAggregate` に拡張する設計を将来検討。
- **実 SaaS 連携**: 現行の Loader Layer を「CSV 実装」として抽象化し、将来的に「API 実装」を差し替え可能にする（本フェーズでは未実装、命名のみ意識）。
- **Slack/メール通知（MAY-4）**: `NotificationWriter` と同インタフェースで `SlackNotificationSender` を追加できる構造を維持。

---

## 付録A. 想定ディレクトリ構成
§5.2 を参照。

## 付録B. 用語定義（要件定義書から継承）
- **ルールエンジン**: 実装上の検知ロジック主体。A-01〜A-10 の決定的判定を担う。
- **AI**: セミナー演者口上における対外表現。実装上はルールエンジンの出力を指す。
- **LLM**: MAY-1 の外部LLM連携機能に限定した用語。
- **3者ワークフロー**: 派遣元担当者／派遣先承認者／スタッフ、の勤怠確定プロセス。
- **判定基準日（as-of-date）**: A-07 など時間経過判定の「現在日」。`--as-of-date` で固定可能。
- **派遣先事業所（client_site）**: `client_id` 配下の具体的な就業場所。JSON出力の任意フィールド。

## 付録C. 設計上の決定記録

| # | 決定事項 | 選択肢 | 選択理由 |
|---|---|---|---|
| C-1 | ルールエンジンをクラス配列で構成 | (a) if-elif 連鎖 (b) クラス配列 (c) ルール外部DSL | (b) を採用。要件 §5「ルール追加容易性」を直接満たし、(c) は過剰設計 |
| C-2 | `MatchedCase` を `staff_id × date` 粒度に | (a) 打刻1行ごと (b) 日次束ね | (b) を採用。A-05（複数出退勤）・A-06（申請突合）は日次束ねでないと判定不能 |
| C-3 | Masking を出力直前の独立層に | (a) Loader で先にマスク (b) 出力直前 (c) 各 Writer で個別に | (b) を採用。ルール本体を氏名非依存に保ち、一元管理 |
| C-4 | LLM はオプトイン（`--llm` 明示） | (a) 既定ON (b) 既定OFF | (b) を採用。再現性と「オフラインでも完結」要件（MAY-1）を優先 |
| C-5 | 通知ファイル名を `assignee_id_slug.txt` 形式に | (a) 名前ベース (b) ID+slug (c) ID のみ | (b) を採用。可読性と PII 防波堤の両立。slug 空文字時は `unknown` にフォールバック |
| C-6 | 設定ファイル外出しを見送り | (a) YAML/JSON 外出し (b) コード内定数 | (b) を採用。最小実装方針。将来拡張点として §10.3 に接続点を残す |
| C-7 | 派遣先事業所別と担当者別の**両方**でチェックリスト出力 | (a) 担当者別のみ (b) 両方 | (b) を採用。3者ワークフローの両サイド（派遣元／派遣先）への差戻し起票資料として必要 |

---

（以上）
